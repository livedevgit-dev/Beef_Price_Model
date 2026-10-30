"""
[파일 정의서]
- 파일명: collect_mla_cattle.py
- 역할: 수집
- 대상: 호주 생우(산지 소) 가격 지표 — 호주산 수입 소고기 원가의 산지 축
- 데이터 소스: MLA(Meat & Livestock Australia) Statistics API (인증키 불필요)
    https://api-mlastatistics.mla.com.au/report/5?indicatorID={id}&fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&page=N
    (지표 목록: https://api-mlastatistics.mla.com.au/indicator , 이용약관: MLA Market Report and Information Terms of Use)
- 수집/가공 주기: 일단위 — indicator_id별 기존 raw CSV max(date) 이후 증분 수집
- 주요 기능:
    1. MLA 지표 2종을 long format 으로 수집하여 공통 거시 raw CSV(FRED·ECOS·KMA 와 공유)에 병합
         au_eyci        = indicatorID 0  Eastern Young Cattle Indicator (AU c/kg cwt) — 호주 소 가격 대표 지표
         au_heavy_steer = indicatorID 4  National Heavy Steer Indicator (AU c/kg lwt) — 수출용 비육 거세우
    2. 최초 실행 시 2019-01-01 부터 백필, 이후 증분
       - API 는 1페이지 100행 + page 파라미터 방식이고 뒤쪽 페이지일수록 느려(28페이지 ≈ 수 분)
         90일 단위 구간으로 나눠 요청한다(구간당 1페이지).
       - toDate 는 오늘 이전이어야 함("Please provide date range before today!") → 어제까지 요청
    3. 비거래일 제거: API 는 주말·휴장일에도 직전 거래일 값(지표값·두수 동일)을 채워 돌려준다.
       직전 행과 지표값·head_count 가 모두 같은 행은 이월값으로 보고 저장하지 않는다
       (가짜 관측치 방지 — 전처리에서 짧은 결측만 ffill).
    4. 자가 치유 증분: 최근 14일을 매번 다시 받아 해당 구간 행을 교체 (소급 정정 반영)
    5. 오류 처리 (다른 macro 수집기와 동일)
       - 네트워크 예외 / HTTP 200 이외 / JSON 파싱 실패 / 오류 메시지 응답 → 오류로 집계, 받은 만큼 저장 후 exit 1
       - 신규 관측치 0건(휴장·미발표) → 정상(exit 0)
       - 기존 raw CSV 를 읽지 못하면 2019년부터 재수집하지 않고 중단(exit 1)

산출 컬럼(long format) — data/0_raw/macro_indicators_raw.csv:
    date, country, indicator_id, indicator_name, value, unit, freq, source
    - country = 'AU' (호주 산지 가격), source = 'MLA', freq = 'D' (거래일만)
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MACRO_RAW_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# 사내망 SSL 검사(중간 프록시)로 인한 인증서 오류 대응 (다른 수집기와 동일 패턴)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
BASE_URL = "https://api-mlastatistics.mla.com.au/report/5"
INITIAL_START = date(2019, 1, 1)          # 다른 데이터셋과 정합
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_CALLS = 0.3
CHUNK_DAYS = 90                           # 1회 요청 구간 (100행/페이지 이내)
MAX_PAGES = 10                            # 구간 내 페이지 반복 상한 (무한루프 방지)
REFETCH_DAYS = 14                         # 증분 시 재수집 일수
CONTEXT_DAYS = 7                          # 이월값 판정용으로 구간 앞에 더 받는 일수

COUNTRY = "AU"
SOURCE = "MLA"

DUPLICATE_KEYS = ["date", "country", "indicator_id"]

MLA_INDICATORS = [
    {
        "indicator_id": "au_eyci",
        "mla_id": 0,
        "indicator_name": "MLA Eastern Young Cattle Indicator (EYCI, 호주 소 가격 대표)",
        "unit": "AU c/kg cwt",
    },
    {
        "indicator_id": "au_heavy_steer",
        "mla_id": 4,
        "indicator_name": "MLA National Heavy Steer Indicator (수출용 비육 거세우)",
        "unit": "AU c/kg lwt",
    },
]


# --------------------------------------------------------------------------
# 유틸
# --------------------------------------------------------------------------
def _read_last_date(df_existing: pd.DataFrame, indicator_id: str) -> date | None:
    if df_existing.empty:
        return None
    sub = df_existing.loc[df_existing["indicator_id"] == indicator_id, "date"]
    if sub.empty:
        return None
    parsed = pd.to_datetime(sub, errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.max().date()


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_chunk(mla_id: int, start: date, end: date, label: str) -> list[dict] | None:
    """[start, end] 구간 원본 행 리스트. 오류면 None, 무자료면 []."""
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        params = {
            "indicatorID": mla_id,
            "fromDate": start.strftime("%Y-%m-%d"),
            "toDate": end.strftime("%Y-%m-%d"),
            "page": page,
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException as e:
            print(f"   └ [예외] {label}: 연결 실패 ({type(e).__name__})")
            return None
        if resp.status_code != 200:
            snippet = resp.text[:160].replace("\n", " ")
            print(f"   └ [에러] HTTP {resp.status_code} ({label}): {snippet}")
            return None
        try:
            payload = resp.json()
        except ValueError:
            print(f"   └ [에러] JSON 파싱 실패 ({label})")
            return None
        if not isinstance(payload, dict):
            print(f"   └ [에러] 예상치 못한 응답 형식 ({label})")
            return None
        if "data" not in payload:
            # 오류 응답은 {"Message": "..."} 형태 (파라미터 오류 등)
            msg = str(payload.get("Message") or payload.get("message") or payload)[:160]
            print(f"   └ [에러] MLA 응답 오류 ({label}): {msg}")
            return None
        data = payload.get("data") or []
        out.extend(d for d in data if isinstance(d, dict))
        try:
            total = int(payload.get("total number rows", len(out)) or 0)
        except (TypeError, ValueError):
            total = len(out)
        if not data or len(out) >= total:
            break
        time.sleep(SLEEP_BETWEEN_CALLS)
    return out


def _fetch_indicator(indicator: dict, start: date, end: date) -> list[dict] | None:
    """long row 리스트 반환 (start 이후, 이월값 제거). 오류면 None."""
    fetch_start = start - timedelta(days=CONTEXT_DAYS)
    raw: list[dict] = []
    cur = fetch_start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        got = _fetch_chunk(indicator["mla_id"], cur, chunk_end, indicator["indicator_id"])
        if got is None:
            return None
        raw.extend(got)
        cur = chunk_end + timedelta(days=1)
        time.sleep(SLEEP_BETWEEN_CALLS)

    if not raw:
        return []
    df = pd.DataFrame(raw)
    if "calendar_date" not in df.columns or "indicator_value" not in df.columns:
        print(f"   └ [에러] 응답 컬럼 누락 ({indicator['indicator_id']}): {list(df.columns)[:8]}")
        return None
    df["date"] = pd.to_datetime(df["calendar_date"], errors="coerce")
    df["value"] = pd.to_numeric(df["indicator_value"], errors="coerce")
    df["head_count"] = pd.to_numeric(df.get("head_count"), errors="coerce")
    df = df.dropna(subset=["date", "value"])
    df = df[df["value"] > 0]
    df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    # 주말·휴장일 이월값(직전 행과 지표값·두수 동일) 제거
    carried = (df["value"].diff() == 0) & (df["head_count"].diff().fillna(1) == 0)
    df = df[~carried]
    df = df[df["date"] >= pd.Timestamp(start)]

    return [
        {
            "date": d.strftime("%Y-%m-%d"),
            "country": COUNTRY,
            "indicator_id": indicator["indicator_id"],
            "indicator_name": indicator["indicator_name"],
            "value": round(float(v), 4),
            "unit": indicator["unit"],
            "freq": "D",
            "source": SOURCE,
        }
        for d, v in zip(df["date"], df["value"])
    ]


# --------------------------------------------------------------------------
# 누적 저장 (공통 raw — FRED·ECOS·KMA 와 공유)
# --------------------------------------------------------------------------
def _merge_and_save(new_rows: list[dict], save_path: Path, windows: dict[str, str]) -> int:
    """windows = {indicator_id: 재수집 시작일} — 해당 indicator 의 시작일 이후 기존 행은 이번 응답으로 교체.
    다른 소스(FRED·ECOS·KMA) 행은 건드리지 않는다."""
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
    """파일이 없으면 빈 DF. 있는데 읽지 못하면 예외 (2019년부터 재수집해 덮어쓰는 사고 방지)."""
    if not save_path.exists():
        return pd.DataFrame()
    return pd.read_csv(save_path, low_memory=False)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_mla_cattle_increment() -> int:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)

    try:
        df_existing = _load_existing(save_path)
    except Exception as e:
        print(f"[중단] 기존 raw 를 읽을 수 없습니다 ({type(e).__name__}): {save_path}")
        return 1

    end = date.today() - timedelta(days=1)   # MLA API 는 오늘 이전까지만 허용
    new_rows: list[dict] = []
    windows: dict[str, str] = {}
    errors: list[str] = []
    for indicator in MLA_INDICATORS:
        last_date = _read_last_date(df_existing, indicator["indicator_id"])
        if last_date is None:
            start = INITIAL_START
            print(f"[수집] {indicator['indicator_id']} (MLA {indicator['mla_id']}) "
                  f"— 기존 없음 → {start} 부터 전체")
        else:
            start = last_date - timedelta(days=REFETCH_DAYS)
            print(f"[수집] {indicator['indicator_id']} (MLA {indicator['mla_id']}) "
                  f"— 마지막 {last_date} → {start} 부터 재수집·증분")
        if start > end:
            print("   └ 이미 최신")
            continue

        rows = _fetch_indicator(indicator, start, end)
        if rows is None:
            errors.append(indicator["indicator_id"])
        else:
            print(f"   └ 수신 {len(rows)}건 (이월값 제외 거래일 기준)")
            new_rows.extend(rows)
            if rows:  # 빈 응답으로 기존 구간을 지우지 않도록, 받은 게 있을 때만 교체
                windows[indicator["indicator_id"]] = start.strftime("%Y-%m-%d")

    if new_rows:
        total = _merge_and_save(new_rows, save_path, windows)
        print(f"[완료] MLA {len(new_rows)}건 반영(최근 구간 교체) — raw 누적 총 {total}건 ({save_path})")
    else:
        print("[안내] MLA 신규 데이터가 없습니다.")

    if errors:
        print(f"[오류] MLA 수집 실패 {len(errors)}종 (기존 값 유지): {errors}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(collect_mla_cattle_increment())
