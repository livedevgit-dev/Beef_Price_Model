import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py (구 dashboard_price_app.py)
# - 역할: 시세 데이터 시각화 및 부위별 등락률 요약
# - 데이터 소스: data/1_processed/dashboard_ready_data.csv
# - 업데이트: 메인 화면을 '부위별 등락률 요약 테이블'로 개편 (6개월 하락폭 기준 정렬)

# --------------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 데이터 로드
# --------------------------------------------------------------------------------
st.set_page_config(page_title="소고기 시세 대시보드", page_icon="🥩", layout="wide")

@st.cache_data
def load_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if 'pages' in current_dir:
        project_root = os.path.dirname(os.path.dirname(current_dir))
    else:
        project_root = os.path.dirname(current_dir)
        
    file_path = os.path.join(project_root, "data", "2_dashboard", "dashboard_ready_data.csv")
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    
    # [추가된 핵심 로직] 가공된 파일의 컬럼명을 대시보드에 맞게 호환시켜줍니다.
    df = df.rename(columns={
        'category': 'country',
        'part': 'part_clean',
        'brand': 'brand_clean'
    })
    
    return df

df = load_data()

# --------------------------------------------------------------------------------
# 2. 사이드바 (검색 필터)
# --------------------------------------------------------------------------------
st.sidebar.header("🔍 검색 필터")

if df is None:
    st.error("데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다.")
    st.stop()

# (1) 국가 선택
country_list = sorted(df['country'].unique().tolist())
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
# CASE A: 전체 보기 (요약 테이블 화면)
# ================================================================================
if selected_part == "전체 보기 (가격 동향 요약)":
    st.title("📉 부위별 시세 변동 요약")
    
    # 데이터 가공: 브랜드 통합 평균 가격 산출
    # 날짜와 부위별로 그룹화하여 평균가 계산
    df_avg = df_country.groupby(['date', 'part_clean'])['wholesale_price'].mean().reset_index()
    
    # 기준일(최신) 확인
    latest_date = df_avg['date'].max()
    st.markdown(f"**기준일:** {latest_date.strftime('%Y-%m-%d')} | **기준:** 브랜드 통합 평균가")
    
    # 비교 시점 날짜 계산
    date_3m = latest_date - timedelta(days=90)
    date_6m = latest_date - timedelta(days=180)
    date_12m = latest_date - timedelta(days=365)
    
    # 각 부위별 변동률 계산
    summary_list = []
    
    for part in part_options:
        part_df = df_avg[df_avg['part_clean'] == part].sort_values('date')
        
        # 현재 가격
        curr_row = part_df[part_df['date'] == latest_date]
        if curr_row.empty: continue
        curr_price = curr_row['wholesale_price'].values[0]
        
        # 과거 가격 찾기 (가장 가까운 날짜 검색)
        def get_price_at_date(target_date):
            # target_date 이전이면서 가장 가까운 날짜 찾기
            # (데이터가 매일 없을 수 있으므로)
            available_data = part_df[part_df['date'] <= target_date]
            if available_data.empty:
                return None
            return available_data.iloc[-1]['wholesale_price']

        price_3m = get_price_at_date(date_3m)
        price_6m = get_price_at_date(date_6m)
        price_12m = get_price_at_date(date_12m)
        
        # 변동률 계산
        def calc_pct(curr, past):
            if past is None or past == 0: return None
            return ((curr - past) / past) * 100

        summary_list.append({
            "부위": part,
            "현재가": curr_price,
            "3개월 전 대비": calc_pct(curr_price, price_3m),
            "6개월 전 대비": calc_pct(curr_price, price_6m),
            "1년 전 대비": calc_pct(curr_price, price_12m),
            # 정렬을 위한 6개월 등락값 (None이면 0 처리)
            "_sort_key": calc_pct(curr_price, price_6m) if price_6m else 0
        })
    
    # DataFrame 생성
    df_summary = pd.DataFrame(summary_list)
    
    if not df_summary.empty:
        # [정렬 로직] 6개월 대비 '하락폭'이 큰 순서대로 (오름차순)
        # 값이 작을수록(마이너스가 클수록) 상단에 위치
        df_summary = df_summary.sort_values(by="_sort_key", ascending=True)
        
        # 정렬 키 컬럼 제거
        df_display = df_summary.drop(columns=["_sort_key"])
        
        # 스타일링 함수 (주식 스타일: 상승=빨강, 하락=파랑)
        def style_variance(val):
            if pd.isna(val): return ""
            if val > 0:
                return 'color: #D32F2F; background-color: #FFEBEE; font-weight: bold' # Red
            elif val < 0:
                return 'color: #1976D2; background-color: #E3F2FD; font-weight: bold' # Blue
            return ""

        def format_pct(val):
            if pd.isna(val): return "-"
            return f"{val:+.1f}%"

        # 테이블 표시
        st.dataframe(
            df_display.style
            .format({"현재가": "{:,.0f}원"})
            .format(format_pct, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"])
            .map(style_variance, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"]),
            use_container_width=True,
            height=(len(df_display) + 1) * 35 + 3,
            hide_index=True
        )
        
        st.info("💡 **Tip:** '6개월 전 대비' 하락폭이 큰 순서대로 정렬되어 있습니다. 상세 분석을 원하시면 좌측 메뉴에서 부위를 선택해주세요.")
    else:
        st.warning("분석할 데이터가 충분하지 않습니다.")

# ================================================================================
# CASE B: 상세 분석 화면 (기존 대시보드 기능)
# ================================================================================
else:
    # ----------------------------------------------------------------------------
    # B-1. 추가 필터 (브랜드, 기간) - 상세 화면에서만 노출
    # ----------------------------------------------------------------------------
    # 해당 부위의 데이터만 필터링
    df_part = df_country[df_country['part_clean'] == selected_part]
    
    # 브랜드 필터
    available_brands = sorted(df_part['brand_clean'].unique())
    major_keywords = ['IBP', '엑셀', '스위프트']
    available_majors = [kw for kw in major_keywords if any(kw in b for b in available_brands)]
    brand_ui_options = ['전체'] + available_majors
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏷️ 브랜드 필터")
    selected_brand_ui = st.sidebar.selectbox("브랜드 선택", brand_ui_options)
    
    # 기간 필터
    st.sidebar.subheader("📅 조회 기간")
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
    if selected_brand_ui == '전체':
        display_brand = "시장 전체 평균"
        # 전체 선택 시에도 브랜드별 데이터가 아니라 '평균'을 구해야 함
        target_df = df_part[mask]
    else:
        display_brand = selected_brand_ui
        # 특정 브랜드 포함된 것만 필터링
        target_df = df_part[mask & df_part['brand_clean'].str.contains(selected_brand_ui)]
        
    # 차트용 데이터 (일별 평균)
    if not target_df.empty:
        chart_df = target_df.groupby('date')[['wholesale_price', 'ma7', 'ma30']].mean().reset_index()
    else:
        chart_df = pd.DataFrame()
        
    # ----------------------------------------------------------------------------
    # B-3. 화면 구성 (KPI + 차트)
    # ----------------------------------------------------------------------------
    display_title = f"{selected_country} {selected_part} ({display_brand})"
    st.title(f"🥩 {display_title}")
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
        st.subheader("📈 가격 추이 분석")
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