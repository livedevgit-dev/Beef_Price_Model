"""
[파일 정의서]
- 파일명: collect_nass_supply.py
- 역할: 수집
- 대상: 미국 소고기 공급 지표 — 냉동 쇠고기 재고(월간) · 연방검사(FI) 소 도축두수(주간) · FI 쇠고기 생산량(주간)
- 데이터 소스: USDA NASS Quick Stats API (키 필요 — .env NASS_API_KEY, collect_cattle_on_feed.py 와 공유)
    https://quickstats.nass.usda.gov/api/api_GET/?key=...&commodity_desc=...&statisticcat_desc=...&year=YYYY&format=JSON
    키 발급(무료): https://quickstats.nass.usda.gov/api
- 수집/가공 주기: 일단위 실행 — 매 실행 올해·작년 2개 연도를 다시 받아 해당 구간 행을 교체(소급 정정 반영)
- 주요 기능:
    1. NASS Quick Stats 3종을 long format 으로 수집하여 공통 거시 raw CSV(FRED·ECOS·KMA·MLA 와 공유)에 병합
         us_beef_cold_storage   = 월간 미국 냉동 쇠고기 재고 (Cold Storage 보고서, 월말 기준, lb → t 환산)
                                   short_desc 'BEEF, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB' (TOTAL 만, BONE-IN/BONELESS 분할 제외)
                                   reference_period_desc 'END OF SEP' → 해당 월 1일 (2026-09-01) 로 저장
                                   ※ NASS 의 freq_desc 는 'POINT IN TIME' 이라 MONTHLY 필터는 쓰지 않고 'END OF' 접두어로 판별
         us_cattle_slaughter_wk = 주간 미국 연방검사(FI) 소 도축두수 (Livestock Slaughter 주간, 주말(토) 기준 week_ending)
                                   short_desc 'CATTLE, GE 500 LBS, SLAUGHTER, COMMERCIAL, FI - SLAUGHTERED, MEASURED IN HEAD'
                                   (NASS 는 '전체 소' 단일 시리즈를 주지 않고 GE 500 LBS(=거세우+미경산우+암소+수소, 송아지 제외) 가
                                    주간 보고서의 'Cattle' 합계에 해당 — 2026-11-07 주 535,500두)
         us_beef_production_wk  = 주간 미국 FI 쇠고기 생산량 (lb → t 환산)
                                   short_desc 'BEEF, SLAUGHTER, COMMERCIAL, FI - PRODUCTION, MEASURED IN LB'
                                   (도축두수 응답에는 없고 commodity_desc=BEEF&statisticcat_desc=PRODUCTION 별도 조회 — 연도당 1회 추가 호출)
    2. 조회 단위 = 연도(year=YYYY) — 조회당 1회 호출. sector_desc 는 넣지 않는다(Quick Stats 가 invalid query 로 거절).
       - 증분(기본): 올해·작년 2개 연도 재수집 → 해당 indicator 의 작년 1월 1일 이후 기존 행을 이번 응답으로 교체
       - 백필: --backfill-from YYYY → YYYY~올해 전 연도 수집, YYYY-01-01 이후 행 교체 (최초 1회, 2005 부터 권장)
    3. 값 정제: NASS Value 는 천 단위 콤마 문자열이고 '(D)'(비공개) '(NA)' '(Z)' 등 자리표시자가 섞여 있어 숫자 변환 실패 행은 버린다.
       lb 단위는 metric ton 으로 환산 (lb × 0.45359237 / 1000), unit 't'.
    4. 오류 처리 (다른 macro 수집기와 동일)
       - 네트워크 예외 / HTTP 200 이외 / JSON 파싱 실패 / {"error":[...]} 응답 → 오류. 해당 시리즈는 한 연도라도 실패하면
         받은 행을 저장하지 않고 기존 값 유지(부분 연도로 구간을 지우지 않기 위해), 다른 시리즈는 정상 반영 후 exit 1
       - HTTP 200 + 0행(올해 미발표 등) → 정상(exit 0)
       - 기존 raw CSV 를 읽지 못하면 수집 전 중단(exit 1). 키 미설정은 graceful skip(exit 0)
    5. 발표 지연: 냉동 재고는 익월 ~23일(약 1개월), 주간 도축·생산은 해당 주 다음 목요일(약 1~2주)

산출 컬럼(long format) — data/0_raw/macro_indicators_raw.csv:
    date, country, indicator_id, indicator_name, value, unit, freq, source
    - country = 'US', source = 'NASS', freq = 'M'(냉동 재고) / 'W'(주간 도축·생산)

사용법:
    python src/collectors/collect_nass_supply.py                      # 증분(올해·작년 재수집)
    python src/collectors/collect_nass_supply.py --backfill-from 2005 # 최초 백필
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MACRO_RAW_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# 사내망 SSL 검사(중간 프록시)로 인한 인증서 오류 대응 (다른 수집기와 동일 패턴)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
BASE_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
REQUEST_TIMEOUT = 90
RETRIES = 3
SLEEP_BETWEEN_CALLS = 0.5
REFETCH_YEARS = 2                         # 증분 시 재수집 연도 수 (올해·작년)
MIN_BACKFILL_YEAR = 1990

COUNTRY = "US"
SOURCE = "NASS"
LB_TO_T = 0.45359237 / 1000.0             # lb → metric ton

DUPLICATE_KEYS = ["date", "country", "indicator_id"]

# 월 매핑 (reference_period_desc: 'END OF SEP' 등)
_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

# 조회(연도별 1회 호출) → 그 응답에서 뽑는 시리즈(short_desc → indicator)
NASS_QUERIES = [
    {
        "label": "BEEF/STOCKS (냉동 재고)",
        "params": {"commodity_desc": "BEEF", "statisticcat_desc": "STOCKS"},
        "date_mode": "end_of_month",       # year + reference_period_desc('END OF SEP') → 월 1일
        "series": {
            "BEEF, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB": {
                "indicator_id": "us_beef_cold_storage",
                "indicator_name": "USDA NASS Cold Storage — 미국 냉동 쇠고기 재고 (월말, 전체)",
                "unit": "t",
                "freq": "M",
                "scale": LB_TO_T,
            },
        },
    },
    {
        "label": "CATTLE/SLAUGHTERED WEEKLY (주간 도축두수)",
        "params": {"commodity_desc": "CATTLE", "statisticcat_desc": "SLAUGHTERED",
                   "freq_desc": "WEEKLY", "agg_level_desc": "NATIONAL"},
        "date_mode": "week_ending",
        "series": {
            "CATTLE, GE 500 LBS, SLAUGHTER, COMMERCIAL, FI - SLAUGHTERED, MEASURED IN HEAD": {
                "indicator_id": "us_cattle_slaughter_wk",
                "indicator_name": "USDA NASS 주간 연방검사(FI) 소 도축두수 (500lb 이상, 송아지 제외)",
                "unit": "head",
                "freq": "W",
                "scale": 1.0,
            },
        },
    },
    {
        "label": "BEEF/PRODUCTION WEEKLY (주간 쇠고기 생산량)",
        "params": {"commodity_desc": "BEEF", "statisticcat_desc": "PRODUCTION",
                   "freq_desc": "WEEKLY", "agg_level_desc": "NATIONAL"},
        "date_mode": "week_ending",
        "series": {
            "BEEF, SLAUGHTER, COMMERCIAL, FI - PRODUCTION, MEASURED IN LB": {
                "indicator_id": "us_beef_production_wk",
                "indicator_name": "USDA NASS 주간 연방검사(FI) 쇠고기 생산량",
                "unit": "t",
                "freq": "W",
                "scale": LB_TO_T,
            },
        },
    },
]

ALL_INDICATOR_IDS = [s["indicator_id"] for q in NASS_QUERIES for s in q["series"].values()]


# --------------------------------------------------------------------------
# 유틸
# --------------------------------------------------------------------------
def _get_key() -> str | None:
    return os.getenv("NASS_API_KEY", "").strip() or None


def _read_last_date(df_existing: pd.DataFrame, indicator_id: str) -> date | None:
    if df_existing.empty or "indicator_id" not in df_existing.columns:
        return None
    sub = df_existing.loc[df_existing["indicator_id"] == indicator_id, "date"]
    if sub.empty:
        return None
    parsed = pd.to_datetime(sub, errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.max().date()


def _parse_value(raw) -> float | None:
    """NASS Value 문자열('400,006,000', '(D)', '(NA)') → float. 숫자가 아니면 None."""
    s = str(raw).replace(",", "").strip()
    if not s or s.startswith("("):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_month_start(year, ref: str):
    """year + reference_period_desc('END OF SEP') → 해당 월 1일. 'END OF' 가 아니면 NaT."""
    ref = str(ref).upper().strip()
    if not ref.startswith("END OF"):
        return pd.NaT
    for k, m in _MONTHS.items():
        if k in ref:
            try:
                return pd.Timestamp(int(year), m, 1)
            except Exception:
                return pd.NaT
    return pd.NaT


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_year(api_key: str, params: dict, year: int, label: str) -> list[dict] | None:
    """해당 연도 레코드 리스트. 오류(네트워크·HTTP·파싱·NASS error)면 None, 무자료면 []."""
    q = dict(params)
    q.update({"key": api_key, "year": str(year), "format": "JSON"})
    for attempt in range(RETRIES):
        try:
            r = requests.get(BASE_URL, params=q, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException as e:
            if attempt == RETRIES - 1:
                print(f"   └ [예외] {label} {year}: 연결 실패 ({type(e).__name__})")
                return None
            time.sleep(1.5)
            continue
        if r.status_code != 200:
            snippet = r.text[:160].replace("\n", " ")
            print(f"   └ [에러] HTTP {r.status_code} ({label} {year}): {snippet}")
            return None
        try:
            payload = r.json()
        except ValueError:
            print(f"   └ [에러] JSON 파싱 실패 ({label} {year})")
            return None
        if isinstance(payload, dict) and "data" in payload:
            return [d for d in payload["data"] if isinstance(d, dict)]
        # 오류 응답은 {"error":[...]} 형태 (잘못된 필터 등)
        msg = str(payload.get("error") if isinstance(payload, dict) else payload)[:160]
        print(f"   └ [에러] NASS 응답 오류 ({label} {year}): {msg}")
        return None
    return None


def _records_to_rows(recs: list[dict], query: dict, seen_short_desc: set[str]) -> list[dict]:
    """원본 레코드 → long rows (query['series'] 에 정의된 short_desc 만, NATIONAL·TOTAL 만)."""
    rows: list[dict] = []
    for r in recs:
        sd = str(r.get("short_desc", "")).strip()
        seen_short_desc.add(sd)
        spec = query["series"].get(sd)
        if spec is None:
            continue
        if str(r.get("agg_level_desc", "")).strip().upper() != "NATIONAL":
            continue
        if str(r.get("domain_desc", "")).strip().upper() != "TOTAL":
            continue
        value = _parse_value(r.get("Value"))
        if value is None:
            continue
        if query["date_mode"] == "week_ending":
            dt = pd.to_datetime(r.get("week_ending"), errors="coerce")
        else:
            dt = _to_month_start(r.get("year"), r.get("reference_period_desc", ""))
        if pd.isna(dt):
            continue
        rows.append({
            "date": dt.strftime("%Y-%m-%d"),
            "country": COUNTRY,
            "indicator_id": spec["indicator_id"],
            "indicator_name": spec["indicator_name"],
            "value": round(value * spec["scale"], 3),
            "unit": spec["unit"],
            "freq": spec["freq"],
            "source": SOURCE,
        })
    return rows


# --------------------------------------------------------------------------
# 누적 저장 (공통 raw — FRED·ECOS·KMA·MLA 와 공유)
# --------------------------------------------------------------------------
def _merge_and_save(new_rows: list[dict], save_path: Path, windows: dict[str, str]) -> int:
    """windows = {indicator_id: 재수집 시작일} — 해당 indicator 의 시작일 이후 기존 행은 이번 응답으로 교체.
    다른 소스(FRED·ECOS·KMA·MLA) 행은 건드리지 않는다."""
    df_new = pd.DataFrame(new_rows)
    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        old_dt = pd.to_datetime(df_old["date"], errors="coerce")
        drop = pd.Series(False, index=df_old.index)
        for iid, start in windows.items():
            drop |= (df_old["indicator_id"] == iid) & (old_dt >= pd.Timestamp(start))
        df_final = pd.concat([df_old[~drop], df_new], ignore_index=True)
    else:
        df_final = df_new

    df_final = df_final.drop_duplicates(subset=DUPLICATE_KEYS, keep="last")
    df_final["_sort_dt"] = pd.to_datetime(df_final["date"], errors="coerce")
    df_final = df_final.sort_values(
        by=["_sort_dt", "country", "indicator_id"]
    ).drop(columns=["_sort_dt"])

    save_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


def _load_existing(save_path: Path) -> pd.DataFrame:
    """파일이 없으면 빈 DF. 있는데 읽지 못하면 예외 (전체 재수집으로 덮어쓰는 사고 방지)."""
    if not save_path.exists():
        return pd.DataFrame()
    return pd.read_csv(save_path, low_memory=False)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_nass_supply(backfill_from: int | None = None) -> int:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)

    api_key = _get_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 NASS_API_KEY 가 비어 있습니다.\n"
            "         발급(무료): https://quickstats.nass.usda.gov/api → .env 에 NASS_API_KEY=... 입력"
        )
        return 0

    try:
        df_existing = _load_existing(save_path)
    except Exception as e:
        print(f"[중단] 기존 raw 를 읽을 수 없습니다 ({type(e).__name__}): {save_path}")
        return 1

    this_year = date.today().year
    if backfill_from is not None:
        start_year = backfill_from
        mode = f"백필 {start_year}~{this_year}"
    else:
        start_year = this_year - (REFETCH_YEARS - 1)
        mode = f"증분 (올해·작년 재수집 {start_year}~{this_year})"
    years = list(range(start_year, this_year + 1))
    window_start = f"{start_year}-01-01"
    print(f"[NASS] {mode} — 조회 {len(NASS_QUERIES)}종 × {len(years)}개 연도")

    for iid in ALL_INDICATOR_IDS:
        last = _read_last_date(df_existing, iid)
        print(f"   · {iid}: 기존 마지막 {last if last else '없음'}")

    new_rows: list[dict] = []
    windows: dict[str, str] = {}
    errors: list[str] = []
    for query in NASS_QUERIES:
        label = query["label"]
        ids = [s["indicator_id"] for s in query["series"].values()]
        print(f"[수집] {label} → {ids}")
        q_rows: list[dict] = []
        seen: set[str] = set()
        failed = False
        for y in years:
            recs = _fetch_year(api_key, query["params"], y, label)
            time.sleep(SLEEP_BETWEEN_CALLS)
            if recs is None:
                failed = True
                break
            rows = _records_to_rows(recs, query, seen)
            print(f"   └ {y}: 원본 {len(recs)}행 → 채택 {len(rows)}건")
            q_rows.extend(rows)
        # 응답에 등장한 short_desc 목록 (시리즈 선택 근거 확인용)
        if seen:
            print(f"   └ 응답 short_desc 종류 {len(seen)}개:")
            for sd in sorted(seen):
                mark = "*" if sd in query["series"] else " "
                print(f"      {mark} {sd}")
        if failed:
            # 한 연도라도 실패하면 부분 연도로 기존 구간을 지우지 않도록 이 조회의 행은 버린다
            errors.extend(ids)
            print(f"   └ [오류] {label}: 일부 연도 실패 → 이번 응답 폐기, 기존 값 유지")
            continue
        if not q_rows:
            print(f"   └ 신규 관측치 없음 ({label})")
            continue
        new_rows.extend(q_rows)
        for iid in ids:
            if any(r["indicator_id"] == iid for r in q_rows):
                windows[iid] = window_start

    if new_rows:
        total = _merge_and_save(new_rows, save_path, windows)
        print(f"[완료] NASS {len(new_rows)}건 반영({window_start} 이후 구간 교체) — raw 누적 총 {total}건 ({save_path})")
        df_now = pd.DataFrame(new_rows)
        for iid, g in df_now.groupby("indicator_id"):
            g = g.sort_values("date")
            print(f"   · {iid}: {g['date'].min()} ~ {g['date'].max()} ({len(g)}건), "
                  f"최신 {g['value'].iloc[-1]:,.3f} {g['unit'].iloc[-1]}")
    else:
        print("[안내] NASS 신규 데이터가 없습니다.")

    if errors:
        print(f"[오류] NASS 수집 실패 {len(errors)}종 (기존 값 유지): {errors}")
        return 1
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="USDA NASS 미국 소고기 공급 지표 수집 (냉동 재고·주간 도축·주간 생산)")
    p.add_argument("--backfill-from", type=int, default=None, metavar="YYYY",
                   help=f"최초 백필 시작 연도 (예: 2005). 생략 시 올해·작년만 재수집. {MIN_BACKFILL_YEAR} 이상")
    args = p.parse_args(argv)
    if args.backfill_from is not None and not (MIN_BACKFILL_YEAR <= args.backfill_from <= date.today().year):
        p.error(f"--backfill-from 은 {MIN_BACKFILL_YEAR}~{date.today().year} 사이여야 합니다")
    return args


if __name__ == "__main__":
    _args = _parse_args()
    sys.exit(collect_nass_supply(backfill_from=_args.backfill_from))
