"""
[파일 정의서]
- 파일명: collect_kamis_hanwoo.py
- 역할: 수집
- 대상: 한우 도/소매 가격 (KAMIS 한국농수산식품유통공사)
- 데이터 소스:
    http://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList
- 수집/가공 주기: 일단위 — 기존 CSV의 마지막 reg_date 이후 영업일만 증분 수집
- 주요 기능:
    1. .env(KAMIS_CERT_KEY, KAMIS_CERT_ID) 로딩
    2. 키가 비어 있으면 즉시 graceful skip (파이프라인 중단 없이 종료)
    3. 도매(p_product_cls_code=02) + 소매(=01) 각각 호출하여 부류=500(축산물) 응답을 받아 한우/소 row만 필터링
    4. 일자별 호출 (KAMIS 1번 API는 하루 단위 조회. 1만 호출/일 한도 내에서 백필 충분)
    5. 누적 CSV(`data/0_raw/kamis_hanwoo_raw.csv`)에 (reg_date, item_name, kind_name, product_cls_code, country_name) 키 기준 중복 제거 병합

산출 컬럼(long format):
    reg_date, product_cls_code, product_cls_name (도매/소매),
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
def _fetch_day(
    cert_key: str,
    cert_id: str,
    target_date: date,
    product_cls_code: str,
) -> list[dict]:
    """일자 + 도매/소매 구분으로 한 번 호출. 한우 row만 필터링하여 long row 반환."""
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
        return []

    if resp.status_code != 200:
        print(f"   └ [에러] HTTP {resp.status_code}")
        return []

    try:
        payload = resp.json()
    except ValueError:
        # 인증 실패 등은 텍스트로 떨어지는 경우가 있음
        snippet = resp.text[:200].replace("\n", " ")
        print(f"   └ [에러] JSON 파싱 실패. 응답 일부: {snippet}")
        return []

    # KAMIS 응답은 케이스에 따라 dict({'condition': ..., 'price': [...]}) 또는 dict({'data': {...}})
    items: list[dict] = []
    if isinstance(payload, dict):
        if "price" in payload and isinstance(payload["price"], list):
            items = payload["price"]
        elif "data" in payload and isinstance(payload["data"], dict):
            inner = payload["data"].get("item")
            if isinstance(inner, list):
                items = inner
        elif isinstance(payload.get("error_code", None), str):
            print(f"   └ [KAMIS 에러] {payload.get('error_code')}")
            return []

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
def _merge_and_save(new_rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(new_rows)
    if df_new.empty:
        return _existing_row_count(save_path)

    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    if subset:
        df_final = df_final.drop_duplicates(subset=subset, keep="last")

    if "reg_date" in df_final.columns:
        df_final["_sort_dt"] = pd.to_datetime(df_final["reg_date"], errors="coerce")
        df_final = df_final.sort_values(
            by=["_sort_dt", "product_cls_code", "kind_name"]
        ).drop(columns=["_sort_dt"])

    save_path.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(str(save_path), index=False, encoding="utf-8-sig")
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
def collect_kamis_hanwoo_increment() -> None:
    ensure_dirs()
    save_path = Path(KAMIS_HANWOO_RAW_CSV)
    creds = _get_credentials()
    if creds is None:
        print(
            "[건너뜀] .env 의 KAMIS_CERT_KEY / KAMIS_CERT_ID 가 비어 있습니다.\n"
            "         KAMIS 신청 후 키를 입력하면 다음 실행부터 자동 수집됩니다.\n"
            "         신청: https://www.kamis.or.kr/customer/reference/openapi_list.do"
        )
        return
    cert_key, cert_id = creds

    last_date = _read_last_date(save_path)
    today = date.today()

    if last_date is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start} 부터 전체 수집")
    else:
        start = last_date + timedelta(days=1)
        print(f"[시스템] 기존 데이터 마지막일: {last_date} → {start} 부터 증분 수집")

    if start > today:
        print("[성공] 이미 최신 상태입니다.")
        return

    all_days = _iter_dates(start, today)
    if len(all_days) > MAX_DAYS_PER_RUN:
        print(
            f"[안내] 백필 범위 {len(all_days)}일 → 1회 실행 한도 {MAX_DAYS_PER_RUN}일로 제한.\n"
            f"        다음 실행 때 이어서 진행합니다."
        )
        all_days = all_days[:MAX_DAYS_PER_RUN]

    print(
        f"[안내] {len(all_days)}일 × 2(도매/소매) = {len(all_days) * 2} 호출 "
        f"({all_days[0]} ~ {all_days[-1]})"
    )

    new_rows: list[dict] = []
    failed_days: list[date] = []
    for i, d in enumerate(all_days, 1):
        day_rows: list[dict] = []
        for product_cls_code in ("02", "01"):
            rows = _fetch_day(cert_key, cert_id, d, product_cls_code)
            day_rows.extend(rows)
            time.sleep(SLEEP_BETWEEN_CALLS)
        if day_rows:
            new_rows.extend(day_rows)
        else:
            failed_days.append(d)

        if i % 30 == 0:
            print(
                f" - 진행 {i}/{len(all_days)} 일, 누적 신규 row {len(new_rows)}, "
                f"실패일 {len(failed_days)}"
            )

    if not new_rows:
        print("[안내] 한우 데이터를 수집하지 못했습니다 (KAMIS 측 공휴일·미게시 등 가능).")
        return

    total = _merge_and_save(new_rows, save_path)
    print(
        f"[완료] 신규 {len(new_rows)}건 병합 — 누적 총 {total}건 ({save_path}) "
        f"/ 빈 응답일 {len(failed_days)}일"
    )


if __name__ == "__main__":
    collect_kamis_hanwoo_increment()
