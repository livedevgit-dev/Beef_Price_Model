import streamlit as st
import pandas as pd
import os
import numpy as np
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, PROCESSED_USDA_COST_CSV, DATA_PROCESSED

# [파일 정의서]
# - 파일명: 04_Backtesting_Analysis.py
# - 역할: 시각화
# - 대상: 수입육 (미국산 삼겹양지)
# - 주요 기능: 수기 데이터(ffill 보간)와 자동화 데이터를 병합하여, 미국 USDA 상륙 원가와 한국 도매가의 시차(Time Lag)를 완벽히 분석함.

# ======================================================
# [설정] 기본 환경 설정 및 경로 지정
# ======================================================
st.set_page_config(page_title="백테스팅 및 시차 분석", layout="wide")

KOR_AUTO_PATH = DASHBOARD_READY_CSV
KOR_UNIFIED_PATH = DATA_PROCESSED / "samgyup_unified_monthly.csv"  # 도매상 과거 + 미트박스 최신 통합
US_DATA_PATH = PROCESSED_USDA_COST_CSV

# ======================================================
# [함수] 데이터 결합 및 최적화 로직
# ======================================================
@st.cache_data
def load_and_merge_data():
    # --------------------------------------------------
    # 1. 달력 뼈대 생성 (2024년 1월 1일 ~ 현재)
    # --------------------------------------------------
    start_date = pd.to_datetime("2024-01-01")
    end_date = pd.to_datetime('today')
    calendar_df = pd.DataFrame({'date': pd.date_range(start=start_date, end=end_date)})

    # --------------------------------------------------
    # 2. 한국 삼겹양지 가격 — 통합 시계열(도매상 과거 + 미트박스 최신)
    #    (기존 manual_kor_price.csv 스키마 불일치 버그 → 통합 시계열로 대체)
    # --------------------------------------------------
    if KOR_UNIFIED_PATH.exists():
        df_uni = pd.read_csv(KOR_UNIFIED_PATH)
        df_uni['date'] = pd.to_datetime(df_uni['date'])
        df_uni = df_uni[['date', 'price_won_per_kg']].rename(columns={'price_won_per_kg': 'KOR_Price_KRW_kg'})
        df_kor_combined = pd.merge(calendar_df, df_uni, on='date', how='left')
        # 월별 → 일별 계단식 보간
        df_kor_combined['KOR_Price_KRW_kg'] = df_kor_combined['KOR_Price_KRW_kg'].ffill()
    else:
        df_kor_combined = calendar_df.copy()
        df_kor_combined['KOR_Price_KRW_kg'] = np.nan

    # --------------------------------------------------
    # 5. 미국 USDA 상륙 원가 로드 및 병합
    # --------------------------------------------------
    df_us = pd.read_csv(US_DATA_PATH)
    df_us['Date'] = pd.to_datetime(df_us['Date'], errors='coerce')
    # 상륙원가 KRW = USD/kg × 환율 (processed_usda_cost.csv 는 USD 컬럼 보유)
    if 'weighted_average_KRW_kg' not in df_us.columns:
        usd = pd.to_numeric(df_us.get('weighted_average_USD_kg'), errors='coerce')
        fx = pd.to_numeric(df_us.get('Exchange_Rate'), errors='coerce')
        df_us['weighted_average_KRW_kg'] = usd * fx
    df_us_valid = df_us.dropna(subset=['item_description', 'weighted_average_KRW_kg'])
    mask_plate = df_us_valid['item_description'].str.contains('short plate', case=False, na=False)
    mask_skirt = df_us_valid['item_description'].str.contains('skirt', case=False, na=False)
    
    df_us_filtered = df_us_valid[mask_plate & ~mask_skirt]
    df_us_daily = df_us_filtered.groupby('Date')['weighted_average_KRW_kg'].mean().reset_index()
    df_us_daily = df_us_daily.rename(columns={'Date': 'date', 'weighted_average_KRW_kg': 'US_Cost_KRW_kg'})

    # 최종 한-미 데이터 병합
    df_merged = pd.merge(calendar_df, df_us_daily, on='date', how='left')
    df_merged = pd.merge(df_merged, df_kor_combined[['date', 'KOR_Price_KRW_kg']], on='date', how='left')

    return df_merged

# ======================================================
# [화면] 대시보드 UI 구성
# ======================================================
def main():
    st.title("한-미 소고기 가격 백테스팅 분석")
    st.markdown("수기 과거 데이터와 자동화 최신 데이터를 결합하여 시차(Time Lag)를 정밀하게 분석합니다.")

    with st.spinner('데이터를 병합하고 보간(Interpolation)하는 중입니다...'):
        df_chart = load_and_merge_data()

    if df_chart.empty:
        st.error("시각화할 데이터가 없습니다.")
        return

    tab1, tab2 = st.tabs(["시계열 차트 분석", "병합 데이터 상세 보기"])

    with tab1:
        st.subheader("🇺🇸 미국 Short Plate vs 🇰🇷 한국 삼겹양지 비교 (2024년 이후)")
        st.markdown(
            "* **파란색 선(US_Cost)**: 미국 상륙 추정 원가\n"
            "* **빨간색 선(KOR_Price)**: 한국 미트박스 실거래가 (과거 수기 데이터 계단식 보간 + 최신 자동화 데이터)"
        )
        
        chart_data = df_chart.set_index('date')
        st.line_chart(
            chart_data[['US_Cost_KRW_kg', 'KOR_Price_KRW_kg']], 
            height=500,
            color=["#1f77b4", "#d62728"]
        )

    with tab2:
        st.subheader("일자별 상세 데이터")
        df_display = df_chart.sort_values(by='date', ascending=False)
        st.dataframe(df_display, width="stretch", hide_index=True)

if __name__ == "__main__":
    main()