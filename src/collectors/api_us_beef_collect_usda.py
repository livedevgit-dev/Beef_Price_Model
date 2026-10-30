import os
import requests
import pandas as pd
import time
import urllib3
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import USDA_BEEF_HISTORY_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# [파일 정의서]
# - 파일명: src/collectors/api_us_beef_collect_usda.py
# - 역할: 수집
# - 대상: 수입육 (미국 소고기 전체 시장 데이터)
# - 데이터 소스: USDA API (Choice, Select, Ground, Trimmings)
# - 수집/가공 주기: 일단위 (최초 실행 시 2019년부터 전체 수집)
# - 주요 기능:
#   1. 미국 소고기 도매시장 4대 섹션 전체 데이터 수집
#   2. 대용량 수집 중단 리스크 방지를 위한 6개월(130 영업일) 단위 중간 저장
#   3. 자가 치유 증분: 매 실행마다 마지막 수집일 기준 최근 5영업일을 다시 받아 해당 (날짜·섹션) 행을 교체
#      (지연 게시·정정분 반영, 직전 실행에서 일부 섹션이 실패했어도 다음 실행에서 메워짐)
#   4. 실패 처리 (2026-10 정합성 수정):
#      - 네트워크 예외 / HTTP 200 이외 / JSON 파싱 실패 = '오류'로 집계 → 받은 만큼 저장 후 exit 1
#      - 'No Results Found.'(미국 공휴일·미게시) = 정상(데이터 없음) → exit 0
#      - 기존 CSV 를 읽지 못하면 2019년부터 재수집하지 않고 즉시 중단(exit 1)
#   ※ 무거래일은 원본에 가격 .00 + number_trades 빈 값으로 들어온다. raw 는 그대로 두고
#     process_usda_data.py 에서 NaN 으로 바꾼다.

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

REFETCH_BUSINESS_DAYS = 5   # 매 실행 재수집하는 최근 영업일 수
REQUEST_RETRY = 2           # 네트워크 예외 시 재시도 횟수


class ExistingFileError(RuntimeError):
    pass


def get_api_key():
    return os.getenv("USDA_API_KEY")

def get_paths():
    ensure_dirs()
    return str(USDA_BEEF_HISTORY_CSV)

def get_last_update_date(save_path):
    if os.path.exists(save_path):
        try:
            df = pd.read_csv(save_path, usecols=['report_date'])
            dt = pd.to_datetime(df['report_date'], errors='coerce').dropna()
        except Exception as e:
            raise ExistingFileError(f"기존 파일을 읽을 수 없습니다 ({type(e).__name__}: {e})")
        if dt.empty:
            raise ExistingFileError("기존 파일에 유효한 report_date 가 없습니다")
        last_date = dt.max()
        print(f"[시스템] 기존 데이터 발견: 마지막 수집일 {last_date.strftime('%Y-%m-%d')}")
        return last_date

    print("[시스템] 기존 데이터 없음: 2019-01-01부터 전체 수집을 시작합니다.")
    return datetime(2018, 12, 31)

def generate_new_dates(last_date, refetch=True):
    # refetch=True: 마지막 수집일 포함 최근 N영업일을 다시 받아 교체 (자가 치유)
    if refetch:
        start_date = pd.Timestamp(last_date) - pd.offsets.BDay(REFETCH_BUSINESS_DAYS - 1)
    else:
        start_date = pd.Timestamp(last_date) + timedelta(days=1)
    end_date = datetime.now()
    if start_date > end_date:
        return []
    dates = pd.date_range(start=start_date, end=end_date, freq='B') # B: 비즈니스 데이(영업일)
    date_strings = [d.strftime('%m/%d/%Y') for d in dates]
    date_strings.sort(reverse=True)
    return date_strings

