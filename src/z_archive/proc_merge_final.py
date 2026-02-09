"""
[파일 정의서]
- 파일명: proc_merge_final.py
- 역할: 가공 (Final Merge)
- 대상: 공통 (시세 데이터 전체)
- 데이터 소스: 
    1. data/0_raw/history_batch/*.xlsx (과거 12개월, API 원천)
    2. data/1_processed/beef_price_history.xlsx (최신 1개월, 이미 전처리됨)
- 주요 기능: 
    - 두 소스의 컬럼명을 표준 영어 변수명으로 통일
    - 날짜 기준 정렬 및 중복 제거
    - 최종 학습용 데이터셋(master_price_data.csv) 생성
"""

import pandas as pd
import os
import glob

def main():
    # 1. 경로 설정 (기획자님 환경에 맞춘 절대 경로)
    PROJECT_ROOT = r"D:\Beef_Price_Model"
    
    # 입력 데이터 경로
    PATH_HISTORY_BATCH = os.path.join(PROJECT_ROOT, "data", "0_raw", "history_batch")
    PATH_RECENT_PROCESSED = os.path.join(PROJECT_ROOT, "data", "1_processed", "beef_price_history.xlsx")
    
    # 출력 데이터 경로
    PATH_SAVE_DIR = os.path.join(PROJECT_ROOT, "data", "1_processed")

    print(">> [최종 통합 프로세스] 시작합니다.")

    # -----------------------------------------------------
    # Step 1: 과거 데이터 로딩 (History Batch)
    # -----------------------------------------------------
    history_files = glob.glob(os.path.join(PATH_HISTORY_BATCH, "*.xlsx"))
    print(f"   1. 과거 데이터(Batch) 로딩 중... (파일 {len(history_files)}개)")
    
    df_past_list = []
    for f in history_files:
        try:
            temp = pd.read_excel(f)
            
            # 필요한 컬럼 존재 여부 확인 및 선택
            # 과거 데이터는 'marketPrice'가 실제 변동가격임
            if 'marketPrice' in temp.columns:
                temp = temp[['기준일자', '품목명', '원산지', 'marketPrice']].copy()
                temp.columns = ['date', 'part_name', 'country', 'wholesale_price']
                
                # 브랜드 정보가 있다면 추가 (없으면 '-' 처리)
                # (API 데이터 구조상 브랜드 정보는 별도 매핑이 필요할 수 있으나, 일단 핵심 4개 컬럼 위주로 통합)
                temp['brand'] = '-' 
                
                # 가격이 0인 데이터 제거
                temp = temp[temp['wholesale_price'] > 0]
                df_past_list.append(temp)
                
        except Exception as e:
            print(f"      [Pass] {os.path.basename(f)} 읽기 실패")

    if df_past_list:
        df_past = pd.concat(df_past_list, ignore_index=True)
    else:
        df_past = pd.DataFrame()
        print("      [Warning] 과거 데이터를 가져오지 못했습니다.")

    print(f"      -> 과거 데이터 확보: {len(df_past)}행")

    # -----------------------------------------------------
    # Step 2: 최신 데이터 로딩 (Processed History)
    # -----------------------------------------------------
    print(f"   2. 최신 데이터(Processed) 로딩 중... ({os.path.basename(PATH_RECENT_PROCESSED)})")
    
    if os.path.exists(PATH_RECENT_PROCESSED):
        df_recent = pd.read_excel(PATH_RECENT_PROCESSED)
        
        # 기획자님이 확인해주신 컬럼: ['기준일자', '품목명', '원산지', '보관', '도매시세']
        # 여기서 '도매시세'를 가격으로 사용
        target_cols = ['기준일자', '품목명', '원산지', '도매시세']
        
        # 컬럼명이 정확한지 방어적 코딩
        existing_cols = [c for c in target_cols if c in df_recent.columns]
        df_recent = df_recent[existing_cols].copy()
        
        # 컬럼명 변경 (영어 표준화)
        rename_map = {
            '기준일자': 'date',
            '품목명': 'part_name',
            '원산지': 'country',
            '도매시세': 'wholesale_price'
        }
        df_recent = df_recent.rename(columns=rename_map)
        
        # 브랜드 컬럼 추가 (현재 파일에는 브랜드가 품목명에 섞여있지 않고 분리되어 있지 않으므로 '-' 처리하거나, 필요시 파싱)
        # 이미지상 품목명에 브랜드가 섞여있지 않으므로 일단 '-'로 둡니다.
        df_recent['brand'] = '-'
        
        print(f"      -> 최신 데이터 확보: {len(df_recent)}행")
    else:
        print("      [Error] 최신 데이터 파일을 찾을 수 없습니다.")
        df_recent = pd.DataFrame()

    # -----------------------------------------------------
    # Step 3: 병합 및 저장 (Merge & Save)
    # -----------------------------------------------------
    print("   3. 병합 및 정렬 중...")
    
    # 두 데이터셋 합치기
    master_df = pd.concat([df_past, df_recent], ignore_index=True)
    
    # 날짜 형식 확실하게 변환
    master_df['date'] = pd.to_datetime(master_df['date'])
    
    # 정렬: 날짜 -> 부위 -> 국가 순
    master_df = master_df.sort_values(by=['date', 'part_name', 'country'])
    
    # 중복 제거 (과거 데이터와 최신 데이터가 겹치는 날짜가 있을 경우 최신 데이터 우선 등)
    # 여기서는 단순히 완전히 같은 행을 제거합니다.
    master_df = master_df.drop_duplicates(subset=['date', 'part_name', 'country'], keep='last')
    
    # 저장
    save_path = os.path.join(PATH_SAVE_DIR, "master_price_data.csv")
    master_df.to_csv(save_path, index=False, encoding='utf-8-sig')

    print("==========================================")
    print(f"   ✅ [성공] 마스터 데이터셋 생성 완료")
    print(f"   📂 저장 경로: {save_path}")
    print(f"   📊 총 데이터: {len(master_df)}행")
    print(f"   📅 데이터 기간: {master_df['date'].min().date()} ~ {master_df['date'].max().date()}")
    print("==========================================")
    print(master_df.head())

if __name__ == "__main__":
    main()