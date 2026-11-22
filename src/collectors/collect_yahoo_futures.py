"""
[파일 정의서]
- 파일명: collect_yahoo_futures.py
- 역할: 수집
- 대상: 미국 선물 시장가 — 생우(LE=F)·비육우(GF=F)·옥수수(ZC=F) 근월물 연속 (유일한 forward-looking 시장가)
- 데이터 소스: Yahoo Finance chart API (인증키 불필요)
    https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1=..&period2=..&interval=1d
- 수집/가공 주기: 일단위 — 종목(indicator_id)별 기존 raw CSV max(date) 이후 증분 (최근 14일 재수집)
- 주요 기능:
    1. 지표 정의는 config/indicators.csv 의 source=YAHOO 행 (indicator_registry.indicators_for("YAHOO"))
    2. 일별 종가(close)를 long format 으로 공통 거시 raw CSV(FRED·ECOS·KMA·MLA 와 공유)에 병합
       → preprocess_macro 가 일별 확장·ma30·yoy 를 만들고, 대시보드·지표 스크리닝에 자동 포함
    3. 최초 실행 시 2005-01-01 부터 백필(USDA 프라이멀 이력과 기간 일치), 이후 증분
    4. 오류 처리 (다른 macro 수집기와 동일)
       - 네트워크 예외 / HTTP 200 이외 / JSON 파싱 실패 / 응답에 error → 오류 집계, 받은 만큼 저장 후 exit 1
       - 신규 관측치 0건(휴장) → 정상(exit 0)
       - 기존 raw CSV 를 읽지 못하면 처음부터 재수집하지 않고 중단(exit 1)
- 주의: Yahoo 비공식 API — User-Agent 헤더 필요, 과도한 호출 시 429. 종목당 1~2회 호출이라 부담 없음.
      단위: LE/GF = US cents/lb, ZC = US cents/bushel (meta.currency 'USX' = 센트).

산출 컬럼(long format) — data/0_raw/macro_indicators_raw.csv:
    date, country, indicator_id, indicator_name, value, unit, freq, source   (country='US', source='YAHOO', freq='D')
"""
from __future__ import annotations

import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MACRO_RAW_CSV, ensure_dirs  # noqa: E402
from utils.indicator_registry import indicators_for  # noqa: E402
from utils.io_safe import atomic_to_csv  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) beef-price-model/1.0"}
INITIAL_START = date(2005, 1, 1)
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_CALLS = 1.0
REFETCH_DAYS = 14
COUNTRY = "US"
SOURCE = "YAHOO"
DUPLICATE_KEYS = ["date", "country", "indicator_id"]

YAHOO_INDICATORS = indicators_for("YAHOO")


def _read_last_date(df_existing: pd.DataFrame, indicator_id: str) -> date | None:
    if df_existing.empty:
        return None
    sub = df_existing.loc[df_existing["indicator_id"] == indicator_id, "date"]
    parsed = pd.to_datetime(sub, errors="coerce").dropna()
    return parsed.max().date() if not parsed.empty else None


def _fetch(symbol: str, start: date, end: date) -> pd.Series | None:
    """[start, end] 일별 종가 Series(index=date). 오류면 None, 무자료면 빈 Series."""
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp()) + 86400
    params = {"period1": p1, "period2": p2, "interval": "1d", "events": "history"}
    for attempt in range(3):
        try:
            resp = requests.get(BASE_URL.format(symbol=symbol), params=params, headers=HEADERS,
                                timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException as e:
            print(f"   └ [예외] {symbol}: 연결 실패 ({type(e).__name__}) — 재시도 {attempt + 1}/3")
            time.sleep(3 + 3 * attempt)
            continue
        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            print(f"   └ [대기] {symbol}: HTTP {resp.status_code} — 재시도 {attempt + 1}/3")
            time.sleep(5 + 5 * attempt)
            continue
        if resp.status_code != 200:
            print(f"   └ [에러] {symbol}: HTTP {resp.status_code} {resp.text[:120]!r}")
            return None
        try:
            payload = resp.json()
        except ValueError:
            print(f"   └ [에러] {symbol}: JSON 파싱 실패")
            return None
        chart = payload.get("chart") or {}
        if chart.get("error"):
            print(f"   └ [에러] {symbol}: {chart['error']}")
            return None
        result = (chart.get("result") or [None])[0]
        if not result:
            return pd.Series(dtype=float)
        ts = result.get("timestamp") or []
        closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
        if not ts or not closes:
            return pd.Series(dtype=float)
        idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert("America/Chicago").date
        s = pd.Series(pd.to_numeric(pd.Series(closes), errors="coerce").values, index=pd.Index(idx))
        s = s.dropna()
        s = s[(s > 0)]
        return s[~s.index.duplicated(keep="last")].sort_index()
    return None


def _merge_and_save(new_rows: list[dict], save_path: Path, windows: dict[str, str]) -> int:
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
    df_final = df_final.sort_values(by=["_sort_dt", "country", "indicator_id"]).drop(columns=["_sort_dt"])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


def collect_yahoo_futures_increment(backfill_from: date | None = None) -> int:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)
    if save_path.exists():
        try:
            df_existing = pd.read_csv(save_path, low_memory=False)
        except Exception as e:
            print(f"[중단] 기존 raw 를 읽을 수 없습니다 ({type(e).__name__}): {save_path}")
            return 1
    else:
        df_existing = pd.DataFrame()
    if not YAHOO_INDICATORS:
        print("[건너뜀] config/indicators.csv 에 source=YAHOO 지표가 없습니다.")
        return 0

    end = date.today()
    new_rows: list[dict] = []
    windows: dict[str, str] = {}
    errors: list[str] = []
    for ind in YAHOO_INDICATORS:
        iid, sym = ind["indicator_id"], ind["symbol"]
        last = _read_last_date(df_existing, iid)
        if backfill_from is not None:
            start = backfill_from
            print(f"[백필] {iid} ({sym}) — {start} 부터 전체 재수집")
        elif last is None:
            start = INITIAL_START
            print(f"[수집] {iid} ({sym}) — 기존 없음 → {start} 부터 전체")
        else:
            start = last - timedelta(days=REFETCH_DAYS)
            print(f"[수집] {iid} ({sym}) — 마지막 {last} → {start} 부터 재수집·증분")
        s = _fetch(sym, start, end)
        time.sleep(SLEEP_BETWEEN_CALLS)
        if s is None:
            errors.append(iid)
            continue
        print(f"   └ 수신 {len(s)}건")
        for d, v in s.items():
            new_rows.append({"date": d.isoformat(), "country": COUNTRY, "indicator_id": iid,
                             "indicator_name": ind["indicator_name"], "value": round(float(v), 4),
                             "unit": ind["unit"], "freq": "D", "source": SOURCE})
        if len(s):
            windows[iid] = start.isoformat()

    if new_rows:
        total = _merge_and_save(new_rows, save_path, windows)
        print(f"[완료] YAHOO {len(new_rows)}건 반영(최근 구간 교체) — raw 누적 총 {total}건 ({save_path})")
    else:
        print("[안내] YAHOO 신규 데이터가 없습니다.")
    if errors:
        print(f"[오류] YAHOO 수집 실패 {len(errors)}종 (기존 값 유지): {errors}")
        return 1
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Yahoo Finance 선물 일별 종가 수집")
    ap.add_argument("--backfill-from", help="YYYY-MM-DD — 이 날짜부터 전부 다시 받아 교체")
    a = ap.parse_args()
    sys.exit(collect_yahoo_futures_increment(date.fromisoformat(a.backfill_from) if a.backfill_from else None))
