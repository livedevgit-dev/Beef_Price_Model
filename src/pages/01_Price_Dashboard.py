import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py
# - 역할: 시각화 (KPI 및 이동평균 분석)
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv

st.set_page_config(page_title="Price Dashboard", page_icon="📈", layout="wide")

# --------------------------------------------------------------------------------
# 1. 데이터 로드 및 전처리 (준비 단계)
# --------------------------------------------------------------------------------
@st.cache_data
def load_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
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
# 2. 사이드바 컨트롤 (기간 및 품목 선택)
# --------------------------------------------------------------------------------
st.sidebar.header("Filter Options")

# [기간 선택 기능 추가] 기획하신 3, 6, 12개월 필터
period_options = ["1개월", "3개월", "6개월", "12개월", "전체"]
selected_period = st.sidebar.radio("분석 기간", period_options, index=3, horizontal=True)

# 품목 필터링 (Home 연동)
default_cat, default_part, default_brand = "전체", "전체", "전체"
if "target_product" in st.session_state:
    target = st.session_state["target_product"]
    if target['category'] in df['category'].unique(): default_cat = target['category']
    if target['part'] in df['part'].unique(): default_part = target['part']
    if target['brand'] in df['brand'].unique(): default_brand = target['brand']

# 1) 원산지
cat_list = ['전체'] + sorted(df['category'].unique().tolist())
cat_idx = cat_list.index(default_cat) if default_cat in cat_list else 0
sel_cat = st.sidebar.selectbox("원산지 (Origin)", cat_list, index=cat_idx)

# 2) 부위
df_cat = df[df['category'] == sel_cat] if sel_cat != '전체' else df
part_list = ['전체'] + sorted(df_cat['part'].unique().tolist())
part_idx = part_list.index(default_part) if default_part in part_list else 0
sel_part = st.sidebar.selectbox("부위 (Part)", part_list, index=part_idx)

# 3) 브랜드
df_part = df_cat[df_cat['part'] == sel_part] if sel_part != '전체' else df_cat
brand_list = ['전체'] + sorted(df_part['brand'].unique().tolist())
brand_idx = brand_list.index(default_brand) if default_brand in brand_list else 0
sel_brand = st.sidebar.selectbox("브랜드 (Brand)", brand_list, index=brand_idx)

# --------------------------------------------------------------------------------
# 3. 데이터 가공 (chart_df 생성)
# --------------------------------------------------------------------------------
# (1) 품목 필터링
filtered_df = df.copy()
if sel_cat != '전체': filtered_df = filtered_df[filtered_df['category'] == sel_cat]
if sel_part != '전체': filtered_df = filtered_df[filtered_df['part'] == sel_part]
if sel_brand != '전체': filtered_df = filtered_df[filtered_df['brand'] == sel_brand]

