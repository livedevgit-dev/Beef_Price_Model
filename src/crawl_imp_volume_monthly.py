import requests
import pandas as pd
import time
import urllib3
import os
from datetime import datetime

# [파일 정의서]
# - 파일명: src/crawl_imp_volume_monthly.py
# - 역할: 수집
# - 대상: 수입육
# - 데이터 소스: 한국육류유통수출협회 (KMTA)
# - 수집/가공 주기: 월단위
# - 주요 기능: 2019년부터 현재까지 '냉동' 섹션의 '미국', '호주' 데이터만 추출하여 저장(합계 제외)

# =========================================================
# 1. 설정 (URL 및 저장 경로)
# =========================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
SAVE_DIR = os.path.join(project_root, "data", "0_raw")
os.makedirs(SAVE_DIR, exist_ok=True)

# 파일명은 기존 시스템 연동을 위해 원래대로 유지합니다.
SAVE_FILENAME = "master_import_volume.csv"
SAVE_PATH = os.path.join(SAVE_DIR, SAVE_FILENAME)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Origin": "https://www.kmta.or.kr",
    "Referer": "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"
}

# =========================================================
# 2. 수집 기간 설정
# =========================================================
start_date = "2019-01-01"
end_date = datetime.now().strftime("%Y-%m-%d")

date_range = pd.date_range(start=start_date, end=end_date, freq='MS')

print(f"--- [시작] 미국/호주 냉동 데이터 수집 (파일명: {SAVE_FILENAME}) ---")

all_data = []

# =========================================================
# 3. 데이터 순회 및 수집
# =========================================================
for target_date in date_range:
    year = str(target_date.year)
    month = f"{target_date.month:02d}"
    
    print(f"▶ {year}년 {month}월 처리 중...", end=" ")
    
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
            
            # 실제 데이터가 있는 테이블 찾기
            target_table = None
            for t in tables:
                if '미국' in t.to_string():
                    target_table = t
                    break
            
            if target_table is not None:
                df = target_table.copy()
                
                # 헤더 평탄화
                new_columns = []
                for col in df.columns:
                    col_name = "_".join([str(c).replace(" ", "") for c in col if "Unnamed" not in str(c)])
                    new_columns.append(col_name)
                df.columns = new_columns
                
                # [필터링 1] '냉동' 섹션만 유지 (이미지상 상단 부위)
                # '냉장' 행이 나오기 전까지만 자릅니다.
                first_col = df.columns[0]
                refrigerated_idx = df[df[first_col].str.contains('냉장', na=False)].index
                if not refrigerated_idx.empty:
                    df = df.iloc[:refrigerated_idx[0]]
                
                # [필터링 2] '미국'과 '호주'만 추출 (이 과정에서 '소계', '합계', '기타' 자동 제거됨)
                df = df[df[first_col].isin(['미국', '호주'])].copy()
                
                # 기준 정보 추가
                df.insert(0, 'std_date', f"{year}-{month}")
                
                all_data.append(df)
                print(f"성공 ({len(df)}건)")
            else:
                print("데이터 없음")
        else:
            print(f"서버 오류 ({response.status_code})")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        
    time.sleep(0.5)

# =========================================================
# 4. 통합 및 저장
# =========================================================
print("\n" + "="*50)
if all_data:
    final_df = pd.concat(all_data, ignore_index=True)
    
    # 최종 저장 (기존 파일명 유지)
    final_df.to_csv(SAVE_PATH, index=False, encoding='utf-8-sig')
    
    print(f"성공: 미국/호주 냉동 데이터만 추출 완료")
    print(f"파일 저장 경로: {SAVE_PATH}")
    print(f"총 행 수: {len(final_df)}행")
else:
    print("실패: 수집된 데이터가 없습니다.")
print("="*50)