def save_checkpoint(new_data, save_path):
    """메모리에 쌓인 데이터를 CSV 파일에 병합하고 저장하는 헬퍼 함수입니다.
    새로 받은 (report_date, grade) 묶음은 기존 행을 통째로 교체한다 (정정·삭제분까지 반영)."""
    if not new_data:
        return 0

    df_new = pd.DataFrame(new_data)
    df_new['_key_dt'] = pd.to_datetime(df_new['report_date'], errors='coerce')

    if os.path.exists(save_path):
        df_old = pd.read_csv(save_path)
        df_old['_key_dt'] = pd.to_datetime(df_old['report_date'], errors='coerce')
        new_keys = set(zip(df_new['_key_dt'], df_new['grade']))
        replaced = pd.Series(list(zip(df_old['_key_dt'], df_old['grade'])), index=df_old.index).isin(new_keys)
        df_final = pd.concat([df_old[~replaced], df_new], ignore_index=True)
    else:
        df_final = df_new

    # 중복 제거 (날짜 + 품목명 + 등급 기준)
    if 'item_description' in df_final.columns:
        subset_cols = ['_key_dt', 'item_description', 'grade']
    else:
        subset_cols = None

    if subset_cols:
         df_final.drop_duplicates(subset=subset_cols, inplace=True, keep='last')
    else:
         df_final.drop_duplicates(inplace=True)

    # 정렬 (날짜 -> 등급 -> 품목명)
    sort_cols = ['_key_dt', 'grade']
    if 'item_description' in df_final.columns:
        sort_cols.append('item_description')

    df_final = df_final.sort_values(by=sort_cols, ascending=[False, True, True])
    df_final = df_final.drop(columns=['_key_dt'])

    atomic_to_csv(df_final, save_path, index=False, encoding='utf-8-sig')
    return len(df_final)

def fetch_section(api_key, section, date_str):
    """(results, error) 반환. results=[] & error=None 이면 '데이터 없음'(공휴일·미게시)."""
    base_url = f"https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/{section}"
    query = f"report_date={date_str}"
    last_err = None
    for attempt in range(REQUEST_RETRY + 1):
        try:
            response = requests.get(
                base_url,
                auth=(api_key, '') if api_key else None,
                params={'q': query},
                verify=False, timeout=30
            )
        except requests.RequestException as e:
            last_err = f"연결 실패({type(e).__name__})"
            time.sleep(1.0 + attempt)
            continue
        if response.status_code != 200:
            return [], f"HTTP {response.status_code}"
        try:
            data = response.json()
        except ValueError:
            return [], "JSON 파싱 실패"
        if isinstance(data, dict):
            return data.get('results', []) or [], None
        if isinstance(data, str) and 'no results' in data.lower():
            return [], None   # 공휴일·미게시 → 정상
        return [], f"예상 밖 응답({type(data).__name__})"
    return [], last_err

def fetch_and_append():
    api_key = get_api_key()
    save_path = get_paths()

    try:
        last_date = get_last_update_date(save_path)
    except ExistingFileError as e:
        print(f"[중단] {e}: {save_path}")
        print("        2019년부터 재수집하지 않습니다. 파일을 확인/복구한 뒤 다시 실행하세요.")
        return 1
    target_dates = generate_new_dates(last_date, refetch=os.path.exists(save_path))

    if not target_dates:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return 0

    target_sections = [
        'Choice Cuts',    # 상급 부분육
        'Select Cuts',    # 일반/저가 부분육
        'Ground Beef',    # 다짐육/패티용
        'Beef Trimmings'  # 자투리/가공용
    ]

    total_days = len(target_dates)
    print(f"[안내] 수집 시작(최근 {REFETCH_BUSINESS_DAYS}영업일 재수집 포함): {target_dates[-1]} ~ {target_dates[0]} (총 {total_days}일)")

    new_data = []
    errors = []
    chunk_size = 130 # 영업일 기준 약 6개월 치 분량

    for i, date_str in enumerate(target_dates):
        print(f"\r[진행중] [{i+1}/{total_days}] {date_str} 데이터 4종 요청 중...", end="")

        for section in target_sections:
            results, err = fetch_section(api_key, section, date_str)
            if err:
                errors.append(f"{date_str} {section}: {err}")
                time.sleep(0.5)
                continue
            if results:
                clean_name = section.replace(' Cuts', '').replace('Beef ', '')
                for item in results:
                    item['grade'] = clean_name
                new_data.extend(results)

        # [중간 저장 로직] 130일(약 6개월) 단위로 파일에 저장하고 메모리 비우기
        if (i + 1) % chunk_size == 0 or (i + 1) == total_days:
            if new_data:
                total_rows = save_checkpoint(new_data, save_path)
                print(f"\n[자동 저장] {date_str}까지의 데이터를 안전하게 기록했습니다. (현재 누적 총 {total_rows}건)")
                new_data = [] # 다음 6개월 치를 위해 메모리 초기화
                time.sleep(1) # 디스크 저장 후 잠시 대기

    if errors:
        print(f"\n[오류] 요청 {len(errors)}건 실패 — 받은 데이터는 저장됨. "
              f"다음 실행 때 최근 {REFETCH_BUSINESS_DAYS}영업일을 다시 받습니다.")
        for e in errors[:10]:
            print(f"   └ {e}")
        return 1
    print("\n[완료] 지정된 기간의 데이터 수집 및 최종 저장이 모두 끝났습니다.")
    return 0

if __name__ == "__main__":
    sys.exit(fetch_and_append())
