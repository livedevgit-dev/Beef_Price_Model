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
from utils.io_safe import atomic_to_csv

# [파일 정의서]
# - 파일명: collect_usda_primal.py
# - 역할: 수집
# - 대상: 수입육 거시 지표 (Composite Primal Values)
# - 데이터 소스: USDA AMS Datamart API (Slug 2453, Composite Primal Values 섹션)
# - 수집/가공 주기: 일단위 — 기존 CSV의 마지막 report_date 이후만 증분 수집
# - 주요 기능:
#   1. 최초 실행 시 2019-01-01부터 전체 수집
#   2. 이후 실행 시 (마지막 수집일 - 7일) ~ 오늘 범위를 호출 (1년 단위 분할 요청)
#      → 최근 약 5영업일은 매번 다시 받아 해당 report_date 행을 교체 (지연 게시·정정분 자가 치유)
#   3. 실패 처리 (2026-10 정합성 수정):
#      - 네트워크 예외 / HTTP 200 이외 / JSON 파싱 실패 = 오류 집계 → 받은 만큼 저장 후 exit 1
#      - 'No Results Found.'(공휴일·미게시) = 정상 → exit 0
#      - 기존 CSV 를 읽지 못하면 2019년부터 재수집하지 않고 중단(exit 1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/Composite%20Primal%20Values"
INITIAL_START = datetime(2019, 1, 1)
DUPLICATE_KEYS = ["report_date", "primal_desc"]
REFETCH_DAYS = 7   # 매 실행 재수집하는 최근 일수(달력일, 약 5영업일)


class ExistingFileError(RuntimeError):
    pass


def _read_last_date(save_path: Path) -> datetime | None:
    if not save_path.exists():
        return None
    try:
        df = pd.read_csv(save_path, usecols=["report_date"], low_memory=False)
    except Exception as e:
        raise ExistingFileError(f"기존 파일을 읽을 수 없습니다 ({type(e).__name__}: {e})")
    parsed = pd.to_datetime(df["report_date"], errors="coerce").dropna()
    if parsed.empty:
        raise ExistingFileError("기존 파일에 유효한 report_date 가 없습니다")
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


def _fetch_range(start_str: str, end_str: str) -> list[dict] | None:
    """결과 리스트 반환. 오류(네트워크·HTTP·파싱)면 None, 데이터 없음이면 []."""
    query_url = f"{BASE_URL}?q=report_date={start_str}:{end_str}"
    response = None
    for attempt in range(3):
        try:
            response = requests.get(query_url, timeout=60, verify=False)
            break
        except requests.RequestException as e:
            print(f"   └ [예외] 연결 실패 ({type(e).__name__}) — 재시도 {attempt + 1}/3")
            time.sleep(2 + attempt)
    if response is None:
        return None
    if response.status_code != 200:
        print(f"   └ [에러] 상태 코드 {response.status_code}")
        return None
    try:
        payload = response.json()
    except ValueError:
        print("   └ [에러] JSON 파싱 실패")
        return None
    if isinstance(payload, dict):
        return payload.get("results", []) or []
    if isinstance(payload, str) and "no results" in payload.lower():
        return []   # 공휴일·미게시 → 정상
    print(f"   └ [에러] 예상 밖 응답 ({type(payload).__name__})")
    return None


def _merge_and_save(new_rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(new_rows)
    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        # 새로 받은 report_date 는 기존 행을 통째로 교체 (정정·삭제분 반영)
        new_dates = set(pd.to_datetime(df_new["report_date"], errors="coerce").dropna())
        old_dt = pd.to_datetime(df_old["report_date"], errors="coerce")
        df_final = pd.concat([df_old[~old_dt.isin(new_dates)], df_new], ignore_index=True)
    else:
        df_final = df_new

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    if subset:
        df_final = df_final.drop_duplicates(subset=subset, keep="last")
    else:
        df_final = df_final.drop_duplicates()

    df_final["_sort_dt"] = pd.to_datetime(df_final["report_date"], errors="coerce")
    df_final = df_final.sort_values(by=["_sort_dt", "primal_desc"]).drop(columns=["_sort_dt"])
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


def collect_primal_increment() -> int:
    ensure_dirs()
    save_path = Path(USDA_PRIMAL_HISTORY_CSV)

    try:
        last_date = _read_last_date(save_path)
    except ExistingFileError as e:
        print(f"[중단] {e}: {save_path}")
        print("        2019년부터 재수집하지 않습니다. 파일을 확인/복구한 뒤 다시 실행하세요.")
        return 1
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if last_date is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start.date()}부터 전체 수집")
    else:
        start = last_date - timedelta(days=REFETCH_DAYS)
        print(f"[시스템] 기존 데이터 마지막일: {last_date.date()} → {start.date()}부터 증분 수집 (최근 {REFETCH_DAYS}일 재수집)")

    if start > today:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return 0

    ranges = _generate_year_ranges(start, today)
    print(f"[안내] 요청 범위 {len(ranges)}건 ({start.date()} ~ {today.date()})")

    new_rows: list[dict] = []
    errors = 0
    for i, (s, e) in enumerate(ranges, 1):
        print(f" - [{i}/{len(ranges)}] {s} ~ {e}")
        rows = _fetch_range(s, e)
        if rows is None:
            errors += 1
        elif rows:
            print(f"   └ 수집: {len(rows)}건")
            new_rows.extend(rows)
        else:
            print("   └ 신규 데이터 없음")
        time.sleep(1)

    if new_rows:
        total = _merge_and_save(new_rows, save_path)
        print(f"[완료] 신규 {len(new_rows)}건 병합 — 누적 총 {total}건 ({save_path})")
    else:
        print("[안내] API에서 신규 데이터가 반환되지 않았습니다.")

    if errors:
        print(f"[오류] 요청 {errors}건 실패 — 받은 데이터만 저장했습니다. 다음 실행 때 최근 구간을 다시 받습니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(collect_primal_increment())
