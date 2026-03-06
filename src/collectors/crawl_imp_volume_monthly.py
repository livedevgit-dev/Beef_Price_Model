import requests
import pandas as pd
import time
import urllib3
import os
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW

# [파일 정의서]
# - 파일명: src/crawl_imp_volume_monthly.py
# - 역할: 수집 (KMTA 한국육류유통수출협회)
# - 대상: 수입 소고기 (미국/호주 냉동)
# - 기능: 월별 데이터 수집 -> 정제 -> 정렬 -> 저장 (증분 업데이트)
#         기존 파일이 있을 경우 마지막 수집 월 이후 데이터만 증분 수집

# =========================================================
# 1. 설정 (URL 및 저장 경로)
# =========================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"

DATA_RAW.mkdir(parents=True, exist_ok=True)
SAVE_PATH = DATA_RAW / "master_import_volume.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Origin": "https://www.kmta.or.kr",
    "Referer": "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"
}

# =========================================================
# 2. 수집 기간 설정 (증분 업데이트)
# =========================================================
START_DATE = "2019-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")


def get_last_collected_date(file_path):
    """기존 파일에서 마지막 수집 월을 확인하여 다음 월 반환"""
    if not os.path.exists(file_path):
        return START_DATE

    try:
        existing_df = pd.read_csv(file_path, encoding='utf-8-sig')
        if existing_df.empty or 'std_date' not in existing_df.columns:
            return START_DATE

        last_date = existing_df['std_date'].max()
        year, month = map(int, str(last_date).split('-')[:2])

        # 다음 달부터 수집
        month += 1
        if month > 12:
            month = 1
            year += 1

        return f"{year}-{month:02d}-01"
    except Exception as e:
        print(f"[경고] 기존 파일 읽기 실패: {e}. 처음부터 수집합니다.")
        return START_DATE


# 기존 파일에서 마지막 수집 월 확인
start_date = get_last_collected_date(SAVE_PATH)
end_year = datetime.now().year
end_month = datetime.now().month

# 이미 최신 상태인지 확인 (다음 수집 시작 월이 현재보다 미래인 경우)
start_dt = pd.to_datetime(start_date)
end_dt = pd.to_datetime(f"{end_year}-{end_month:02d}-01")
if start_dt > end_dt:
    print(f"--- [정보] 이미 최신 데이터입니다. 수집할 데이터가 없습니다. ---")
    print(f"--- 경로: {SAVE_PATH} ---")
    exit(0)

date_range = pd.date_range(start=start_date, end=end_date, freq='MS')

print(f"--- [시작] 미국/호주 냉동 데이터 수집 (Target: {SAVE_FILENAME}) ---")
if start_date != START_DATE:
    print(f"--- [증분 수집] 기간: {start_date[:7]} ~ {end_date[:7]} (신규 데이터만) ---")
else:
    print(f"--- [전체 수집] 기간: {start_date[:7]} ~ {end_date[:7]} ---")

all_data = []

