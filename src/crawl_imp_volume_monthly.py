import requests
import pandas as pd
import time
import urllib3
import os
from datetime import datetime

# [파일 정의서]
# - 파일명: src/crawl_imp_volume_monthly.py
# - 역할: 수집 (KMTA 한국육류유통수출협회)
# - 대상: 수입 소고기 (미국/호주 냉동)
# - 기능: 2019년부터 현재까지 월별 데이터 수집 -> 정제 -> 정렬 -> 저장 (Full Refresh)

# =========================================================
# 1. 설정 (URL 및 저장 경로)
# =========================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
SAVE_DIR = os.path.join(project_root, "data", "0_raw")
os.makedirs(SAVE_DIR, exist_ok=True)

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

print(f"--- [시작] 미국/호주 냉동 데이터 수집 (Target: {SAVE_FILENAME}) ---")
print(f"--- 기간: {start_date} ~ {end_date} ---")

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
# 4. 통합, 정렬 및 저장
# =========================================================
print("\n" + "="*50)
if all_data:
    final_df = pd.concat(all_data, ignore_index=True)
    
    # [핵심] 날짜 기준 내림차순 정렬 (최신순)
    # 문자열 날짜(YYYY-MM)여도 ISO 포맷이므로 정렬이 잘 됨
    final_df = final_df.sort_values(by=['std_date', '구분'], ascending=[False, True])
    
    # 저장
    final_df.to_csv(SAVE_PATH, index=False, encoding='utf-8-sig')
    
    print(f"✅ 수집 및 정렬 완료!")
    print(f"📂 저장 경로: {SAVE_PATH}")
    print(f"📊 총 데이터: {len(final_df)}행")
    print(f"📅 최신 데이터: {final_df.iloc[0]['std_date']} (상단 확인)")
else:
    print("❌ 실패: 수집된 데이터가 없습니다.")
print("="*50)