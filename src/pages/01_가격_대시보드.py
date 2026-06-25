import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py
# - 역할: 시세 데이터 시각화 (미시적 뷰)
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
# - 업데이트: CASE A를 Market Highlights(브랜드별 등락) 화면으로 개편

# --------------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 데이터 로드
# --------------------------------------------------------------------------------
st.set_page_config(page_title="소고기 시세 대시보드", page_icon="", layout="wide")

@st.cache_data
def load_data():
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(str(DASHBOARD_READY_CSV))
    df['date'] = pd.to_datetime(df['date'])
    
    # [추가된 핵심 로직] 가공된 파일의 컬럼명을 대시보드에 맞게 호환시켜줍니다.
    df = df.rename(columns={
        'category': 'country',
        'part': 'part_clean',
        'brand': 'brand_clean'
    })
    
    return df

df = load_data()

# 메이저 3사 브랜드 식별 패턴 (대소문자 무시)
MAJOR_BRAND_PATTERN = r"IBP|Excel|Swift|엑셀|스위프트"

# --------------------------------------------------------------------------------
# 1-b. Market Highlights 계산 함수 및 렌더 헬퍼
# --------------------------------------------------------------------------------
def calculate_market_highlights(df_input):
    """각 품목별 12개월 최고/최저 대비 등락률 산출, 전체 목록 반환"""
    if df_input is None or df_input.empty:
        return None, None

    global_latest_date = df_input['date'].max()
    active_cutoff = global_latest_date - timedelta(days=7)
    one_year_ago = global_latest_date - timedelta(days=365)
    df_1y = df_input[df_input['date'] >= one_year_ago]

    product_groups = df_1y.groupby(['country', 'brand_clean', 'part_clean'])
    highlights = []

    for (country, brand, part), group_df in product_groups:
        if len(group_df) < 2:
            continue
        traded = group_df.dropna(subset=['wholesale_price'])
        if traded.empty:
            continue
        last_trade_date = traded['date'].max()
        if last_trade_date < active_cutoff:
            continue

        current_price = traded[traded['date'] == last_trade_date]['wholesale_price'].mean()
        max_price_12m = traded['wholesale_price'].max()
        min_price_12m = traded['wholesale_price'].min()

        drop_rate = (current_price - max_price_12m) / max_price_12m if max_price_12m > 0 else 0
        rise_rate = (current_price - min_price_12m) / min_price_12m if min_price_12m > 0 else 0

        highlights.append({
            'country': country, 'brand': brand, 'part': part,
            'current_price': current_price,
            'max_12m': max_price_12m, 'min_12m': min_price_12m,
            'drop_rate': drop_rate, 'rise_rate': rise_rate
        })

    if not highlights:
        return None, None

    highlights_df = pd.DataFrame(highlights)
    all_drops = highlights_df[highlights_df['drop_rate'] < 0].sort_values('drop_rate', ascending=True)
    all_rises = highlights_df[highlights_df['rise_rate'] > 0].sort_values('rise_rate', ascending=False)
    return all_drops, all_rises


