# [파일 정의서]
# - 파일명: analyze_shortplate_lag.py
# - 역할: 분석/시각화
# - 대상: 수입육 (삼겹양지)
# - 데이터 소스: USDA 도매가, 한국 도매가, 환율 데이터
# - 주요 기능: 노이즈 스무딩(4주 이동평균) 및 최대 6개월(26주) 장기 Time-Lag 정밀 분석

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, DATA_PROCESSED, EXCHANGE_RATE_XLSX, USDA_PLATE_USD_KG_CSV

def load_and_preprocess_data():
    print("데이터를 불러오고 2023년 이후 주간(Weekly) 단위로 병합 및 스무딩(Smoothing)을 진행합니다...")
    
    us_df = pd.read_csv(USDA_PLATE_USD_KG_CSV)
    us_df['date'] = pd.to_datetime(us_df['report_date'])
    us_df = us_df[['date', 'choice_usd_per_kg']].rename(columns={'choice_usd_per_kg': 'us_price_usd'})
    
    ex_df = pd.read_excel(EXCHANGE_RATE_XLSX)
    ex_df['date'] = pd.to_datetime(ex_df['Date'])
    ex_df = ex_df[['date', 'Close']].rename(columns={'Close': 'exchange_rate'})
    
    kr_file = DATA_RAW / "beef_Short Plate_wholesale_price.xlsx"
    kr_df = pd.read_excel(kr_file, skiprows=2) 
    
    kr_df.columns = ['date', 'item_name', 'kr_price'] + list(kr_df.columns[3:])
    kr_df = kr_df[['date', 'kr_price']].dropna()
    kr_df['date'] = pd.to_datetime(kr_df['date'], errors='coerce')
    kr_df['kr_price'] = pd.to_numeric(kr_df['kr_price'], errors='coerce')
    kr_df = kr_df.dropna()

    start_date = pd.to_datetime('2023-01-01')
    end_date = min(us_df['date'].max(), kr_df['date'].max())
    
    date_range = pd.date_range(start=start_date, end=end_date)
    master_df = pd.DataFrame({'date': date_range})
    
    master_df = pd.merge(master_df, us_df, on='date', how='left')
    master_df = pd.merge(master_df, ex_df, on='date', how='left')
    master_df = pd.merge(master_df, kr_df, on='date', how='left')
    
    master_df = master_df.ffill().bfill()
    
    master_df.set_index('date', inplace=True)
    weekly_df = master_df.resample('W').mean()
    
    # [핵심 로직] 주간 잔파도(노이즈)를 제거하기 위해 4주(약 1개월) 이동평균 적용
    weekly_df['kr_price_smooth'] = weekly_df['kr_price'].rolling(window=4, min_periods=1).mean()
    weekly_df['us_price_usd_smooth'] = weekly_df['us_price_usd'].rolling(window=4, min_periods=1).mean()
    weekly_df['exchange_rate_smooth'] = weekly_df['exchange_rate'].rolling(window=4, min_periods=1).mean()
    
    return weekly_df

def calculate_time_lag(df):
    print("최대 6개월(26주) 범위에서 최적의 시차(Time-Lag)를 탐색하는 중입니다...")
    
    # [핵심 로직] 시차 탐색 범위를 0주 ~ 26주(약 6개월)로 대폭 확장
    lags = range(0, 27) 
    correlations = []
    
    df['us_price_krw_converted'] = df['us_price_usd_smooth'] * df['exchange_rate_smooth']
    
    for lag in lags:
        shifted_us = df['us_price_krw_converted'].shift(lag)
        # 스무딩 처리된 가격끼리 상관관계를 계산하여 굵직한 추세의 일치도를 확인
        corr = shifted_us.corr(df['kr_price_smooth'])
        correlations.append(corr)
        
    best_lag = correlations.index(max(correlations))
    best_corr = max(correlations)
    
    print(f"\n[분석 완료] 미국 우삼겹 가격 변동은 약 **{best_lag}주 (약 {best_lag/4:.1f}개월)** 뒤에 한국 삼겹양지 도매가에 가장 강하게 반영됩니다.")
    print(f"- 최대 상관계수: {best_corr:.3f} (1에 가까울수록 완벽한 동기화)")
    print(f"- 적용 기술: 4주 이동평균 스무딩 적용, 최대 26주 시차 탐색")
    
    return df, best_lag

def visualize_lag(df, best_lag):
    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.set_xlabel('날짜 (연-월)')
    ax1.set_ylabel('한국 삼겹양지 도매가 (원/kg, 4주 평균)', color='tab:red')
    
    # 스무딩 처리된 한국 가격 라인 (선 굵기를 키워 강조)
    line1 = ax1.plot(df.index, df['kr_price_smooth'], color='tab:red', linewidth=2.5, label='한국 도매가 (Smoothed)')
    
    # 원본(Real) 가격은 배경에 연하게(alpha=0.3) 표시하여 참고용으로 남김
    ax1.plot(df.index, df['kr_price'], color='tab:red', alpha=0.3, linestyle=':', label='한국 도매가 (Raw Noise)')
    ax1.tick_params(axis='y', labelcolor='tab:red')

    ax2 = ax1.twinx()  
    ax2.set_ylabel(f'미국 우삼겹 환산가 (원/kg, {best_lag}주 Shifted)', color='tab:blue')
    
    shifted_us_price = df['us_price_krw_converted'].shift(best_lag)
    line2 = ax2.plot(df.index, shifted_us_price, color='tab:blue', linestyle='--', linewidth=2.5, label=f'미국 환산가 ({best_lag}주 시차 적용)')
    ax2.tick_params(axis='y', labelcolor='tab:blue')

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    plt.title(f'미국 vs 한국 삼겹양지 거시 트렌드 분석 (최적 시차: {best_lag}주 / 4주 스무딩 적용)')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    try:
        weekly_data = load_and_preprocess_data()
        analyzed_data, best_lag_weeks = calculate_time_lag(weekly_data)
        visualize_lag(analyzed_data, best_lag_weeks)
    except Exception as e:
        print(f"\n[에러 발생] 데이터 처리 중 문제가 발생했습니다: {e}")