# =========================================================
# 3. 데이터 순회 및 수집
# =========================================================
for target_date in date_range:
    year = str(target_date.year)
    month = f"{target_date.month:02d}"
    
    print(f"▶ {year}-{month} 처리 중...", end=" ")
    
    form_data = {
        "ymw_y": year,
        "ymw_m": month,
        "ymw2_y": year,
        "ymw2_m": month,
        "typ": "write",
        "gubun": "CC01"
    }
    
    try:
        response = requests.post(URL, data=form_data, headers=HEADERS, verify=False)
        
        if response.status_code == 200:
            tables = pd.read_html(response.text)
            target_df = None
            
            # '미국'이 포함된 테이블 찾기
            for t in tables:
                if t.shape[0] > 5 and t.apply(lambda x: x.astype(str).str.contains('미국').any(), axis=1).any():
                    target_df = t
                    break
            
            if target_df is not None:
                # -------------------------------------------------------------
                # [핵심] 냉동 섹션 정밀 슬라이싱 (합계/냉장 제외)
                # -------------------------------------------------------------
                df_str = target_df.astype(str)
                frozen_start = df_str[df_str.apply(lambda x: x.str.contains('냉동').any(), axis=1)].index.tolist()
                chilled_start = df_str[df_str.apply(lambda x: x.str.contains('냉장').any(), axis=1)].index.tolist()
                
                start_idx = 0
                end_idx = len(target_df)
                
                if frozen_start: start_idx = frozen_start[0]
                if chilled_start:
                    valid_ends = [i for i in chilled_start if i > start_idx]
                    if valid_ends: end_idx = valid_ends[0]
                
                section_df = target_df.iloc[start_idx:end_idx].copy()
                
                # 미국/호주 행만 추출
                mask = section_df.apply(lambda x: x.astype(str).isin(['미국', '호주']).any(), axis=1)
                filtered_df = section_df[mask].copy()
                
                # 컬럼 정의
                expected_cols = [
                    '구분', '부위별_갈비_합계', '부위별_등심_합계', '부위별_목심_합계', 
                    '부위별_사태_합계', '부위별_설도_합계', '부위별_안심_합계', 
                    '부위별_앞다리_합계', '부위별_양지_합계', '부위별_우둔_합계', 
                    '부위별_채끝_합계', '부위별_기타_합계', '부위별_계_합계'
                ]
                
                # 컬럼 매핑 및 부족분 채우기
                curr_cols = filtered_df.shape[1]
                if curr_cols >= len(expected_cols):
                    filtered_df = filtered_df.iloc[:, :len(expected_cols)]
                    filtered_df.columns = expected_cols
                else:
                    mapped = expected_cols[:curr_cols]
                    filtered_df.columns = mapped
                    for col in expected_cols[curr_cols:]:
                        filtered_df[col] = 0

                # [중요] 날짜 포맷 통일 (YYYY-MM)
                filtered_df.insert(0, 'std_date', f"{year}-{month}")
                
                # 숫자 변환
                numeric_cols = [c for c in filtered_df.columns if '합계' in c]
                for col in numeric_cols:
                    filtered_df[col] = (
                        filtered_df[col].astype(str)
                        .str.replace(',', '').str.replace('-', '0')
                        .str.replace('nan', '0').str.replace('None', '0')
                    )
                    filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce').fillna(0)

                # [중요] 합계(계) 재계산 (Null 방지)
                parts_cols = [c for c in filtered_df.columns if '부위별_' in c and '계_합계' not in c]
                filtered_df['부위별_계_합계'] = filtered_df[parts_cols].sum(axis=1)

                all_data.append(filtered_df)
                print(f"성공 ({len(filtered_df)}건)")
            else:
                print("데이터 없음")
        else:
            print(f"오류 ({response.status_code})")
            
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(0.2)

# =========================================================
# 4. 통합, 기존 데이터 병합, 정렬 및 저장
# =========================================================
print("\n" + "="*50)
if all_data:
    new_df = pd.concat(all_data, ignore_index=True)

    # 기존 데이터가 있으면 병합
    existing_df = None
    if os.path.exists(SAVE_PATH):
        try:
            existing_df = pd.read_csv(SAVE_PATH, encoding='utf-8-sig')
        except Exception:
            existing_df = None

    if existing_df is not None and not existing_df.empty:
        # 기존 + 신규 병합, 중복 제거 (std_date + 구분 기준)
        final_df = pd.concat([existing_df, new_df], ignore_index=True)
        final_df = final_df.drop_duplicates(subset=['std_date', '구분'], keep='last')
        print(f"📦 병합: 기존 {len(existing_df)}행 + 신규 {len(new_df)}행 = 총 {len(final_df)}행")
    else:
        final_df = new_df

    # [핵심] 날짜 기준 내림차순 정렬 (최신순)
    final_df = final_df.sort_values(by=['std_date', '구분'], ascending=[False, True])

    # 저장
    final_df.to_csv(SAVE_PATH, index=False, encoding='utf-8-sig')

    print(f"✅ 수집 및 정렬 완료!")
    print(f"📂 저장 경로: {SAVE_PATH}")
    print(f"📊 총 데이터: {len(final_df)}행")
    print(f"📅 최신 데이터: {final_df.iloc[0]['std_date']} (상단 확인)")
else:
    if os.path.exists(SAVE_PATH):
        print("ℹ️ 신규 수집 데이터 없음 (아직 업데이트 안 됨). 기존 파일 유지.")
    else:
        print("❌ 실패: 수집된 데이터가 없습니다.")
print("="*50)