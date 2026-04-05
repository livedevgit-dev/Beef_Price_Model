# [파일 정의서]
# - 파일명: feature_engineering_rolling.py
# - 역할: 가공 (중장기 버퍼 타겟 생성)
# - 주요 기능: 향후 6개월(Rolling Window) 내 도달 가능한 '최대 상승폭(Max Delta)' 타겟 변수 생성

import sys
import os
import pandas as pd
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from config import (
    DATA_PROCESSED, MANUAL_KOR_PRICE_CSV, MASTER_IMPORT_VOLUME_CSV,
    BEEF_STOCK_XLSX, EXCHANGE_RATE_XLSX, PROCESSED_USDA_COST_CSV
)

def process_daily_to_monthly(df, date_col, value_col, target_col_name):
    df_monthly = df.set_index(date_col).resample('MS')[value_col].mean().to_frame()
    df_monthly.columns = [target_col_name]
    return df_monthly

def load_and_merge_data():
    df_exchange = pd.read_excel(EXCHANGE_RATE_XLSX, parse_dates=['Date'])
    df_exchange_m = process_daily_to_monthly(df_exchange, 'Date', 'Close', 'exchange_rate')

    df_kr_price = pd.read_csv(MANUAL_KOR_PRICE_CSV)
    df_kr_price['date'] = pd.to_datetime(df_kr_price['날짜'], format='%b-%y')
    if df_kr_price['갈비_냉동_미국산'].dtype == 'object':
        df_kr_price['갈비_냉동_미국산'] = df_kr_price['갈비_냉동_미국산'].astype(str).str.replace(',', '').astype(float)
    df_kr_price_m = df_kr_price.set_index('date')[['갈비_냉동_미국산']].rename(columns={'갈비_냉동_미국산': 'kr_price'})

    df_us_price = pd.read_csv(PROCESSED_USDA_COST_CSV, parse_dates=['Date'], low_memory=False)
    df_us_price_rib = df_us_price[df_us_price['item_description'].str.contains('Rib', case=False, na=False)]
    df_us_price_m = process_daily_to_monthly(df_us_price_rib, 'Date', 'weighted_average_USD_kg', 'us_price')

    df_import = pd.read_csv(MASTER_IMPORT_VOLUME_CSV)
    df_import['date'] = pd.to_datetime(df_import['std_date'] + '-01')
    df_import_m = df_import.groupby('date')['부위별_갈비_합계'].sum().to_frame(name='import_vol')

    df_stock = pd.read_excel(BEEF_STOCK_XLSX)
    df_stock['date'] = pd.to_datetime(df_stock['기준년월'] + '-01')
    df_stock_rib = df_stock[df_stock['부위별 부위별'].str.contains('갈비', na=False)]
    df_stock_m = df_stock_rib.groupby('date')['조사재고량 조사재고량'].sum().to_frame(name='stock')

    df_merged = pd.concat([df_kr_price_m, df_us_price_m, df_exchange_m, df_import_m, df_stock_m], axis=1).sort_index()
    df_merged = df_merged[df_merged.index >= '2018-01-01'].interpolate(method='linear')
    return df_merged

def create_rolling_targets(df):
    df = df.copy()

    # 기존 파생 변수 동일하게 생성
    df['import_vol_mom'] = df['import_vol'].pct_change(periods=1)
    df['import_vol_yoy'] = df['import_vol'].pct_change(periods=12)
    df['stock_mom'] = df['stock'].pct_change(periods=1)
    df['stock_yoy'] = df['stock'].pct_change(periods=12)
    df['stock_ma_3'] = df['stock'].rolling(window=3).mean()
    df['margin_spread'] = df['kr_price'] - (df['us_price'] * df['exchange_rate'])

    for lag in [1, 2, 3]:
        df[f'us_price_lag_{lag}'] = df['us_price'].shift(lag)
        df[f'exchange_rate_lag_{lag}'] = df['exchange_rate'].shift(lag)

    # [핵심] 기획자 로직: 향후 1~6개월 뒤 가격을 모두 가져옴
    lead_cols = []
    for i in range(1, 7):
        col_name = f'kr_price_lead_{i}'
        df[col_name] = df['kr_price'].shift(-i)
        lead_cols.append(col_name)

    # 향후 6개월 내 가장 높은 가격 (Max Price)
    df['kr_price_max_6m'] = df[lead_cols].max(axis=1)
    
    # 🎯 새로운 타겟 변수: (향후 6개월 내 최고가) - (현재가) = 최대 상승 기대폭
    df['target_max_diff_6m'] = df['kr_price_max_6m'] - df['kr_price']

    return df

def main():
    print("데이터 로드 및 6개월 버퍼(Rolling Window) 타겟 생성 중...")
    df_base = load_and_merge_data()
    df_ml = create_rolling_targets(df_base)
    
    # 향후 6개월 데이터가 없는 최근 6개월 행은 평가 불가하므로 제거 (dropna)
    df_final = df_ml.dropna()
    
    os.makedirs(DATA_PROCESSED, exist_ok=True)
    save_path = os.path.join(DATA_PROCESSED, "ml_features_rolling_rib.csv")
    df_final.to_csv(save_path)
    print(f"완료! 버퍼 고려용 데이터가 저장되었습니다: {save_path}")

if __name__ == "__main__":
    main()