import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# [파일 정의서]
# - 파일명: dashboard_price_app.py
# - 역할: 시각화 (시세 분석 대시보드)
# - 데이터 소스: 1_processed/dashboard_ready_data.csv
# - 주요 기능: 3대 패커 중심 필터링, 기간별 차트, KPI 카드

# --------------------------------------------------------------------------------
# 1. 페이지 기본 설정
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="소고기 시세 대시보드",
    page_icon="🥩",
    layout="wide"
)

# --------------------------------------------------------------------------------
# 2. 데이터 로드 함수 (캐싱 적용)
# --------------------------------------------------------------------------------
@st.cache_data
def load_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    if 'pages' in current_dir:
        project_root = os.path.dirname(os.path.dirname(current_dir))
    else:
        project_root = os.path.dirname(current_dir)
        
    file_path = os.path.join(project_root, "data", "1_processed", "dashboard_ready_data.csv")
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    return df

df = load_data()

# --------------------------------------------------------------------------------
# 3. 사이드바 (필터 영역)
# --------------------------------------------------------------------------------
st.sidebar.header("🔍 검색 필터")

if df is not None:
    # (1) 국가 선택
    country_list = ['전체'] + sorted(df['country'].unique().tolist())
    selected_country = st.sidebar.selectbox("원산지 선택", country_list)

    # (2) 품목 선택
    if selected_country != '전체':
        part_options = sorted(df[df['country'] == selected_country]['part_clean'].unique())
    else:
        part_options = sorted(df['part_clean'].unique())
    
    selected_part = st.sidebar.selectbox("부위 선택", part_options)

    # --------------------------------------------------------------------------------
    # (3) 브랜드 선택 (3대 패커 UI 필터링 적용)
    # --------------------------------------------------------------------------------
    # 해당 부위의 모든 브랜드 목록 추출 (데이터 필터링용)
    available_brands_in_data = sorted(df[df['part_clean'] == selected_part]['brand_clean'].unique())
    
    # 3대 패커 키워드 정의
    major_keywords = ['IBP', '엑셀', '스위프트']
    
    # 현재 데이터(available_brands_in_data)에 존재하는 패커만 UI 목록에 추가
    # 예: 데이터에 '스위프트'가 없으면 UI에도 뜨지 않게 처리
    available_majors = []
    for keyword in major_keywords:
        # 해당 키워드가 포함된 브랜드가 하나라도 있으면 목록에 추가
        if any(keyword in brand for brand in available_brands_in_data):
            available_majors.append(keyword)
            
    # 최종 UI 리스트 구성: '전체' + 존재하는 메이저 브랜드
    brand_ui_options = ['전체'] + available_majors
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏷️ 브랜드 필터")
    
    # 셀렉트박스(단일 선택)로 변경
    selected_brand_ui = st.sidebar.selectbox(
        "분석할 브랜드를 선택하세요",
        options=brand_ui_options
    )

    # (4) 기간 선택
    st.sidebar.subheader("📅 조회 기간")
    period_options = ["3개월", "12개월", "36개월", "전체"]
    selected_period = st.sidebar.radio(
        label="기간을 선택하세요", 
        options=period_options, 
        index=0, 
        horizontal=True, 
        label_visibility="collapsed"
    )

    # 전체 데이터의 최소/최대 날짜 확인
    min_date_in_data = df['date'].min()
    max_date_in_data = df['date'].max()

    # 기간 계산 로직
    if selected_period == "3개월":
        calc_start_date = max_date_in_data - timedelta(days=90)
    elif selected_period == "12개월":
        calc_start_date = max_date_in_data - timedelta(days=365)
    elif selected_period == "36개월":
        calc_start_date = max_date_in_data - timedelta(days=365*3)
    else: 
        calc_start_date = min_date_in_data

    if calc_start_date < min_date_in_data:
        start_date = min_date_in_data.date()
    else:
        start_date = calc_start_date.date()
        
    end_date = max_date_in_data.date()

    # --------------------------------------------------------------------------------
    # 4. 데이터 필터링 및 가공
    # --------------------------------------------------------------------------------
    # 1차: 날짜, 부위, 국가
    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date) & (df['part_clean'] == selected_part)
    if selected_country != '전체':
        mask = mask & (df['country'] == selected_country)
    
    # 2차: 브랜드 필터 적용 (선택된 UI 옵션에 따라 실제 필터링할 브랜드 리스트 생성)
    if selected_brand_ui == '전체':
        # '전체' 선택 시: 해당 부위의 모든 브랜드를 포함하여 '시장 평균' 산출
        target_brands = available_brands_in_data
        display_brand_name = "(시장 전체 평균)"
    else:
        # 특정 패커(예: 'IBP') 선택 시: 이름에 'IBP'가 포함된 브랜드만 필터링
        target_brands = [b for b in available_brands_in_data if selected_brand_ui in b]
        display_brand_name = f"- {selected_brand_ui}"
    
    mask = mask & (df['brand_clean'].isin(target_brands))
    
    filtered_df = df[mask].copy()

    # 평균 산출
    # 데이터가 없을 경우를 대비해 예외처리나 빈 차트 방지 로직이 필요할 수 있음
    if not filtered_df.empty:
        chart_df = filtered_df.groupby('date')[['wholesale_price', 'ma7', 'ma30', 'min_total']].mean().reset_index()
    else:
        chart_df = pd.DataFrame()
    
    # 화면 표시 이름 설정
    display_name = f"{selected_country} {selected_part} {display_brand_name}"

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
        # (1) KPI 카드 (3분할 구조 + 폰트 축소)
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

        # 괴리율 계산
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

        # 메시지 박스
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
            margin=dict(l=20, r=20, t=30, b=20)
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
    st.error("데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다. 먼저 데이터 파이프라인을 실행해주세요.")