import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py
# - 역할: 시각화 (KPI 및 이동평균 분석)
# - 대상: 수입육
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
# - 수집/가공 주기: 일단위
# - 주요 기능: 3대 패커 중심의 브랜드 필터링 및 시세 대시보드

st.set_page_config(page_title="Price Dashboard", page_icon="📈", layout="wide")

# --------------------------------------------------------------------------------
# 1. 데이터 로드 및 전처리
# --------------------------------------------------------------------------------
@st.cache_data
def load_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 프로젝트 구조에 따라 경로 조정 (pages 폴더 내부일 경우 부모의 부모)
    project_root = os.path.dirname(os.path.dirname(current_dir))
    file_path = os.path.join(project_root, "data", "2_dashboard", "dashboard_ready_data.csv")
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    return df

df = load_data()

if df is None:
    st.error("데이터 파일을 찾을 수 없습니다. (data/2_dashboard/dashboard_ready_data.csv)")
    st.stop()

# --------------------------------------------------------------------------------
# 2. 사이드바 컨트롤 (수정된 브랜드 필터 로직)
# --------------------------------------------------------------------------------
st.sidebar.header("Filter Options")

# 분석 기간 선택
period_options = ["1개월", "3개월", "6개월", "12개월", "전체"]
selected_period = st.sidebar.radio("분석 기간", period_options, index=3, horizontal=True)

# 홈 화면 연동 세션 상태 확인
default_cat, default_part, default_brand = "전체", "전체", "전체"
if "target_product" in st.session_state:
    target = st.session_state["target_product"]
    if target['category'] in df['category'].unique(): default_cat = target['category']
    if target['part'] in df['part'].unique(): default_part = target['part']
    if target['brand'] in df['brand'].unique(): default_brand = target['brand']

# 1) 원산지 선택
cat_list = ['전체'] + sorted(df['category'].unique().tolist())
cat_idx = cat_list.index(default_cat) if default_cat in cat_list else 0
sel_cat = st.sidebar.selectbox("원산지 (Origin)", cat_list, index=cat_idx)

# 2) 부위 선택
df_cat = df[df['category'] == sel_cat] if sel_cat != '전체' else df
part_list = ['전체'] + sorted(df_cat['part'].unique().tolist())
part_idx = part_list.index(default_part) if default_part in part_list else 0
sel_part = st.sidebar.selectbox("부위 (Part)", part_list, index=part_idx)

# 3) 브랜드 선택 (핵심 수정 구간)
df_part = df_cat[df_cat['part'] == sel_part] if sel_part != '전체' else df_cat

# UI에 노출할 특정 브랜드만 정의
target_brands = ['IBP', 'Excel', 'Swift']
# 데이터에 실제 존재하는 브랜드 중 타겟 브랜드만 필터링
available_brands = sorted([b for b in df_part['brand'].unique() if b in target_brands])

brand_list = ['전체'] + available_brands
# 만약 홈에서 넘어온 브랜드가 리스트에 없으면 '전체'를 기본값으로 설정
brand_idx = brand_list.index(default_brand) if default_brand in brand_list else 0
sel_brand = st.sidebar.selectbox("브랜드 (Brand)", brand_list, index=brand_idx)

# --------------------------------------------------------------------------------
# 3. 데이터 가공 (기존 로직 유지)
# --------------------------------------------------------------------------------
filtered_df = df.copy()
if sel_cat != '전체': filtered_df = filtered_df[filtered_df['category'] == sel_cat]
if sel_part != '전체': filtered_df = filtered_df[filtered_df['part'] == sel_part]
if sel_brand != '전체': filtered_df = filtered_df[filtered_df['brand'] == sel_brand]

