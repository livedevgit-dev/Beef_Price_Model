"""
[파일 정의서]
- 파일명: collect_macro_kma.py
- 역할: 수집
- 대상: 국내 기후 지표 (평균기온·최고기온·일강수량) — 축산물 소비/공급 계절성 외생변수
- 데이터 소스: 기상청 API 허브 — 지상관측(ASOS) 일자료
    https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php?tm1=YYYYMMDD&tm2=YYYYMMDD&stn=...&authKey=...
    키 발급: https://apihub.kma.go.kr (회원가입 → 종관기상관측 일자료 API 활용신청)
- 수집/가공 주기: 일단위 — indicator_id별 기존 raw CSV max(date) 이후만 증분 수집
- 주요 기능:
    1. .env(KMA_API_KEY) = API 허브 authKey 로딩. 없으면 graceful skip
    2. 전국 대표 관측소 일자료를 받아 날짜별 평균 → 전국 대표값
    3. 응답은 고정폭 텍스트(#=주석). 콤마 분리 파싱. 결측(-9/-99)은 제외.
    4. 공통 raw CSV(FRED/ECOS 와 공유)에 long format 병합

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
    """단일 일자(tm) 전 지점(stn=0) 조회. 대표 관측소 row 만 반환."""
    params = {"tm": tm.strftime("%Y%m%d"), "stn": "0", "authKey": api_key}
    for attempt in range(3):
        try:
            r = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException:
            time.sleep(2)
            continue
        if r.status_code != 200:
            return []
        text = r.text
        if "활용신청" in text or '"status"' in text[:120]:
            print(f"   └ [에러] 인증/활용신청 문제")
            return []
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
    return []


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


def _merge_and_save(rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(rows)
    if df_new.empty:
        return _count(save_path)
    if save_path.exists():
        df = pd.concat([pd.read_csv(save_path, low_memory=False), df_new], ignore_index=True)
    else:
        df = df_new
    sub = [c for c in DUPLICATE_KEYS if c in df.columns]
    if sub:
        df = df.drop_duplicates(subset=sub, keep="last")
    df["_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["_dt", "country", "indicator_id"]).drop(columns=["_dt"])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(str(save_path), index=False, encoding="utf-8-sig")
    return len(df)


def _count(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        return sum(1 for _ in open(p, "r", encoding="utf-8-sig")) - 1
    except OSError:
        return 0


def _load(p: Path) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, low_memory=False)
    except Exception:
        return pd.DataFrame()


def collect_macro_kma_increment() -> None:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)
    api_key = _get_key()
    if api_key is None:
        print("[건너뜀] .env 의 KMA_API_KEY(API허브 authKey) 가 비어 있습니다.\n"
              "         발급: https://apihub.kma.go.kr (종관기상관측 일자료 활용신청)")
        return

    df_existing = _load(save_path)
    today = date.today()
    last_dates = [d for d in (_read_last_date(df_existing, i["indicator_id"]) for i in INDICATORS) if d]
    start = (min(last_dates) + timedelta(days=1)) if last_dates else INITIAL_START
    if start > today:
        print("[성공] 이미 최신 상태입니다.")
        return

    # 일 단위 루프 (kma_sfcdd.php 는 단일 tm 만 지원). 365일마다 중간 저장(체크포인트).
    all_days = []
    d = start
    while d <= today:
        all_days.append(d)
        d += timedelta(days=1)
    print(f"[안내] {start} ~ {today} ({len(all_days)}일) 일단위 수집 (stn=0, 365일마다 저장)")

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
    for i, day in enumerate(all_days, 1):
        for rec in _fetch_day(api_key, day):
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

    if bucket:
        done = _merge_and_save(_bucket_to_rows(bucket), save_path)
    print(f"[완료] KMA 수집 완료 — raw 누적 {done if done else _count(save_path)}건 ({save_path})")


if __name__ == "__main__":
    collect_macro_kma_increment()
