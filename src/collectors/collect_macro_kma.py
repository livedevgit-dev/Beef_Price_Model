"""
[파일 정의서]
- 파일명: collect_macro_kma.py
- 역할: 수집
- 대상: 국내 기후 지표 (평균기온·최고기온·일강수량) — 축산물 소비/공급 계절성 외생변수
- 데이터 소스: 기상청 API 허브 — 지상관측(ASOS) 일자료
    https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php?tm1=YYYYMMDD&tm2=YYYYMMDD&stn=...&authKey=...
    키 발급: https://apihub.kma.go.kr (회원가입 → 종관기상관측 일자료 API 활용신청)
- 수집/가공 주기: 일단위 — 기존 raw 의 마지막 날짜 이후 + 최근 7일 재수집 + 과거 누락일 재시도, 어제까지만
- 주요 기능:
    1. .env(KMA_API_KEY) = API 허브 authKey 로딩. 없으면 graceful skip
    2. 전국 대표 관측소 일자료를 받아 날짜별 평균 → 전국 대표값
    3. 응답은 고정폭 텍스트(#=주석). 콤마 분리 파싱. 결측(-9/-99)은 제외.
    4. 공통 raw CSV(FRED/ECOS 와 공유)에 long format 병합
    5. (2026-10 정합성 수정)
       - 수집 종료일 = 어제. 오늘 자료는 관측 중인 부분값이라 저장하지 않으며, 이미 저장된 오늘 이후 KMA 행은 삭제
       - 최근 7일은 매번 다시 받아 교체 (지연 확정·정정 반영)
       - 2019-01-01 ~ 어제 중 raw 에 없는 날짜(예: 2023-11-08~16 HTTP 오류 공백)는 매 실행 재시도
       - 네트워크 예외(재시도 초과) / HTTP 200 이외 / 인증 오류 = 오류 집계 → 받은 만큼 저장 후 exit 1
         (200 응답인데 해당일 자료가 없는 것은 정상)
       - 기존 raw 를 읽지 못하면 2019년부터 재수집하지 않고 중단(exit 1)

응답 컬럼(0-based 인덱스): TM=0, STN=1, TA_AVG=10, TA_MAX=11, TA_MIN=13, RN_DAY=38
산출 지표(long): kr_temp_avg(평균기온°C), kr_temp_max(최고기온°C), kr_precip(일강수량mm)
    country='KR', source='KMA', freq='D'
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
from utils.io_safe import atomic_to_csv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

BASE_URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php"
INITIAL_START = date(2019, 1, 1)
REQUEST_TIMEOUT = 90        # 허브 응답이 느릴 수 있음
SLEEP = 0.4

COUNTRY = "KR"
SOURCE = "KMA"
DUPLICATE_KEYS = ["date", "country", "indicator_id"]

# 전국 대표 관측소 (지점번호: 이름)
STATIONS = {108: "서울", 159: "부산", 143: "대구", 156: "광주", 133: "대전"}

# 응답 컬럼 인덱스(0-based) → indicator
COL = {"TA_AVG": 10, "TA_MAX": 11, "TA_MIN": 13, "RN_DAY": 38}
INDICATORS = [
    {"indicator_id": "kr_temp_avg", "col": "TA_AVG", "name": "평균기온(전국대표)", "unit": "°C"},
    {"indicator_id": "kr_temp_max", "col": "TA_MAX", "name": "최고기온(전국대표)", "unit": "°C"},
    {"indicator_id": "kr_precip", "col": "RN_DAY", "name": "일강수량(전국대표)", "unit": "mm"},
]
MISSING = {"-9", "-9.0", "-99", "-99.0", "", "-"}
REFETCH_DAYS = 7            # 매 실행 재수집하는 최근 일수
MAX_CONSECUTIVE_ERRORS = 5  # 연속 오류 시 조기 중단 (인증 만료·장애 시 서버 부하 방지)


class FetchError(RuntimeError):
    pass


def _get_key() -> str | None:
    return os.getenv("KMA_API_KEY", "").strip() or None


def _read_last_date(df: pd.DataFrame, indicator_id: str) -> date | None:
    if df.empty:
        return None
    sub = df.loc[df["indicator_id"] == indicator_id, "date"]
    if sub.empty:
        return None
    parsed = pd.to_datetime(sub, errors="coerce").dropna()
    return parsed.max().date() if not parsed.empty else None


def _year_ranges(start: date, end: date) -> list[tuple[date, date]]:
    out, cur = [], start
    while cur <= end:
        ye = date(cur.year, 12, 31)
        out.append((cur, min(ye, end)))
        cur = min(ye, end) + timedelta(days=1)
    return out


def _fetch_day(api_key: str, tm: date) -> list[dict]:
    """단일 일자(tm) 전 지점(stn=0) 조회. 대표 관측소 row 만 반환.
    네트워크 예외(재시도 초과)·HTTP 200 이외·인증 오류는 FetchError."""
    params = {"tm": tm.strftime("%Y%m%d"), "stn": "0", "authKey": api_key}
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException as e:
            last_err = type(e).__name__
            time.sleep(2)
            continue
        if r.status_code != 200:
            raise FetchError(f"HTTP {r.status_code}")
        text = r.text
        if "활용신청" in text or '"status"' in text[:120]:
            raise FetchError("인증/활용신청 문제")
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) <= COL["RN_DAY"]:
                continue
            try:
                d = datetime.strptime(parts[0], "%Y%m%d").date()
                stn = int(parts[1])
            except ValueError:
                continue
            if stn in STATIONS:
                rows.append({"date": d, "stn": stn, "parts": parts})
        return rows
    raise FetchError(f"연결 실패({last_err})")


def _val(parts: list[str], col: str) -> float | None:
    idx = COL[col]
    if idx >= len(parts):
        return None
    v = parts[idx]
    if v in MISSING:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _merge_and_save(rows: list[dict], save_path: Path, purge_from: date | None = None) -> int:
    """purge_from 이 주어지면 그 날짜 이후의 KMA 행(관측 중 부분값)을 삭제한다."""
    df_new = pd.DataFrame(rows)
    if df_new.empty and purge_from is None:
        return _count(save_path)
    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        if purge_from is not None:
            stale = ((df_old["source"] == SOURCE)
                     & (pd.to_datetime(df_old["date"], errors="coerce") >= pd.Timestamp(purge_from)))
            if stale.any():
                print(f"   └ 관측 중(오늘 이후) KMA 부분값 {int(stale.sum())}행 삭제")
            df_old = df_old[~stale]
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    if df.empty:
        return 0
    sub = [c for c in DUPLICATE_KEYS if c in df.columns]
    if sub:
        df = df.drop_duplicates(subset=sub, keep="last")
    df["_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["_dt", "country", "indicator_id"]).drop(columns=["_dt"])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_to_csv(df, save_path, index=False, encoding="utf-8-sig")
    return len(df)


def _count(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        return sum(1 for _ in open(p, "r", encoding="utf-8-sig")) - 1
    except OSError:
        return 0


def _load(p: Path) -> pd.DataFrame:
    """파일이 없으면 빈 DF. 있는데 읽지 못하면 예외 (2019년부터 재수집해 덮어쓰는 사고 방지)."""
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, low_memory=False)


def _missing_days(df: pd.DataFrame, end: date) -> list[date]:
    """INITIAL_START ~ end 중 KMA 지표가 하나라도 빠진 날짜."""
    if df.empty:
        return []
    sub = df[df["indicator_id"].isin([i["indicator_id"] for i in INDICATORS])]
    have = pd.to_datetime(sub["date"], errors="coerce").dropna()
    if have.empty:
        return []
    counts = have.value_counts()
    full_days = set(counts[counts >= len(INDICATORS)].index.date)
    out, d = [], max(have.min().date(), INITIAL_START)
    while d <= end:
        if d not in full_days:
            out.append(d)
        d += timedelta(days=1)
    return out


def collect_macro_kma_increment() -> int:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)
    api_key = _get_key()
    if api_key is None:
        print("[건너뜀] .env 의 KMA_API_KEY(API허브 authKey) 가 비어 있습니다.\n"
              "         발급: https://apihub.kma.go.kr (종관기상관측 일자료 활용신청)")
        return 0

    try:
        df_existing = _load(save_path)
    except Exception as e:
        print(f"[중단] 기존 raw 를 읽을 수 없습니다 ({type(e).__name__}): {save_path}")
        return 1
    today = date.today()
    end = today - timedelta(days=1)   # 오늘 자료는 관측 중 부분값 → 어제까지만
    last_dates = [d for d in (_read_last_date(df_existing, i["indicator_id"]) for i in INDICATORS) if d]
    if last_dates:
        start = min(min(last_dates) + timedelta(days=1), end - timedelta(days=REFETCH_DAYS - 1))
    else:
        start = INITIAL_START

    # 수집 대상 = 과거 누락일(재시도) + start ~ 어제
    gap_days = sorted(d for d in _missing_days(df_existing, end) if d < start)
    days = set(gap_days)
    d = start
    while d <= end:
        days.add(d)
        d += timedelta(days=1)
    all_days = sorted(days)
    if gap_days:
        print(f"[안내] 과거 누락일 {len(gap_days)}일 재시도: {[x.isoformat() for x in gap_days[:20]]}")
    if not all_days:
        print("[성공] 이미 최신 상태입니다.")
        _merge_and_save([], save_path, purge_from=today)
        return 0

    # 일 단위 루프 (kma_sfcdd.php 는 단일 tm 만 지원). 365일마다 중간 저장(체크포인트).
    print(f"[안내] {start} ~ {end} (+누락 {len(gap_days)}일, 총 {len(all_days)}일) 일단위 수집 (stn=0, 365일마다 저장)")

    def _bucket_to_rows(bucket):
        rows = []
        for ds, inds in bucket.items():
            for ind in INDICATORS:
                vals = inds.get(ind["indicator_id"])
                if not vals:
                    continue
                rows.append({"date": ds, "country": COUNTRY, "indicator_id": ind["indicator_id"],
                             "indicator_name": ind["name"], "value": round(sum(vals)/len(vals), 2),
                             "unit": ind["unit"], "freq": "D", "source": SOURCE})
        return rows

    bucket: dict[str, dict[str, list[float]]] = {}
    done = 0
    errors: list[str] = []
    empty_days: list[str] = []
    consecutive = 0
    for i, day in enumerate(all_days, 1):
        try:
            recs = _fetch_day(api_key, day)
            consecutive = 0
        except FetchError as e:
            errors.append(f"{day} {e}")
            consecutive += 1
            if consecutive >= MAX_CONSECUTIVE_ERRORS:
                print(f"   └ [중단] 연속 {consecutive}회 오류 — 이번 실행 수집을 멈춥니다 ({e})")
                break
            time.sleep(SLEEP)
            continue
        if not recs:
            empty_days.append(day.isoformat())
        for rec in recs:
            ds = rec["date"].strftime("%Y-%m-%d")
            b = bucket.setdefault(ds, {})
            for ind in INDICATORS:
                val = _val(rec["parts"], ind["col"])
                if ind["col"] == "RN_DAY" and val is None:
                    val = 0.0
                if val is not None:
                    b.setdefault(ind["indicator_id"], []).append(val)
        time.sleep(SLEEP)
        if i % 365 == 0:
            done = _merge_and_save(_bucket_to_rows(bucket), save_path)
            bucket = {}
            print(f"   └ 진행 {i}/{len(all_days)}일, 누적 저장 {done}건")

    done = _merge_and_save(_bucket_to_rows(bucket), save_path, purge_from=today)
    if empty_days:
        print(f"   └ 자료 없음(정상 응답) {len(empty_days)}일: {empty_days[:10]}")
    print(f"[완료] KMA 수집 완료 — raw 누적 {done}건 ({save_path})")
    if errors:
        print(f"[오류] {len(errors)}일 수집 실패 — 다음 실행 때 누락일로 재시도: {errors[:5]}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(collect_macro_kma_increment())
