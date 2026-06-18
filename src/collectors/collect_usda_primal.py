import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import USDA_PRIMAL_HISTORY_CSV, ensure_dirs

# [파일 정의서]
# - 파일명: collect_usda_primal.py
# - 역할: 수집
# - 대상: 수입육 거시 지표 (Composite Primal Values)
# - 데이터 소스: USDA AMS Datamart API (Slug 2453, Composite Primal Values 섹션)
# - 수집/가공 주기: 일단위 — 기존 CSV의 마지막 report_date 이후만 증분 수집
# - 주요 기능:
#   1. 최초 실행 시 2019-01-01부터 전체 수집
#   2. 이후 실행 시 마지막 수집일 + 1일 ~ 오늘 범위만 호출 (1년 단위 분할 요청)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/Composite%20Primal%20Values"
INITIAL_START = datetime(2019, 1, 1)
DUPLICATE_KEYS = ["report_date", "primal_desc"]


def _read_last_date(save_path: Path) -> datetime | None:
    if not save_path.exists():
        return None
    try:
        df = pd.read_csv(save_path, usecols=["report_date"], low_memory=False)
    except Exception:
        return None
    if df.empty:
        return None
    parsed = pd.to_datetime(df["report_date"], errors="coerce")
    parsed = parsed.dropna()
    if parsed.empty:
        return None
    return parsed.max().to_pydatetime()


def _generate_year_ranges(start: datetime, end: datetime) -> list[tuple[str, str]]:
    """1년(또는 잔여) 단위로 API 호출 범위를 잘라 반환."""
    ranges: list[tuple[str, str]] = []
    cursor = start
    while cursor <= end:
        year_end = datetime(cursor.year, 12, 31)
        chunk_end = min(year_end, end)
        ranges.append((cursor.strftime("%m/%d/%Y"), chunk_end.strftime("%m/%d/%Y")))
        cursor = chunk_end + timedelta(days=1)
    return ranges


def _fetch_range(start_str: str, end_str: str) -> list[dict]:
    query_url = f"{BASE_URL}?q=report_date={start_str}:{end_str}"
    try:
        response = requests.get(query_url, timeout=30, verify=False)
    except Exception as e:
        print(f"   └ [예외] {e}")
        return []
    if response.status_code != 200:
        print(f"   └ [에러] 상태 코드 {response.status_code}")
        return []
    payload = response.json()
    return payload.get("results", []) if isinstance(payload, dict) else []


def _merge_and_save(new_rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(new_rows)
    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    if subset:
        df_final = df_final.drop_duplicates(subset=subset, keep="last")
    else:
        df_final = df_final.drop_duplicates()

    df_final["_sort_dt"] = pd.to_datetime(df_final["report_date"], errors="coerce")
    df_final = df_final.sort_values(by=["_sort_dt", "primal_desc"]).drop(columns=["_sort_dt"])
    df_final.to_csv(str(save_path), index=False, encoding="utf-8-sig")
    return len(df_final)


def collect_primal_increment() -> None:
    ensure_dirs()
    save_path = Path(USDA_PRIMAL_HISTORY_CSV)

    last_date = _read_last_date(save_path)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if last_date is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start.date()}부터 전체 수집")
    else:
        start = last_date + timedelta(days=1)
        print(f"[시스템] 기존 데이터 마지막일: {last_date.date()} → {start.date()}부터 증분 수집")

    if start > today:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return

    ranges = _generate_year_ranges(start, today)
    print(f"[안내] 요청 범위 {len(ranges)}건 ({start.date()} ~ {today.date()})")

    new_rows: list[dict] = []
    for i, (s, e) in enumerate(ranges, 1):
        print(f" - [{i}/{len(ranges)}] {s} ~ {e}")
        rows = _fetch_range(s, e)
        if rows:
            print(f"   └ 수집: {len(rows)}건")
            new_rows.extend(rows)
        else:
            print("   └ 신규 데이터 없음")
        time.sleep(1)

    if not new_rows:
        print("[안내] API에서 신규 데이터가 반환되지 않았습니다.")
        return

    total = _merge_and_save(new_rows, save_path)
    print(f"[완료] 신규 {len(new_rows)}건 병합 — 누적 총 {total}건 ({save_path})")


if __name__ == "__main__":
    collect_primal_increment()