# (2) 기간 필터링 로직
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
    else: # 전체
        start_date_limit = min_date

    filtered_df = filtered_df[filtered_df['date'] >= start_date_limit]

    # (3) 집계 및 chart_df 생성
    # 브랜드가 '전체'인 경우 날짜별 평균을 구해서 차트를 그림
    chart_df = filtered_df.groupby('date')[['wholesale_price']].mean().reset_index()
    
    # 이동평균 재계산 (기간/필터에 맞게)
    chart_df['ma7'] = chart_df['wholesale_price'].rolling(window=7, min_periods=1).mean()
    chart_df['ma30'] = chart_df['wholesale_price'].rolling(window=30, min_periods=1).mean()
    
    # UI용 변수 설정
    display_name = f"{sel_part}"
    if sel_brand != '전체':
        display_name += f" ({sel_brand})"
    
    if not chart_df.empty:
        start_date = chart_df['date'].min().strftime('%Y-%m-%d')
        end_date = chart_df['date'].max().strftime('%Y-%m-%d')
    else:
        start_date, end_date = "-", "-"

    # --------------------------------------------------------------------------------
    # ▼▼▼ [여기서부터 기획자님이 작성하신 코드입니다] ▼▼▼
    # --------------------------------------------------------------------------------
    
    # --------------------------------------------------------------------------------
    # 5. 메인 대시보드 화면 구성
    # --------------------------------------------------------------------------------
    st.title(f"🥩 {display_name} 시세 분석")
    st.markdown(f"기간: {start_date} ~ {end_date}")

    # [스타일 보정] 폰트 사이즈를 줄이는 CSS 주입
    st.markdown("""
        <style>
        /* 메트릭(숫자) 폰트 사이즈 줄이기 */
        div[data-testid="stMetricValue"] {
            font-size: 24px !important;
        }
        /* 메트릭 라벨(제목) 폰트 사이즈 줄이기 */
        div[data-testid="stMetricLabel"] {
            font-size: 14px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if not chart_df.empty:
        # --------------------------------------------------------------------------------
        # (1) KPI 카드 (3분할 구조 + 폰트 축소)
        # --------------------------------------------------------------------------------
        latest_row = chart_df.iloc[-1]
        current_price = int(latest_row['wholesale_price'])
        
        # [기준 1] 전일 대비 등락
        if len(chart_df) > 1:
            prev_price = int(chart_df.iloc[-2]['wholesale_price'])
            diff_prev = current_price - prev_price
            diff_pct_prev = (diff_prev / prev_price) * 100
        else:
            diff_prev = 0
            diff_pct_prev = 0.0

        # [기준 2] 기간 내 최고가/최저가
        max_price_period = int(chart_df['wholesale_price'].max())
        min_price_period = int(chart_df['wholesale_price'].min())

        diff_from_max = current_price - max_price_period
        pct_from_max = (diff_from_max / max_price_period) * 100 if max_price_period else 0

        diff_from_min = current_price - min_price_period
        pct_from_min = (diff_from_min / min_price_period) * 100 if min_price_period else 0

        # 화면 배치 (3개 컬럼)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="현재가 (전일비)", 
                value=f"{current_price:,}원", 
                delta=f"{diff_prev:,}원 ({diff_pct_prev:.1f}%)"
            )
        
        with col2:
            st.metric(
                label="기간 최고가 (괴리율)", 
                value=f"{max_price_period:,}원", 
                delta=f"{diff_from_max:,}원 ({pct_from_max:.1f}%)",
                delta_color="inverse"
            )
            
        with col3:
            st.metric(
                label="기간 최저가 (괴리율)", 
                value=f"{min_price_period:,}원", 
                delta=f"+{diff_from_min:,}원 (+{pct_from_min:.1f}%)",
                delta_color="normal"
            )

        # 메시지 박스 (차트와 겹치지 않게 간격 조정)
        if current_price <= (min_price_period * 1.05):
            st.success(f"✅ **매수 기회!** 최저가({min_price_period:,}원)에 근접")
        elif current_price >= (max_price_period * 0.95):
            st.warning(f"🚨 **고점 주의!** 최고가({max_price_period:,}원)에 근접")
        else:
            st.info("비교적 평이한 가격 흐름입니다.")

        st.divider()

        # (2) 메인 차트 (Plotly)
        st.subheader("📈 시세 추세 및 이동평균선")
        
        fig = go.Figure()
        
        # 실제 가격 선
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['wholesale_price'],
                                 mode='lines+markers', name='실제 도매가',
                                 line=dict(color='#FF4B4B', width=2)))
        
        # 7일 이평선
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['ma7'],
                                 mode='lines', name='7일 이동평균',
                                 line=dict(color='#FFA15A', width=1, dash='dot')))
        
        # 30일 이평선
        fig.add_trace(go.Scatter(x=chart_df['date'], y=chart_df['ma30'],
                                 mode='lines', name='30일 이동평균',
                                 line=dict(color='#1F77B4', width=1.5)))

        fig.update_layout(
            height=500, 
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20) # 여백을 줄여 차트를 더 크게
        )
        st.plotly_chart(fig, use_container_width=True)

        # (3) 하단 데이터 테이블
        with st.expander("📊 상세 데이터 보기 (클릭하여 펼치기)"):
            display_cols = ['date', 'wholesale_price', 'ma7', 'ma30']
            st.dataframe(chart_df[display_cols].sort_values(by='date', ascending=False),
                         use_container_width=True)
            
    else:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")

else:
    st.warning("선택한 필터 조건에 해당하는 데이터가 없습니다.")