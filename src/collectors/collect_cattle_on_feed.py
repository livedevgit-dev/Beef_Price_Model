"""
[파일 정의서]
- 파일명: collect_cattle_on_feed.py
- 역할: 수집
- 대상: 미국 Cattle on Feed (사육두수) — 미국 소고기 공급의 4~6개월 선행 펀더멘털
- 데이터 소스: USDA NASS QuickStats API
    https://quickstats.nass.usda.gov/api/api_GET/?key=...&[filters]&format=JSON
    키 발급(무료): https://quickstats.nass.usda.gov/api  (이메일 등록)
- 수집/가공 주기: 월간(증분) — 매월 Cattle on Feed 보고서 발표
- 주요 기능:
    1. .env(NASS_API_KEY) 로딩. 키 없으면 즉시 graceful skip
    2. 전국(NATIONAL) 월별 ON FEED 시리즈 수집 (재고/배치/출하)
    3. long format 저장: data/0_raw/us_cattle_on_feed.csv

주의(할루시네이션 방지):
    - short_desc(시리즈명) 어휘가 NASS 통제어휘라, 우선 가장 확실한 'CATTLE, ON FEED - INVENTORY'
      로 조회하고, 응답 record 수/에러를 화면에 출력한다.
    - 첫 실제 실행 결과(상태·건수·short_desc 목록)를 확인해 시리즈 목록을 확정한다.
"""

from __future__ import annotations

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
from config import US_CATTLE_ON_FEED_CSV, ensure_dirs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

BASE_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
INITIAL_YEAR = 2019
REQUEST_TIMEOUT = 60

# 우선 수집할 ON FEED 시리즈(가장 확실한 것부터). 첫 실행 결과로 확정·확장.
SHORT_DESCS = [
    "CATTLE, ON FEED - INVENTORY",                          # 사육두수(공급 수준)
    "CATTLE, ON FEED - PLACEMENTS, MEASURED IN HEAD",       # 배치(4~6개월 선행 핵심)
    "CATTLE, ON FEED - SALES FOR SLAUGHTER, MEASURED IN HEAD",  # 도축출하
]

DUPLICATE_KEYS = ["date", "short_desc"]

# 월 매핑 (reference_period_desc: 'FIRST OF JAN' 등)
_MONTHS = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
           "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}


def _get_key() -> str | None:
    return os.getenv("NASS_API_KEY", "").strip() or None


def _fetch(api_key: str, short_desc: str) -> list[dict]:
    params = {
        "key": api_key,
        "source_desc": "SURVEY",
        "commodity_desc": "CATTLE",
        "short_desc": short_desc,
        "agg_level_desc": "NATIONAL",
        "year__GE": str(INITIAL_YEAR),
        "format": "JSON",
    }
    for attempt in range(3):
        try:
            r = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException as e:
            time.sleep(1.0)
            if attempt == 2:
                print(f"   └ [예외] '{short_desc}': 연결 실패 ({type(e).__name__})")
            continue
        if r.status_code != 200:
            # NASS 는 잘못된 필터/초과 시 JSON error 를 줌
            snippet = r.text[:160].replace("\n", " ")
            print(f"   └ [HTTP {r.status_code}] '{short_desc}': {snippet}")
            return []
        try:
            data = r.json()
        except ValueError:
            print(f"   └ [에러] JSON 파싱 실패 '{short_desc}'")
            return []
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        # 에러 형태: {"error":[...]}
        print(f"   └ [응답이상] '{short_desc}': keys={list(data)[:3] if isinstance(data, dict) else type(data)}")
        return []
    return []


def _to_date(year, ref: str):
    """year + reference_period_desc('FIRST OF JAN') → 해당 월 1일."""
    ref = str(ref).upper()
    for k, m in _MONTHS.items():
        if k in ref:
            try:
                return pd.Timestamp(int(year), m, 1)
            except Exception:
                return pd.NaT
    return pd.NaT


def _merge_and_save(rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(rows)
    if df_new.empty:
        return 0
    if save_path.exists():
        df = pd.concat([pd.read_csv(save_path, low_memory=False), df_new], ignore_index=True)
    else:
        df = df_new
    sub = [c for c in DUPLICATE_KEYS if c in df.columns]
    if sub:
        df = df.drop_duplicates(subset=sub, keep="last")
    df["_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values(["_dt", "short_desc"]).drop(columns=["_dt"])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(str(save_path), index=False, encoding="utf-8-sig")
    return len(df)


def collect_cattle_on_feed() -> None:
    ensure_dirs()
    save_path = Path(US_CATTLE_ON_FEED_CSV)
    api_key = _get_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 NASS_API_KEY 가 비어 있습니다.\n"
            "         발급(무료): https://quickstats.nass.usda.gov/api → .env 에 NASS_API_KEY=... 입력"
        )
        return

    rows: list[dict] = []
    for sd in SHORT_DESCS:
        recs = _fetch(api_key, sd)
        print(f"   └ '{sd}': {len(recs)}건")
        for r in recs:
            val = str(r.get("Value", "")).replace(",", "").strip()
            try:
                value = float(val)
            except ValueError:
                continue
            dt = _to_date(r.get("year"), r.get("reference_period_desc", ""))
            if pd.isna(dt):
                continue
            rows.append({
                "date": dt.strftime("%Y-%m-%d"),
                "short_desc": r.get("short_desc", sd),
                "value": value,
                "unit": r.get("unit_desc", ""),
                "reference_period": r.get("reference_period_desc", ""),
            })
        time.sleep(0.5)

    if not rows:
        print("[안내] 수집된 Cattle on Feed 데이터가 없습니다 (시리즈명/키 확인 필요 — 위 로그 참조).")
        return

    total = _merge_and_save(rows, save_path)
    print(f"[완료] Cattle on Feed 신규 {len(rows)}건 병합 — 누적 {total}건 ({save_path})")


if __name__ == "__main__":
    collect_cattle_on_feed()