if not filtered_df.empty:
    max_date = filtered_df['date'].max()
    min_date = filtered_df['date'].min()
    
    if selected_period == "1개월":
        start_date_limit = max_date - relativedelta(months=1)
    elif selected_period == "3개월":
        start_date_limit = max_date - relativedelta(months=3)
    elif selected_period == "6개월":
        start_date_limit = max_date - relativedelta(months=6)
    elif selected_period == "12개월":
        start_date_limit = max_date - relativedelta(months=12)
    else:
        start_date_limit = min_date

    filtered_df = filtered_df[filtered_df['date'] >= start_date_limit]
    chart_df = filtered_df.groupby('date')[['wholesale_price']].mean().reset_index()
    
    chart_df['ma7'] = chart_df['wholesale_price'].rolling(window=7, min_periods=1).mean()
    chart_df['ma30'] = chart_df['wholesale_price'].rolling(window=30, min_periods=1).mean()
    
    display_name = f"{sel_part}"
    if sel_brand != '전체':
        display_name += f" ({sel_brand})"
    
    start_date = chart_df['date'].min().strftime('%Y-%m-%d') if not chart_df.empty else "-"
    end_date = chart_df['date'].max().strftime('%Y-%m-%d') if not chart_df.empty else "-"

    # --------------------------------------------------------------------------------
    # 5. 메인 대시보드 화면 구성 (기존 UI 스타일 유지)
    # --------------------------------------------------------------------------------
    st.title(f"🥩 {display_name} 시세 분석")
    st.markdown(f"기간: {start_date} ~ {end_date}")

    st.markdown("""
        <style>
        div[data-testid="stMetricValue"] { font-size: 24px !important; }
        div[data-testid="stMetricLabel"] { font-size: 14px !important; }
        </style>
    """, unsafe_allow_html=True)

    if not chart_df.empty:
        # KPI 카드 계산
        latest_row = chart_df.iloc[-1]
        current_price = int(latest_row['wholesale_price'])
        
        if len(chart_df) > 1:
            prev_price = int(chart_df.iloc[-2]['wholesale_price'])
            diff_prev = current_price - prev_price
            diff_pct_prev = (diff_prev / prev_price) * 100
        else:
            diff_prev, diff_pct_prev = 0, 0.0

        max_price_period = int(chart_df['wholesale_price'].max())
        min_price_period = int(chart_df['wholesale_price'].min())
        diff_from_max = current_price - max_price_period
        pct_from_max = (diff_from_max / max_price_period) * 100 if max_price_period else 0
        diff_from_min = current_price - min_price_period
        pct_from_min = (diff_from_min / min_price_period) * 100 if min_price_period else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="현재가 (전일비)", value=f"{current_price:,}원", delta=f"{diff_prev:,}원 ({diff_pct_prev:.1f}%)")
        with col2:
            st.metric(label="기간 최고가 (괴리율)", value=f"{max_price_period:,}원", delta=f"{diff_from_max:,}원 ({pct_from_max:.1f}%)", delta_color="inverse")
        with col3:
            st.metric(label="기간 최저가 (괴리율)", value=f"{min_price_period:,}원", delta=f"+{diff_from_min:,}원 (+{pct_from_min:.1f}%)", delta_color="normal")

        if current_price <= (min_price_period * 1.05):
            st.success(f"매수 기회! 최저가({min_price_period:,}원)에 근접")
        elif current_price >= (max_price_period * 0.95):
            st.warning(f"고점 주의! 최고가({max_price_period:,}원)에 근접")
        else:
            st.info("비교적 평이한 가격 흐름입니다.")

        st.divider()

        # 메인 차트
        st.subheader("📈 시세 추세 및 이동평균선")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['wholesale_price'], mode='lines+markers', name='실제 도매가', line=dict(color='#FF4B4B', width=2)))
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['ma7'], mode='lines', name='7일 이동평균', line=dict(color='#FFA15A', width=1, dash='dot')))
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['ma30'], mode='lines', name='30일 이동평균', line=dict(color='#1F77B4', width=1.5)))
        fig.update_layout(height=500, hovermode="x unified", margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📊 상세 데이터 보기"):
            display_cols = ['date', 'wholesale_price', 'ma7', 'ma30']
            st.dataframe(chart_df[display_cols].sort_values(by='date', ascending=False), use_container_width=True)
    else:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")
else:
    st.warning("선택한 필터 조건에 해당하는 데이터가 없습니다.")