import pandas as pd
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import USDA_PRIMAL_HISTORY_CSV, USDA_PLATE_USD_KG_CSV, ensure_dirs

# [파일 정의서]
# - 파일명: src/utils/preprocess_primal.py
# - 역할: 데이터 가공 (전처리)
# - 대상: 수집된 usda_primal_history.csv
# - 주요 기능: 
#   1. 'Primal Plate(우삼겹)' 데이터만 필터링
#   2. 단위 변환 (100lbs 당 달러 -> 1kg 당 달러(USD/kg))
#   * 환율은 곱하지 않고 독립 변수로 남겨둠 (기획자 요청사항)

RAW_FILE = USDA_PRIMAL_HISTORY_CSV
PROCESSED_FILE = USDA_PLATE_USD_KG_CSV

def preprocess_primal():
    print("=" * 60)
    print("[시작] USDA Primal Plate(우삼겹) 데이터 전처리 (환율 제외)")
    print("=" * 60)

    if not RAW_FILE.exists():
        print("[에러] 원본 데이터 파일이 없습니다. 수집부터 진행해주세요.")
        return

    # 1. 데이터 로드
    df = pd.read_csv(str(RAW_FILE))
    
    # 2. 'Primal Plate' 부위만 필터링 (대소문자 무시)
    df_plate = df[df['primal_desc'].str.contains('plate', case=False, na=False)].copy()
    
    if df_plate.empty:
        print("[에러] 데이터 내에 'Plate' 항목이 없습니다.")
        return
        
    # 3. 날짜 형식 통일 및 정렬
    df_plate['report_date'] = pd.to_datetime(df_plate['report_date'])
    df_plate = df_plate.sort_values('report_date').reset_index(drop=True)

    # 4. 가격 단위 변환 (100lbs -> 1kg)
    # 공식: 100 lbs = 45.3592 kg
    LBS100_TO_KG = 45.3592
    
    # 숫자형으로 변환 (결측치는 이전 값으로 채우거나 제외)
    df_plate['choice_600_900'] = pd.to_numeric(df_plate['choice_600_900'], errors='coerce')
    df_plate['select_600_900'] = pd.to_numeric(df_plate['select_600_900'], errors='coerce')
    
    # 1kg당 달러(USD) 가격 산출
    df_plate['choice_usd_per_kg'] = df_plate['choice_600_900'] / LBS100_TO_KG
    df_plate['select_usd_per_kg'] = df_plate['select_600_900'] / LBS100_TO_KG

    # 5. 필요한 컬럼만 정리하여 최종 데이터프레임 생성
    final_cols = ['report_date', 'primal_desc', 'choice_usd_per_kg', 'select_usd_per_kg']
    df_final = df_plate[final_cols].copy()
    
    # 소수점 4자리까지 반올림
    df_final['choice_usd_per_kg'] = df_final['choice_usd_per_kg'].round(4)
    df_final['select_usd_per_kg'] = df_final['select_usd_per_kg'].round(4)

    # 6. 저장
    ensure_dirs()
    df_final.to_csv(str(PROCESSED_FILE), index=False, encoding='utf-8-sig')
    
    print(f"[완료] 전처리 완료! 총 {len(df_final)}일 치의 우삼겹 USD/kg 데이터가 생성되었습니다.")
    print(f"[저장 위치] {PROCESSED_FILE}")
    print("=" * 60)
    print(df_final.head())

if __name__ == "__main__":
    preprocess_primal()