def _render_drop_row(row, key_prefix):
    c1, c2, c3 = st.columns([4, 1.5, 1.5])
    with c1:
        st.markdown(
            f"**{row['part']}**<br>"
            f"<span style='font-size:0.8em; color:grey'>{row['brand']} ({row['country']})</span>",
            unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='padding-top:5px'>{int(row['current_price']):,}원</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='color:blue; padding-top:5px'><b>{row['drop_rate']*100:.1f}%</b></div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:0.2em 0;border:none;border-bottom:1px solid #f0f0f0;'>", unsafe_allow_html=True)


def _render_rise_row(row, key_prefix):
    c1, c2, c3 = st.columns([4, 1.5, 1.5])
    with c1:
        st.markdown(
            f"**{row['part']}**<br>"
            f"<span style='font-size:0.8em; color:grey'>{row['brand']} ({row['country']})</span>",
            unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='padding-top:5px'>{int(row['current_price']):,}원</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='color:red; padding-top:5px'><b>+{row['rise_rate']*100:.1f}%</b></div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:0.2em 0;border:none;border-bottom:1px solid #f0f0f0;'>", unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# 2. 사이드바 (검색 필터)
# --------------------------------------------------------------------------------
st.sidebar.header("검색 필터")

if df is None:
    st.error("데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다.")
    st.stop()

# (1) 국가 선택
# [src/pages/01_Price_Dashboard.py 수정]

# (1) 에러가 발생하는 기존 코드
# country_list = sorted(df['country'].unique().tolist())

# (2) 다음과 같이 수정 (dropna() 추가)
country_list = sorted(df['country'].dropna().unique().tolist())
selected_country = st.sidebar.selectbox("원산지 선택", ['전체'] + country_list)

# 데이터 1차 필터링 (국가)
if selected_country != '전체':
    df_country = df[df['country'] == selected_country].copy()
else:
    df_country = df.copy()

# (2) 부위 선택 (핵심: '전체 보기' 옵션 추가)
# 부위 목록 추출
part_options = sorted(df_country['part_clean'].unique())
# 메인 화면 진입 시 '전체 보기(요약)'이 기본값
selected_part = st.sidebar.selectbox("부위 선택", ["전체 보기 (가격 동향 요약)"] + part_options)

# --------------------------------------------------------------------------------
# 3. 메인 화면 분기 처리
# --------------------------------------------------------------------------------

# ================================================================================
# CASE A: 전체 보기 (Market Highlights — 브랜드별 등락 상세)
# ================================================================================
if selected_part == "전체 보기 (가격 동향 요약)":
    st.title("Market Highlights")
    st.caption("최근 1년간 가격 변동폭이 큰 품목 (브랜드별 상세)")

    st.markdown("""
        <style>
        .stMarkdown p { margin-bottom: 0.2rem; }
        [data-testid="column"] { padding: 0; }
        </style>
    """, unsafe_allow_html=True)

    all_drops, all_rises = calculate_market_highlights(df_country)

    if all_drops is not None and all_rises is not None:
        col_drop, spacer, col_rise = st.columns([1, 0.05, 1])

        # ------------------------------------------------------------------
        # [Left Column] Price Drop
        # ------------------------------------------------------------------
        with col_drop:
            st.markdown(f"#### Price Drop ({len(all_drops)}건)")

            h1, h2, h3 = st.columns([4, 1.5, 1.5])
            h1.markdown(":grey[**품목 (브랜드)**]")
            h2.markdown(":grey[**현재가**]")
            h3.markdown(":grey[**하락률**]")
            st.markdown("<hr style='margin:0;border:none;border-bottom:2px solid #ddd;'>", unsafe_allow_html=True)

            for i, (idx, row) in enumerate(all_drops.iloc[:10].iterrows()):
                _render_drop_row(row, f"d_{idx}")

            if len(all_drops) > 10:
                with st.expander("목록 전체 펼치기"):
                    for i, (idx, row) in enumerate(all_drops.iloc[10:].iterrows()):
                        _render_drop_row(row, f"d_exp_{idx}")

        # ------------------------------------------------------------------
        # [Right Column] Price Rise
        # ------------------------------------------------------------------
        with col_rise:
            st.markdown(f"#### Price Rise ({len(all_rises)}건)")

            h1, h2, h3 = st.columns([4, 1.5, 1.5])
            h1.markdown(":grey[**품목 (브랜드)**]")
            h2.markdown(":grey[**현재가**]")
            h3.markdown(":grey[**상승률**]")
            st.markdown("<hr style='margin:0;border:none;border-bottom:2px solid #ddd;'>", unsafe_allow_html=True)

            for i, (idx, row) in enumerate(all_rises.iloc[:10].iterrows()):
                _render_rise_row(row, f"r_{idx}")

            if len(all_rises) > 10:
                with st.expander("목록 전체 펼치기"):
                    for i, (idx, row) in enumerate(all_rises.iloc[10:].iterrows()):
                        _render_rise_row(row, f"r_exp_{idx}")
    else:
        st.info("데이터가 충분하지 않아 순위를 계산할 수 없습니다.")

# ================================================================================
# CASE B: 상세 분석 화면 (기존 대시보드 기능)
# ================================================================================
else:
    # ----------------------------------------------------------------------------
    # B-1. 추가 필터 (브랜드, 기간) - 상세 화면에서만 노출
    # ----------------------------------------------------------------------------
    # 해당 부위의 데이터만 필터링
    df_part = df_country[df_country['part_clean'] == selected_part]
    
    # 브랜드 필터: 메인 기준은 메이저 3사 평균, 비교용으로 기타 팩커/전체 제공
    brand_series = df_part['brand_clean'].fillna("").astype(str)
    major_mask_all = brand_series.str.contains(MAJOR_BRAND_PATTERN, case=False, regex=True, na=False)
    other_mask_all = (
        (~major_mask_all)
        & (brand_series.str.strip() != "")
        & (brand_series.str.strip() != "-")
    )

    has_major = major_mask_all.any()
    has_other = other_mask_all.any()

    brand_ui_options = []
    if has_major:
        brand_ui_options.append("메이저 3사")
    if has_other:
        brand_ui_options.append("기타 팩커")
    brand_ui_options.append("전체")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("브랜드 필터")
    selected_brand_ui = st.sidebar.selectbox("브랜드 선택", brand_ui_options, index=0)
    
    # 기간 필터
    st.sidebar.subheader("조회 기간")
    period_options = ["3개월", "12개월", "36개월", "전체"]
    selected_period = st.sidebar.radio("기간 선택", period_options, index=0, horizontal=True, label_visibility="collapsed")
    
    # ----------------------------------------------------------------------------
    # B-2. 데이터 가공 (상세)
    # ----------------------------------------------------------------------------
    # 기간 필터링
    max_date = df_part['date'].max()
    min_date = df_part['date'].min()
    
    if selected_period == "3개월": start_date = max_date - timedelta(days=90)
    elif selected_period == "12개월": start_date = max_date - timedelta(days=365)
    elif selected_period == "36개월": start_date = max_date - timedelta(days=365*3)
    else: start_date = min_date
    
    mask = (df_part['date'] >= start_date) & (df_part['date'] <= max_date)
    
    # 브랜드 필터링
    if selected_brand_ui == '메이저 3사':
        display_brand = "메이저 3사 평균"
        target_df = df_part[mask & major_mask_all]
    elif selected_brand_ui == '기타 팩커':
        display_brand = "기타 팩커 평균"
        target_df = df_part[mask & other_mask_all]
    else:
        display_brand = "시장 전체 평균"
        target_df = df_part[mask]
        
    # 차트용 데이터 (일별 평균)
    if not target_df.empty:
        chart_df = target_df.groupby('date')[['wholesale_price', 'ma7', 'ma30']].mean().reset_index()
    else:
        chart_df = pd.DataFrame()
        
    # ----------------------------------------------------------------------------
    # B-3. 화면 구성 (KPI + 차트)
    # ----------------------------------------------------------------------------
    display_title = f"{selected_country} {selected_part} ({display_brand})"
    st.title(display_title)
    st.markdown(f"조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')}")
    
    # CSS: 메트릭 폰트 조절
    st.markdown("""
        <style>
        div[data-testid="stMetricValue"] { font-size: 24px !important; }
        </style>
    """, unsafe_allow_html=True)
    
    if not chart_df.empty:
        # (1) KPI 카드
        latest = chart_df.iloc[-1]
        curr_price = int(latest['wholesale_price'])
        
        # 전일 대비
        if len(chart_df) > 1:
            prev = int(chart_df.iloc[-2]['wholesale_price'])
            diff = curr_price - prev
            diff_pct = (diff / prev) * 100
        else:
            diff, diff_pct = 0, 0
            
        # 최고/최저
        period_max = int(chart_df['wholesale_price'].max())
        period_min = int(chart_df['wholesale_price'].min())
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("현재가 (전일비)", f"{curr_price:,}원", f"{diff:,}원 ({diff_pct:.1f}%)")
        with col2:
            st.metric("기간 최고가", f"{period_max:,}원", f"{curr_price - period_max:,}원 (괴리율)", delta_color="inverse")
        with col3:
            st.metric("기간 최저가", f"{period_min:,}원", f"{curr_price - period_min:,}원 (괴리율)", delta_color="normal")
            
        st.divider()
        
        # (2) 차트 (Plotly)
        st.subheader("가격 추이 분석")
        fig = go.Figure()
        
        # 메인 가격선
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['wholesale_price'], 
                                 mode='lines+markers', name='도매가', 
                                 line=dict(color='#FF4B4B', width=2)))
        # 이평선
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['ma7'], 
                                 mode='lines', name='7일 이동평균', 
                                 line=dict(color='#FFA15A', width=1, dash='dot')))
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['ma30'], 
                                 mode='lines', name='30일 이동평균', 
                                 line=dict(color='#1F77B4', width=1.5)))
        
        fig.update_layout(height=500, hovermode="x unified", margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")