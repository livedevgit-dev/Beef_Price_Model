import pandas as pd
import os
import warnings
import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import USDA_BEEF_HISTORY_CSV, EXCHANGE_RATE_XLSX, PROCESSED_USDA_COST_CSV, ensure_dirs

# [파일 정의서]
# - 파일명: process_usda_data.py
# - 역할: 가공
# - 대상: 수입육 (Boxed Beef Cuts 세부 단품)
# - 데이터 소스: USDA 도매가 및 환율
# - 수집/가공 주기: 필요시 (배치성 단위 변환)
# - 주요 기능: 원본 스키마를 보존하며, 환율(Exchange_Rate)을 독립 변수로 분리 유지하고, 고기 가격은 USD/kg 단위로 명시적 변환함.

# ======================================================
# [설정] 기본 환경 설정 및 경로 지정
# ======================================================
warnings.filterwarnings("ignore")

USDA_FILE_PATH = USDA_BEEF_HISTORY_CSV
EXCHANGE_FILE_PATH = EXCHANGE_RATE_XLSX
OUTPUT_FILE_PATH = PROCESSED_USDA_COST_CSV

LB_TO_KG = 0.453592
CWT_DIVISOR = 100 

# ======================================================
# [핵심 로직] 명시적 타겟팅 및 파생 변수 생성
# ======================================================
def process_usda_cost():
    print("=" * 60)
    print("[시작] 미국 USDA 데이터(단품) 환율 및 단위 변환 파이프라인 (환율 분리 버전)")
    print("=" * 60)

    if not USDA_FILE_PATH.exists() or not EXCHANGE_FILE_PATH.exists():
        print("[에러] 원본 데이터 파일이 존재하지 않습니다.")
        return

    print(" - 데이터를 불러오는 중입니다...")
    df_usda = pd.read_csv(str(USDA_FILE_PATH))
    df_exch = pd.read_excel(str(EXCHANGE_FILE_PATH))

    df_usda.columns = df_usda.columns.str.strip()

    if 'report_date' in df_usda.columns:
        df_usda['Date'] = pd.to_datetime(df_usda['report_date'])
    else:
        print("[에러] 원본 데이터에 'report_date' 컬럼이 없습니다.")
        return

    df_exch['Date'] = pd.to_datetime(df_exch['Date'])

    start_date = pd.to_datetime("2019-01-01")
    end_date = df_usda['Date'].max()
    calendar_df = pd.DataFrame({'Date': pd.date_range(start=start_date, end=end_date)})

    print(" - 환율 데이터를 병합 및 보간(ffill -> bfill)합니다. (독립 변수 유지)")
    df_merged = pd.merge(calendar_df, df_exch[['Date', 'Close']], on='Date', how='left')
    df_merged['Close'] = df_merged['Close'].fillna(method='ffill').fillna(method='bfill')
    df_merged = df_merged.rename(columns={'Close': 'Exchange_Rate'})

    print(" - USDA 데이터를 병합합니다 (원본 스키마 유지).")
    df_final = pd.merge(df_merged, df_usda, on='Date', how='left')

    print(" - 가격 및 물량 데이터의 쉼표/텍스트를 제거하고 예외 데이터를 추적합니다.")
    target_cols_to_clean = ['total_pounds', 'price_range_low', 'price_range_high', 'weighted_average']
    
    for col in target_cols_to_clean:
        if col in df_final.columns:
            valid_original_mask = df_final[col].notna() & (df_final[col].astype(str).str.strip() != '') & (df_final[col].astype(str).str.lower() != 'nan')
            cleaned_str = df_final[col].astype(str).str.replace(',', '').str.strip()
            converted_num = pd.to_numeric(cleaned_str, errors='coerce')
            failed_mask = valid_original_mask & converted_num.isna()

            if failed_mask.any():
                weird_values = df_final.loc[failed_mask, col].unique().tolist()
                print(f"   [경고] '{col}' 컬럼에서 계산 불가한 텍스트 발견 (NaN 처리됨). -> 샘플: {weird_values[:3]}")
            
            df_final[col] = converted_num

    print(" - 지정된 타겟 컬럼의 단위 변환(USD/kg, kg)을 수행합니다. (환율 곱셈 제거)")
    
    # 1. 물량 단위 변환 (lbs -> kg)
    if 'total_pounds' in df_final.columns:
        df_final['total_volume_kg'] = (df_final['total_pounds'] * LB_TO_KG).round(2)
        
    # 2. 가격 단위 변환 (100lbs 당 USD -> 1kg 당 USD)
    target_price_cols = ['price_range_low', 'price_range_high', 'weighted_average']
    for col in target_price_cols:
        if col in df_final.columns:
            # 컬럼명을 KRW에서 USD로 변경
            new_col_name = f"{col}_USD_kg" 
            # 100 파운드당 가격을 1 파운드당 가격으로 나눔
            price_per_lb = df_final[col] / CWT_DIVISOR
            # 1 파운드당 가격을 kg당 가격으로 환산 (환율은 곱하지 않음!)
            df_final[new_col_name] = (price_per_lb / LB_TO_KG).round(4)

    ensure_dirs()
    df_final.to_csv(str(OUTPUT_FILE_PATH), index=False, encoding='utf-8-sig')
    print("=" * 60)
    print(f"[완료] 데이터 가공 성공! (저장 위치: {OUTPUT_FILE_PATH})")
    
    added_cols = ['Exchange_Rate', 'total_volume_kg'] + [f"{col}_USD_kg" for col in target_price_cols]
    print(f" - 추가된 파생 변수: {', '.join(added_cols)}")
    print("=" * 60)

if __name__ == "__main__":
    process_usda_cost()