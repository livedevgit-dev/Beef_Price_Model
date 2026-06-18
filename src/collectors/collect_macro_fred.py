"""
[파일 정의서]
- 파일명: collect_macro_fred.py
- 역할: 수집
- 대상: 미국 거시경제 지표 (옥수수·WTI 원유·Food PPI)
- 데이터 소스: FRED (Federal Reserve Bank of St. Louis) API
    https://api.stlouisfed.org/fred/series/observations
- 수집/가공 주기: 일단위 — indicator_id별 기존 raw CSV max(date) 이후만 증분 수집
- 주요 기능:
    1. .env(FRED_API_KEY) 로딩. 키가 비어 있으면 즉시 graceful skip (파이프라인 중단 없음)
    2. Tier-1 미국 지표 3종을 long format 으로 수집하여 공통 raw CSV 에 병합
    3. 최초 실행 시 2019-01-01 부터 백필, 이후 증분
    4. indicator 단위 실패는 경고만 출력하고 다음 indicator 로 계속 진행

검증한 FRED series ID (공식: https://fred.stlouisfed.org/series/<ID>):
    us_corn      = PMAIZMTUSDM  (Global price of Corn, 월별, USD/metric ton, 1992~)  사료비 proxy
    us_wti       = DCOILWTICO   (Crude Oil Prices: WTI, Cushing OK, 일별, USD/barrel)
    us_food_ppi  = WPU02        (PPI by Commodity: Processed Foods and Feeds, 월별, Index 1982=100)
    us_soybean      = PSOYBUSDM (Global price of Soybeans, 월별, USD/metric ton, 1992~)  사료비
    us_soybean_meal = PSMEAUSDM (Global price of Soybean Meal, 월별, USD/metric ton)  대두박(사료 직접 투입재)

산출 컬럼(long format) — data/0_raw/macro_indicators_raw.csv:
    date, country, indicator_id, indicator_name, value, unit, freq, source
    - country = 'US', source = 'FRED'
    - 월별 지표의 date 는 FRED 규약대로 해당 월 1일(YYYY-MM-01)로 통일
    - 일별 지표(WTI)는 관측일 그대로
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
from config import MACRO_RAW_CSV, ensure_dirs

# 사내망 SSL 검사(중간 프록시)로 인한 인증서 오류 대응.
# collect_usda_primal.py 와 동일한 패턴 (verify=False + 경고 억제).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
INITIAL_START = date(2019, 1, 1)          # 다른 데이터셋과 정합
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_CALLS = 0.5                  # FRED 트래픽 보호

COUNTRY = "US"
SOURCE = "FRED"

# 공통 raw 파일 dedup 키 (모든 macro 소스 공유)
DUPLICATE_KEYS = ["date", "country", "indicator_id"]

# Tier-1 미국 지표 정의 (series ID 는 위 파일 정의서에서 공식 검증)
FRED_INDICATORS = [
    {
        "indicator_id": "us_corn",
        "series_id": "PMAIZMTUSDM",
        "indicator_name": "Global Price of Corn (사료비 proxy)",
        "unit": "USD/metric ton",
        "freq": "M",
    },
    {
        "indicator_id": "us_wti",
        "series_id": "DCOILWTICO",
        "indicator_name": "WTI Crude Oil (Cushing, OK)",
        "unit": "USD/barrel",
        "freq": "D",
    },
    {
        "indicator_id": "us_food_ppi",
        "series_id": "WPU02",
        "indicator_name": "PPI: Processed Foods and Feeds",
        "unit": "Index 1982=100",
        "freq": "M",
    },
    {
        "indicator_id": "us_soybean",
        "series_id": "PSOYBUSDM",
        "indicator_name": "Global Price of Soybeans (사료비)",
        "unit": "USD/metric ton",
        "freq": "M",
    },
    {
        "indicator_id": "us_soybean_meal",
        "series_id": "PSMEAUSDM",
        "indicator_name": "Global Price of Soybean Meal (대두박, 사료 직접 투입재)",
        "unit": "USD/metric ton",
        "freq": "M",
    },
]


# --------------------------------------------------------------------------
# 인증 / 유틸
# --------------------------------------------------------------------------
def _get_api_key() -> str | None:
    key = os.getenv("FRED_API_KEY", "").strip()
    return key or None


def _read_last_date(df_existing: pd.DataFrame, indicator_id: str) -> date | None:
    """공통 raw 에서 해당 indicator 의 마지막 수집일을 반환."""
    if df_existing.empty:
        return None
    mask = (df_existing["indicator_id"] == indicator_id)
    sub = df_existing.loc[mask, "date"]
    if sub.empty:
        return None
    parsed = pd.to_datetime(sub, errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.max().date()


def _normalize_date(raw_date: str, freq: str) -> str | None:
    """FRED 관측일을 표준 date 문자열로 변환. 월별은 YYYY-MM-01 로 통일."""
    dt = pd.to_datetime(raw_date, errors="coerce")
    if pd.isna(dt):
        return None
    if freq == "M":
        return dt.replace(day=1).strftime("%Y-%m-%d")
    return dt.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_series(
    api_key: str,
    indicator: dict,
    start: date,
    end: date,
) -> list[dict]:
    """단일 FRED series 를 long row 리스트로 반환."""
    params = {
        "series_id": indicator["series_id"],
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start.strftime("%Y-%m-%d"),
        "observation_end": end.strftime("%Y-%m-%d"),
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
    except requests.RequestException as e:
        # 예외 메시지에는 api_key 가 포함된 URL 이 들어갈 수 있으므로 타입만 출력
        print(f"   └ [예외] {indicator['indicator_id']}: 연결 실패 ({type(e).__name__})")
        return []

    if resp.status_code != 200:
        # FRED 는 키 오류 등을 400/403 + 메시지로 반환 → 경고만 출력하고 skip
        snippet = resp.text[:160].replace("\n", " ")
        print(f"   └ [에러] HTTP {resp.status_code} ({indicator['indicator_id']}): {snippet}")
        return []

    try:
        payload = resp.json()
    except ValueError:
        print(f"   └ [에러] JSON 파싱 실패 ({indicator['indicator_id']})")
        return []

    observations = payload.get("observations", []) if isinstance(payload, dict) else []
    long_rows: list[dict] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        raw_value = str(obs.get("value", "")).strip()
        if raw_value in {"", ".", "-"}:   # FRED 결측 표기는 '.'
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        norm_date = _normalize_date(obs.get("date", ""), indicator["freq"])
        if norm_date is None:
            continue
        long_rows.append({
            "date": norm_date,
            "country": COUNTRY,
            "indicator_id": indicator["indicator_id"],
            "indicator_name": indicator["indicator_name"],
            "value": value,
            "unit": indicator["unit"],
            "freq": indicator["freq"],
            "source": SOURCE,
        })

    # 월별: 같은 달 중복 방지 위해 (date) 기준 마지막 값만 (이론상 중복 없음)
    return long_rows


# --------------------------------------------------------------------------
# 누적 저장 (공통 raw 파일 — ECOS 와 공유)
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

    df_final["_sort_dt"] = pd.to_datetime(df_final["date"], errors="coerce")
    df_final = df_final.sort_values(
        by=["_sort_dt", "country", "indicator_id"]
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


def _load_existing(save_path: Path) -> pd.DataFrame:
    if not save_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(save_path, low_memory=False)
    except Exception:
        return pd.DataFrame()


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_macro_fred_increment() -> None:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)

    api_key = _get_api_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 FRED_API_KEY 가 비어 있습니다.\n"
            "         발급 후 입력하면 다음 실행부터 미국 거시지표가 자동 수집됩니다.\n"
            "         발급: https://fredaccount.stlouisfed.org/apikeys"
        )
        return

    df_existing = _load_existing(save_path)
    today = date.today()

    new_rows: list[dict] = []
    for indicator in FRED_INDICATORS:
        last_date = _read_last_date(df_existing, indicator["indicator_id"])
        if last_date is None:
            start = INITIAL_START
            print(f"[수집] {indicator['indicator_id']} ({indicator['series_id']}) "
                  f"— 기존 없음 → {start} 부터 전체")
        else:
            start = last_date + timedelta(days=1)
            print(f"[수집] {indicator['indicator_id']} ({indicator['series_id']}) "
                  f"— 마지막 {last_date} → {start} 부터 증분")

        if start > today:
            print("   └ 이미 최신")
            continue

        rows = _fetch_series(api_key, indicator, start, today)
        print(f"   └ 신규 {len(rows)}건")
        new_rows.extend(rows)
        time.sleep(SLEEP_BETWEEN_CALLS)

    if not new_rows:
        print("[안내] FRED 신규 데이터가 없습니다.")
        return

    total = _merge_and_save(new_rows, save_path)
    print(f"[완료] FRED 신규 {len(new_rows)}건 병합 — raw 누적 총 {total}건 ({save_path})")


if __name__ == "__main__":
    collect_macro_fred_increment()
