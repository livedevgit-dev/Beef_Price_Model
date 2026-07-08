"""
[파일 정의서]
- 파일명: collect_kamis_pork.py
- 역할: 수집
- 대상: 돼지고기 도/소매 가격 (국내 돼지 + 수입 돼지고기)
- 데이터 소스: KAMIS(한국농수산식품유통공사)
    http://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList
- 배경: 외식(요식업)이 대량 소비하는 돼지고기(삼겹살 등)와 수입 돼지고기는
        수입육 삼겹양지의 대체재이자 국내 소비/외식 공급가 신호. 수요측 지표(대형마트·
        음식점 생산지수·품목 CPI)와 짝을 이루는 공급측 지표로 사용한다.
- 수집/가공 주기: 일단위 — 기존 CSV의 마지막 reg_date 이후 영업일만 증분 수집
- 주요 기능:
    1. .env(KAMIS_CERT_KEY, KAMIS_CERT_ID) 로딩. 키 없으면 즉시 graceful skip
    2. 도매(02) + 소매(01) 각각 호출, 부류=500(축산물) 응답에서 돼지 row만 필터링
    3. 누적 CSV(`data/0_raw/kamis_pork_raw.csv`)에 중복 제거 병합
- 필터: item_name 이 '돼지'(국내) 또는 '수입 돼지고기'(수입) 인 행만.

산출 컬럼(long format) — collect_kamis_hanwoo 와 동일 스키마:
    reg_date, product_cls_code, product_cls_name(도매/소매),
    item_name(돼지 / 수입 돼지고기), kind_name(부위 — 삼겹살/앞다리/갈비/목심),
    rank, unit, country_name, market_name, price
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import KAMIS_PORK_RAW_CSV, ensure_dirs

# 사내망 SSL 검사(중간 프록시) 대응 — 한우 수집기와 동일 패턴
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
API_URL = "http://www.kamis.or.kr/service/price/xml.do"
ITEM_CATEGORY_LIVESTOCK = "500"   # 축산물
INITIAL_START = date(2019, 1, 1)  # 다른 데이터셋과 정합
REQUEST_TIMEOUT = 20
SLEEP_BETWEEN_CALLS = 0.3         # KAMIS 트래픽 보호 (개발계정 1만/일)
MAX_DAYS_PER_RUN = 3000           # 1회 실행당 상한. 도매+소매 2콜/일 → 3000일도 6천콜 < KAMIS 1만/일 한도
CHECKPOINT_DAYS = 120             # 이 일수마다 중간 저장 (진행 가시화 + 중단 시 이어받기 안전)

# 돼지 식별 — 응답 item_name 텍스트 기반 (국내 '돼지' + '수입 돼지고기' 모두)
PORK_ITEM_NAMES = ("돼지",)  # '수입 돼지고기'도 '돼지' 포함 → 부분일치로 둘 다 포착

DUPLICATE_KEYS = [
    "reg_date",
    "product_cls_code",
    "item_name",
    "kind_name",
    "rank",
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


def _is_pork_row(row: dict) -> bool:
    """돼지(국내/수입)인지 판별."""
    item_name = str(row.get("item_name", "") or "")
    return any(k in item_name for k in PORK_ITEM_NAMES)


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_day(cert_key: str, cert_id: str, target_date: date, product_cls_code: str) -> list[dict]:
    """일자 + 도매/소매 구분으로 한 번 호출. 돼지 row만 필터링하여 long row 반환."""
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
        # 예외 메시지에 인증정보가 포함된 URL 이 들어갈 수 있으므로 타입만 출력
        print(f"   └ [예외] {target_date} {product_cls_code}: 연결 실패 ({type(e).__name__})")
        return []

    if resp.status_code != 200:
        print(f"   └ [에러] HTTP {resp.status_code}")
        return []

    try:
        payload = resp.json()
    except ValueError:
        snippet = resp.text[:200].replace("\n", " ")
        print(f"   └ [에러] JSON 파싱 실패. 응답 일부: {snippet}")
        return []

    # KAMIS 응답: dict({'price': [...]}) 또는 dict({'data': {'item': [...]}})
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
        if not _is_pork_row(it):
            continue

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
            "item_name": str(it.get("item_name", "") or "").strip(),   # 돼지 / 수입 돼지고기
            "kind_name": str(it.get("kind_name", "") or "").strip(),   # 부위 (삼겹살/앞다리/갈비/목심)
            "rank": str(it.get("rank", "") or "").strip(),
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
def collect_kamis_pork_increment() -> None:
    ensure_dirs()
    save_path = Path(KAMIS_PORK_RAW_CSV)
    creds = _get_credentials()
    if creds is None:
        print(
            "[건너뜀] .env 의 KAMIS_CERT_KEY / KAMIS_CERT_ID 가 비어 있습니다.\n"
            "         (한우 수집기와 동일 키. 입력 시 다음 실행부터 돼지가격도 자동 수집)"
        )
        return
    cert_key, cert_id = creds

    last_date = _read_last_date(save_path)
    today = date.today()

    if last_date is None:
        start = INITIAL_START
        print(f"[시스템] KAMIS 돼지 기존 데이터 없음 → {start} 부터 전체 수집")
    else:
        start = last_date + timedelta(days=1)

    if start > today:
        print(f"[안내] KAMIS 돼지 이미 최신 (마지막 {last_date})")
        return

    # 백필 상한 적용
    end = min(today, start + timedelta(days=MAX_DAYS_PER_RUN - 1))
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)

    print(f"[시스템] KAMIS 돼지 도/소매 수집: {start} ~ {end} ({len(days)}일, {CHECKPOINT_DAYS}일마다 중간 저장)")
    buffer: list[dict] = []          # 체크포인트 대기 버퍼
    collected_total = 0              # 이번 실행 누적 신규건
    days_since_ckpt = 0

    def _flush():
        """버퍼를 파일에 병합 저장하고 비운다 (중단 대비·진행 가시화)."""
        nonlocal buffer, collected_total
        if not buffer:
            return
        total = _merge_and_save(buffer, save_path)
        collected_total += len(buffer)
        print(f"   └ [중간저장] +{len(buffer)}건 → 파일 누적 {total}건 (~{buffer[-1]['reg_date']}까지)")
        buffer = []

    for d in days:
        for cls in ("02", "01"):   # 도매, 소매
            rows = _fetch_day(cert_key, cert_id, d, cls)
            buffer.extend(rows)
            time.sleep(SLEEP_BETWEEN_CALLS)
        days_since_ckpt += 1
        if days_since_ckpt >= CHECKPOINT_DAYS:
            _flush()
            days_since_ckpt = 0

    _flush()   # 잔여분 저장

    if collected_total == 0:
        print("[안내] KAMIS 돼지 신규 데이터 없음 (주말·공휴일 구간이거나 미게시).")
        return

    print(f"[완료] KAMIS 돼지 신규 {collected_total}건 수집 — 최종 {end}까지 ({save_path})")


if __name__ == "__main__":
    collect_kamis_pork_increment()
