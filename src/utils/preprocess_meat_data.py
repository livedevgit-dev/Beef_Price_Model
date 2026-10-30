import pandas as pd
import os
import re
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MASTER_PRICE_CSV, DATA_DASHBOARD, DASHBOARD_READY_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# [파일 정의서]
# - 파일명: preprocess_meat_data.py
# - 역할: 가공 (Data Processing)
# - 대상: 공통
# - 데이터 소스: data/1_processed/master_price_data.csv
# - 수집/가공 주기: 일단위
# - 주요 기능: 
#   1. 부위/브랜드 텍스트 정제
#   2. 품목별 주력 등급 고정(등급 기록분) · 중복 평균 처리 및 결측일 데이터 보간 (Forward Fill, is_filled 표시)
#   3. 기술적 지표(이동평균) 산출
#   4. 3대 패커(IBP, Excel, Swift) 취급 부위 기준 필터링 (Option B)

def load_and_enrich_data():
    """
    master_price_data.csv를 로드하여 브랜드/부위를 분리하고
    중복값 평균 처리 및 결측치를 채운 후 이동평균(MA) 등 보조 지표를 추가합니다.
    """
    # 1. 경로 설정
    input_path = MASTER_PRICE_CSV
    if not input_path.exists():
        print(f"[Error] File not found: {input_path}")
        return None

    # 2. 데이터 로드
    df = pd.read_csv(str(input_path), encoding='utf-8-sig')
    df['date'] = pd.to_datetime(df['date'])
    
    # 3. 부위명 및 브랜드 분리 로직
    def split_part_brand(row):
        full_name = str(row['part_name'])
        if '|' in full_name:
            parts = full_name.split('|')
            part_clean = parts[0].split('-')[0].strip()
            brand_clean = parts[1].strip()
            return part_clean, brand_clean
        # 브랜드 없는 백필 품목명('삼겹양지-호주')도 '-국가' 접미사를 떼어 같은 부위로 묶음
        return full_name.split('-')[0].strip(), row['brand']

    # apply 적용
    df[['part', 'brand']] = df.apply(
        lambda x: pd.Series(split_part_brand(x)), axis=1
    )

    # 4. 등급 고정 및 결측 날짜 보간
    print("품목별 주력 등급 고정 및 결측일 데이터 보간(Forward Fill)을 진행합니다...")

    # 같은 날 같은 품목이 여러 등급으로 올라오면 날마다 수집되는 등급 구성이 달라 평균가가 진동함
    # → 등급이 기록된 품목(2026-10-30~)은 (국가, 부위, 브랜드)별 최다 등급 하나만 사용, 등급 미기록 과거분은 그대로
    if 'grade' in df.columns and df['grade'].notna().any():
        g = df[df['grade'].notna()]
        main_grade = g.groupby(['country', 'part', 'brand'])['grade'].agg(lambda x: x.value_counts().idxmax())
        df = df.join(main_grade.rename('main_grade'), on=['country', 'part', 'brand'])
        df = df[df['grade'].isna() | (df['grade'] == df['main_grade'])].drop(columns=['main_grade'])

    # 같은 날짜, 국가, 부위, 브랜드의 가격이 여러 개면(등급 미기록 과거분) 평균(mean)으로 하나로 합칩니다.
    df = df.groupby(['date', 'country', 'part', 'brand'], as_index=False)['wholesale_price'].mean()

    # category 컬럼 생성 (groupby 이후 다시 생성)
    df['category'] = df['country']

    # 날짜를 인덱스로 설정 (_obs_date: ffill 로 채운 행을 구분하기 위한 실제 관측일)
    df['_obs_date'] = df['date']
    df = df.set_index('date')

    # 국가, 부위, 브랜드별로 그룹화한 뒤, 매일('D') 단위로 빈 날짜가 있으면 생성하고 직전 값으로 채웁니다.
    # limit=7: 최대 7일 연속까지만 직전 가격을 채우고, 그 이상 공백이면 NaN 유지
    df = df.groupby(['country', 'part', 'brand']).resample('D').ffill(limit=7)

    # 그룹화로 인해 중첩된 인덱스를 다시 일반 컬럼으로 풀어줍니다.
    df = df.drop(columns=['country', 'part', 'brand'], errors='ignore').reset_index()
    # is_filled: 그날 실제 관측이 없어 직전 값으로 채운 행 (거래일 집계·월평균에서는 제외해야 함)
    df['is_filled'] = df['_obs_date'].isna() | (df['_obs_date'] != df['date'])
    df = df.drop(columns=['_obs_date'])
    
    # 계산을 위해 품목별/날짜별로 다시 정렬합니다.
    df = df.sort_values(by=['country', 'part', 'brand', 'date'])

    # 5. 핵심 지표 계산 (이동평균)
    grouped = df.groupby(['country', 'part', 'brand'])

    # 7일, 30일 이동평균 (장기 결측 구간에서의 왜곡 방지를 위해 min_periods 강화)
    df['ma7'] = grouped['wholesale_price'].transform(lambda x: x.rolling(window=7, min_periods=4).mean())
    df['ma30'] = grouped['wholesale_price'].transform(lambda x: x.rolling(window=30, min_periods=15).mean())

    # 전체 기간 최고/최저 (참고용)
    df['min_total'] = grouped['wholesale_price'].transform('min')
    df['max_total'] = grouped['wholesale_price'].transform('max')

    print(f"Data Loaded & Enriched: {len(df)} rows")
    return df

def save_dashboard_ready_data(df):
    """
    3대 패커(IBP, Excel, Swift)가 취급하지 않는 마이너 부위를 제거하고
    대시보드 전용 데이터로 저장합니다.
    """
    if df is None:
        return

    print("Filtering logic started (Option B)...")

    # 1. 3대 패커 키워드 정의
    major_keywords = ['IBP', 'Excel', 'Swift', '엑셀', '스위프트']
    pattern = '|'.join(major_keywords)

    # 2. 3대 패커가 취급하는 '유효 부위(Valid Parts)' 식별
    is_major_packer = df['brand'].str.contains(pattern, case=False, na=False)
    valid_parts = df.loc[is_major_packer, 'part'].unique()
    
    print(f"- Major Packer Keywords: {major_keywords}")
    print(f"- Total parts in raw data: {df['part'].nunique()}")
    print(f"- Valid parts (traded by Majors): {len(valid_parts)}")

    # 3. 데이터 필터링 (유효 부위에 해당하는 모든 브랜드 데이터 유지)
    df_ready = df[df['part'].isin(valid_parts)].copy()

    print(f"- Filtering Result: {len(df)} rows -> {len(df_ready)} rows")

    # 4. 저장 (data/2_dashboard/dashboard_ready_data.csv)
    ensure_dirs()
    output_path = DASHBOARD_READY_CSV
    
    cols_to_save = [
        'date', 'category', 'part', 'brand',
        'wholesale_price', 'ma7', 'ma30',
        'min_total', 'max_total', 'is_filled'
    ]
    final_cols = [c for c in cols_to_save if c in df_ready.columns]

    atomic_to_csv(df_ready[final_cols], output_path, index=False, encoding='utf-8-sig')
    print(f"Successfully saved to: {output_path}")

# 메인 실행 블록
if __name__ == "__main__":
    df_enriched = load_and_enrich_data()
    save_dashboard_ready_data(df_enriched)