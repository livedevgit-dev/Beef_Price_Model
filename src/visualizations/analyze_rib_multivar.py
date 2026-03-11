# [파일 정의서]
# - 파일명: analyze_rib_multivar.py
# - 역할: 분석/시각화
# - 대상: 수입육 (갈비 - Rib)
# - 데이터 소스: USDA Primal, 수기 한국 도매가, 환율, 수입물량, 재고 데이터
# - 주요 기능: 가격(USD), 환율, 수급 데이터를 완벽히 분리(Decoupling)한 3단 PoC 대시보드

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from pathlib import Path

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config import DATA_RAW, EXCHANGE_RATE_XLSX, USDA_PRIMAL_HISTORY_CSV, MASTER_IMPORT_VOLUME_CSV, BEEF_STOCK_XLSX, MANUAL_KOR_PRICE_CSV

def load_and_merge_rib_data():
    print("갈비(Rib) 다중 변수 데이터(가격, 환율, 수입물량, 재고)를 독립 변수로 병합 중입니다...")
    
    # 1. 미국 갈비(Primal Rib) 도매가 (순수 USD/kg)
    us_df = pd.read_csv(USDA_PRIMAL_HISTORY_CSV)
    us_df = us_df[us_df['primal_desc'] == 'Primal Rib'].copy()
    us_df['date'] = pd.to_datetime(us_df['report_date'])
    us_df['us_price_usd_kg'] = (us_df['choice_600_900'] / 100) * 2.20462
    us_df = us_df[['date', 'us_price_usd_kg']]
    us_df.set_index('date', inplace=True)
    us_monthly = us_df.resample('MS').mean()
    
    # 2. 환율 (KRW/USD) - 독립 변수 유지
    ex_df = pd.read_excel(EXCHANGE_RATE_XLSX)
    ex_df['date'] = pd.to_datetime(ex_df['Date'])
    ex_df = ex_df[['date', 'Close']].rename(columns={'Close': 'exchange_rate'})
    ex_df.set_index('date', inplace=True)
    ex_monthly = ex_df.resample('MS').mean()
    
    # 3. 한국 갈비 도매가 (순수 원/kg)
    kr_df = pd.read_csv(MANUAL_KOR_PRICE_CSV)
    kr_df['date'] = pd.to_datetime(kr_df['날짜'], format='%b-%y', errors='coerce')
    kr_df = kr_df[['date', '갈비_냉동_미국산']].rename(columns={'갈비_냉동_미국산': 'kr_price'}).dropna()
    kr_df.set_index('date', inplace=True)
    kr_monthly = kr_df.resample('MS').mean()
    
    # 4. 수입물량 (미국산 갈비)
    vol_df = pd.read_csv(MASTER_IMPORT_VOLUME_CSV)
    vol_df = vol_df[vol_df['구분'] == '미국']
    vol_df['date'] = pd.to_datetime(vol_df['std_date'], format='%Y-%m')
    vol_df = vol_df[['date', '부위별_갈비_합계']].rename(columns={'부위별_갈비_합계': 'import_volume'})
    vol_df.set_index('date', inplace=True)
    
    # 5. 재고량 (갈비 전체)
    stock_df = pd.read_excel(BEEF_STOCK_XLSX)
    stock_df = stock_df[stock_df['부위별 부위별'].str.contains('갈비', na=False)]
    stock_df['date'] = pd.to_datetime(stock_df['기준년월'], format='%Y-%m')
    stock_df = stock_df[['date', '조사재고량 조사재고량']].rename(columns={'조사재고량 조사재고량': 'stock_volume'})
    stock_df = stock_df.groupby('date')['stock_volume'].sum().reset_index()
    stock_df.set_index('date', inplace=True)
    
    # 데이터 병합 (2019-01-01 이후)
    master_df = pd.concat([us_monthly, ex_monthly, kr_monthly, vol_df, stock_df], axis=1)
    master_df = master_df[master_df.index >= '2019-01-01']
    master_df = master_df.ffill().bfill()
    
    return master_df

def visualize_rib_multivar(df):
    print("독립 변수 기반 3단 시각화 차트를 생성합니다...")
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [2, 1, 1.5]})
    
    # [1단] 순수 가격 트렌드 (미국 USD vs 한국 KRW)
    ax1.set_title('[PoC 베이스라인] 갈비(Rib) 가격/환율/수급 독립 변수 분석 (2019~)', fontsize=14, fontweight='bold')
    ax1.set_ylabel('한국 도매가 (원/kg)', color='tab:red', fontweight='bold')
    line1 = ax1.plot(df.index, df['kr_price'], color='tab:red', linewidth=2.5, label='한국 도매가 (KRW)')
    ax1.tick_params(axis='y', labelcolor='tab:red')
    
    ax1_twin = ax1.twinx()
    ax1_twin.set_ylabel('미국 도매가 (USD/kg)', color='tab:blue', fontweight='bold')
    line2 = ax1_twin.plot(df.index, df['us_price_usd_kg'], color='tab:blue', linestyle='--', linewidth=2.5, label='미국 도매가 (USD)')
    ax1_twin.tick_params(axis='y', labelcolor='tab:blue')
    
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # [2단] 거시 금융 지표 (환율)
    ax2.set_ylabel('원/달러 환율', color='tab:purple', fontweight='bold')
    ax2.plot(df.index, df['exchange_rate'], color='tab:purple', linewidth=2, label='USD/KRW 환율')
    ax2.tick_params(axis='y', labelcolor='tab:purple')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # [3단] 실물 수급 지표 (수입물량 및 재고량)
    ax3.set_xlabel('날짜 (연-월)')
    ax3.set_ylabel('월간 수입물량 (톤)', color='tab:green', fontweight='bold')
    bar1 = ax3.bar(df.index, df['import_volume'], width=20, color='tab:green', alpha=0.6, label='미국산 갈비 수입물량')
    ax3.tick_params(axis='y', labelcolor='tab:green')
    
    ax3_twin = ax3.twinx()
    ax3_twin.set_ylabel('국내 갈비 총 재고량', color='tab:orange', fontweight='bold')
    fill1 = ax3_twin.fill_between(df.index, 0, df['stock_volume'], color='tab:orange', alpha=0.2, label='국내 갈비 총 재고량')
    line3 = ax3_twin.plot(df.index, df['stock_volume'], color='tab:orange', linewidth=2)
    ax3_twin.tick_params(axis='y', labelcolor='tab:orange')
    
    lines2 = [bar1, fill1]
    labels2 = [l.get_label() for l in lines2]
    ax3.legend(lines2, labels2, loc='upper left')
    
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    try:
        rib_multivar_data = load_and_merge_rib_data()
        visualize_rib_multivar(rib_multivar_data)
    except Exception as e:
        print(f"\n[에러 발생] 데이터 처리 중 문제가 발생했습니다: {e}")