"""
[파일 정의서]
- 파일명: collect_kamis_hanwoo.py
- 역할: 수집
- 대상: 한우 부위별 소매 가격 (KAMIS 한국농수산식품유통공사)
- 데이터 소스:
    http://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList
- 수집/가공 주기: 일단위 — 마지막 reg_date 이후 + 최근 REFETCH_DAYS(7)일을 매번 다시 받아 교체(일시 실패·지연 게시 자가 복구)
- 주요 기능:
    1. .env(KAMIS_CERT_KEY, KAMIS_CERT_ID) 로딩
    2. 키가 비어 있으면 즉시 graceful skip (파이프라인 중단 없이 종료)
    3. 소매(p_product_cls_code=01)만 호출하여 부류=500(축산물) 응답에서 한우/소 row만 필터링
       ※ 2026-10-30 확인: 축산물은 p_product_cls_code 를 무시하고 02(도매) 요청에도 소매와 100% 동일한 응답을 준다
         (과거 누적 42,900쌍 전부 일치, 가격 수준도 소매). → 도매 요청 중단, 누적분의 02 행은 병합 시 제거.
         도매 기준가는 EKAPE 도체 경락가(crawl_han_auction_api.py)를 사용한다.
    4. 일자별 호출 (KAMIS 1번 API는 하루 단위 조회. 1만 호출/일 한도 내에서 백필 충분)
    5. 누적 CSV(`data/0_raw/kamis_hanwoo_raw.csv`): 이번에 정상 응답을 받은 일자의 기존 행은 새 응답으로 교체,
       나머지는 (reg_date, product_cls_code, item_name, kind_name, rank, country_name, market_name) 키로 중복 제거
    6. 응답 없음(error_code 001·빈 목록 = 휴장/미게시)은 정상, 네트워크/HTTP/파싱/그 외 error_code 는 실패로 집계 →
       끝에 요약 출력 후 실패가 있으면 exit 1 (받은 데이터는 저장)

산출 컬럼(long format):
    reg_date, product_cls_code('01'), product_cls_name('소매'),
    item_name (예: 소), kind_name (부위 — 예: 안심/등심/설도/양지),
    rank (등급 — 예: 1++등급/1+등급/1등급),
    unit (예: 100g), country_name, market_name, price

주의: KAMIS 실제 응답에서 부위는 kind_name, 등급은 별도 rank 필드로 분리되어 있다.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import KAMIS_HANWOO_RAW_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# 사내망 SSL 검사(중간 프록시) 대응 — KAMIS는 http 요청이 https 로 리다이렉트됨 (USDA/Macro 수집기와 동일 패턴)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
API_URL = "http://www.kamis.or.kr/service/price/xml.do"
ITEM_CATEGORY_LIVESTOCK = "500"   # 축산물
INITIAL_START = date(2019, 1, 1)  # 다른 데이터셋과 정합성
REQUEST_TIMEOUT = 20
SLEEP_BETWEEN_CALLS = 0.3         # KAMIS 트래픽 보호 (개발계정 1만/일)
MAX_DAYS_PER_RUN = 400            # 1회 실행당 안전 상한 (백필 분할)
REFETCH_DAYS = 7                  # 매 실행 재수집·교체하는 최근 일수
PRODUCT_CLS_CODE = "01"           # 소매만 (축산물은 02 요청도 소매와 동일 응답 — 파일 정의서 참고)

# 한우(국내산 소) 식별 — 응답의 item_name/kind_name 텍스트 기반 필터
# kind_name 예시: "안심(1++등급)", "등심(1+등급)", "갈비(1등급)" 등
HANWOO_ITEM_NAMES = {"소", "쇠고기", "한우"}
IMPORT_KEYWORDS = ("수입", "미국산", "호주산", "뉴질랜드", "캐나다", "멕시코")

DUPLICATE_KEYS = [
    "reg_date",
    "product_cls_code",
    "item_name",
    "kind_name",
    "rank",          # 등급(1++/1+/1 등). 부위(kind_name)가 같아도 등급별로 다른 row 이므로 필수
    "country_name",
    "market_name",
]


# --------------------------------------------------------------------------
# 인증 / 유틸
# --------------------------------------------------------------------------
def _get_credentials() -> tuple[str, str] | None:
    cert_key = os.getenv("KAMIS_CERT_KEY", "").strip()
    cert_id = os.getenv("KAMIS_CERT_ID", "").strip()
    if not cert_key or not cert_id:
        return None
    return cert_key, cert_id


def _read_last_date(save_path: Path) -> date | None:
    if not save_path.exists():
        return None
    try:
        df = pd.read_csv(save_path, usecols=["reg_date"], low_memory=False)
    except Exception:
        return None
    if df.empty:
        return None
    parsed = pd.to_datetime(df["reg_date"], errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.max().date()


def _iter_dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def _is_hanwoo_row(row: dict) -> bool:
    """한우(국내산 소)인지 판별. 수입육·국내 돼지·닭 등은 제외."""
    item_name = str(row.get("item_name", "") or "")
    kind_name = str(row.get("kind_name", "") or "")
    if not any(k in item_name for k in HANWOO_ITEM_NAMES):
        return False
    text = f"{item_name} {kind_name}"
    if any(k in text for k in IMPORT_KEYWORDS):
        return False
    return True


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
KAMIS_OK_CODES = {"", "000"}      # 정상
KAMIS_NODATA_CODES = {"001"}      # 데이터 없음(휴장·미게시) — 오류 아님


def _extract_items(payload, target_date: date) -> list[dict] | None:
    """KAMIS 응답에서 item 목록 추출. 데이터 없음 → [], 오류·예상 밖 구조 → None.
    응답 형태: {'condition':..., 'data': {'error_code': '000', 'item': [...]}}
              {'data': ['001']} (데이터 없음) / {'price': [...]} (구버전)"""
    if not isinstance(payload, dict):
        print(f"   └ [에러] {target_date} 예상 밖 응답 형식: {type(payload).__name__}")
        return None
    if isinstance(payload.get("price"), list):
        return payload["price"]
    data = payload.get("data")
    if isinstance(data, dict):
        code = str(data.get("error_code", "") or "").strip()
        if code in KAMIS_NODATA_CODES:
            return []
        if code not in KAMIS_OK_CODES:
            print(f"   └ [KAMIS 에러] {target_date} error_code={code}")
            return None
        inner = data.get("item")
        if inner is None:
            return []
        return inner if isinstance(inner, list) else [inner]
    if isinstance(data, list):
        codes = {str(x).strip() for x in data if not isinstance(x, dict)}
        if not codes or codes <= KAMIS_NODATA_CODES:
            return [x for x in data if isinstance(x, dict)]
        print(f"   └ [KAMIS 에러] {target_date} error_code={sorted(codes)}")
        return None
    code = str(payload.get("error_code", "") or "").strip()
    if code in KAMIS_NODATA_CODES:
        return []
    print(f"   └ [에러] {target_date} 예상 밖 응답 구조: keys={list(payload.keys())} error_code={code or '-'}")
    return None


def _fetch_day(
    cert_key: str,
    cert_id: str,
    target_date: date,
    product_cls_code: str = PRODUCT_CLS_CODE,
) -> list[dict] | None:
    """일자별 한 번 호출. 한우 row만 필터링하여 long row 반환.
    정상 응답이면 list(휴장·미게시일은 빈 list), 네트워크/HTTP/파싱/API 오류면 None."""
    params = {
        "action": "dailyPriceByCategoryList",
        "p_cert_key": cert_key,
        "p_cert_id": cert_id,
        "p_returntype": "json",
        "p_product_cls_code": product_cls_code,
        "p_item_category_code": ITEM_CATEGORY_LIVESTOCK,
        "p_regday": target_date.strftime("%Y-%m-%d"),
        "p_convert_kg_yn": "N",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
    except requests.RequestException as e:
        # 예외 메시지에 p_cert_key/p_cert_id 가 포함된 URL 이 들어갈 수 있으므로 타입만 출력
        print(f"   └ [예외] {target_date} {product_cls_code}: 연결 실패 ({type(e).__name__})")
        return None

    if resp.status_code != 200:
        print(f"   └ [에러] {target_date} HTTP {resp.status_code}")
        return None

    try:
        payload = resp.json()
    except ValueError:
        # 인증 실패 등은 텍스트로 떨어지는 경우가 있음
        snippet = resp.text[:200].replace("\n", " ")
        print(f"   └ [에러] {target_date} JSON 파싱 실패. 응답 일부: {snippet}")
        return None

    items = _extract_items(payload, target_date)
    if items is None:
        return None
    if not items:
        return []

    product_cls_name = "도매" if product_cls_code == "02" else "소매"
    long_rows: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if not _is_hanwoo_row(it):
            continue

        # 'dpr1' (당일가) 가 핵심. 결측·하이픈은 None 처리.
        raw_price = str(it.get("dpr1", "") or "").replace(",", "").strip()
        if raw_price in {"", "-", "0"}:
            price = None
        else:
            try:
                price = float(raw_price)
            except ValueError:
                price = None

        long_rows.append({
            "reg_date": target_date.strftime("%Y-%m-%d"),
            "product_cls_code": product_cls_code,
            "product_cls_name": product_cls_name,
            "item_name": str(it.get("item_name", "") or "").strip(),
            "kind_name": str(it.get("kind_name", "") or "").strip(),   # 부위 (안심/등심/설도/양지 …)
            "rank": str(it.get("rank", "") or "").strip(),             # 등급 (1++등급/1+등급/1등급 …)
            "unit": str(it.get("unit", "") or "").strip(),
            "country_name": str(it.get("countyname", it.get("county_name", "")) or "").strip(),
            "market_name": str(it.get("marketname", it.get("market_name", "")) or "").strip(),
            "price": price,
        })
    return long_rows


# --------------------------------------------------------------------------
# 누적 저장
# --------------------------------------------------------------------------
def _merge_and_save(new_rows: list[dict], fetched_dates: set[str], save_path: Path) -> int:
    """fetched_dates(정상 응답 일자)의 기존 행은 새 응답으로 교체 후 병합."""
    df_new = pd.DataFrame(new_rows)
    if df_new.empty and not fetched_dates and save_path.exists():
        return _existing_row_count(save_path)

    if save_path.exists():
        df_old = pd.read_csv(save_path, dtype={"product_cls_code": str}, low_memory=False)
        df_old = df_old[~df_old["reg_date"].astype(str).isin(fetched_dates)]
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new
    if df_final.empty:
        return 0

    # product_cls_code 가 CSV 재로딩 시 int(1/2)로 읽혀 '01' 과 키가 어긋나던 문제 → 문자열 2자리로 고정
    df_final["product_cls_code"] = df_final["product_cls_code"].astype(str).str.strip().str.zfill(2)
    # 도매(02) 행은 소매 응답의 중복이므로 제거 (파일 정의서 참고)
    df_final = df_final[df_final["product_cls_code"] != "02"]

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    if subset:
        df_final = df_final.drop_duplicates(subset=subset, keep="last")

    if "reg_date" in df_final.columns:
        df_final["_sort_dt"] = pd.to_datetime(df_final["reg_date"], errors="coerce")
        df_final = df_final.sort_values(
            by=["_sort_dt", "product_cls_code", "kind_name"]
        ).drop(columns=["_sort_dt"])

    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


def _existing_row_count(save_path: Path) -> int:
    if not save_path.exists():
        return 0
    try:
        return sum(1 for _ in open(save_path, "r", encoding="utf-8-sig")) - 1
    except OSError:
        return 0


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_kamis_hanwoo_increment() -> int:
    """증분 수집. 반환값 = 실패(오류) 일수."""
    ensure_dirs()
    save_path = Path(KAMIS_HANWOO_RAW_CSV)
    creds = _get_credentials()
    if creds is None:
        print(
            "[건너뜀] .env 의 KAMIS_CERT_KEY / KAMIS_CERT_ID 가 비어 있습니다.\n"
            "         KAMIS 신청 후 키를 입력하면 다음 실행부터 자동 수집됩니다.\n"
            "         신청: https://www.kamis.or.kr/customer/reference/openapi_list.do"
        )
        return 0
    cert_key, cert_id = creds

    last_date = _read_last_date(save_path)
    today = date.today()

    if last_date is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start} 부터 전체 수집")
    else:
        # 마지막일 다음날부터 + 최근 REFETCH_DAYS 일은 매번 재수집(교체)
        start = min(last_date + timedelta(days=1), today - timedelta(days=REFETCH_DAYS - 1))
        print(f"[시스템] 기존 데이터 마지막일: {last_date} → {start} 부터 수집 (최근 {REFETCH_DAYS}일 재수집 포함)")

    all_days = _iter_dates(start, today)
    if len(all_days) > MAX_DAYS_PER_RUN:
        print(
            f"[안내] 백필 범위 {len(all_days)}일 → 1회 실행 한도 {MAX_DAYS_PER_RUN}일로 제한.\n"
            f"        다음 실행 때 이어서 진행합니다."
        )
        all_days = all_days[:MAX_DAYS_PER_RUN]

    print(f"[안내] {len(all_days)}일 × 소매 1회 = {len(all_days)} 호출 ({all_days[0]} ~ {all_days[-1]})")

    new_rows: list[dict] = []
    fetched_dates: set[str] = set()
    empty_days: list[date] = []
    failed_days: list[date] = []
    for i, d in enumerate(all_days, 1):
        rows = _fetch_day(cert_key, cert_id, d)
        time.sleep(SLEEP_BETWEEN_CALLS)
        if rows is None:
            failed_days.append(d)
        else:
            fetched_dates.add(d.strftime("%Y-%m-%d"))
            if rows:
                new_rows.extend(rows)
            else:
                empty_days.append(d)

        if i % 30 == 0:
            print(
                f" - 진행 {i}/{len(all_days)} 일, 누적 신규 row {len(new_rows)}, "
                f"빈 응답 {len(empty_days)}일, 실패 {len(failed_days)}일"
            )

    if fetched_dates:
        total = _merge_and_save(new_rows, fetched_dates, save_path)
        print(f"[완료] 신규 {len(new_rows)}건 반영 — 누적 총 {total}건 ({save_path})")
    print(
        f"[요약] {len(all_days)}일 호출: 정상 {len(fetched_dates)}일 "
        f"(데이터 없음 {len(empty_days)}일) / 실패 {len(failed_days)}일"
    )
    if failed_days:
        print(f"[경고] 실패일 {len(failed_days)}건 (첫 3건: {failed_days[:3]}) — 최근 {REFETCH_DAYS}일 이내는 다음 실행에서 재시도됩니다.")
    return len(failed_days)


if __name__ == "__main__":
    sys.exit(1 if collect_kamis_hanwoo_increment() else 0)
