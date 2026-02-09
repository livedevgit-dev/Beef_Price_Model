import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py
# - 역할: 시각화 (사용자 인터페이스)
# - 대상: 공통
# - 데이터 소스: 1_processed/dashboard_ready_data.csv
# - 주요 기능: 필터링, KPI 카드, 반응형 차트 그리기

# --------------------------------------------------------------------------------
# 1. 페이지 기본 설정 (반드시 코드 최상단에 위치)
# --------------------------------------------------------------------------------
st.set_page_config(
    page_title="소고기 시세 대시보드",
    page_icon="--",
    layout="wide"  # 화면을 넓게 사용
)

# --------------------------------------------------------------------------------
# 2. 데이터 로드 함수 (캐싱 적용으로 속도 향상)
# --------------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 경로 설정: src/pages 폴더에서 실행됨을 가정하고 상위 폴더로 이동
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(src_dir)
    file_path = os.path.join(project_root, "data", "1_processed", "dashboard_ready_data.csv")
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    return df

# 데이터 불러오기
df = load_data()

# --------------------------------------------------------------------------------
# 3. Home에서 전달받은 target_product 처리
# --------------------------------------------------------------------------------
target_product = st.session_state.get("target_product", None)

# 자동 선택을 위한 기본값 설정
default_country = '전체'
default_part = None
default_brands = []

if target_product is not None and df is not None:
    # Home에서 전달받은 정보 추출
    target_category = target_product.get("category")
    target_brand = target_product.get("brand")
    target_part = target_product.get("part")
    
    # 매핑: category -> country, part -> part_clean 일부 매칭, brand -> brand_clean 일부 매칭
    # 원산지 설정
    if target_category in df['country'].unique():
        default_country = target_category
    
    # 부위 설정 (부분 매칭)
    if target_part:
        matching_parts = [p for p in df['part_clean'].unique() if target_part in p]
        if matching_parts:
            default_part = matching_parts[0]
    
    # 브랜드 설정 (부분 매칭)
    if target_brand and target_brand != 'N/A':
        matching_brands = [b for b in df['brand_clean'].unique() if target_brand in b]
        if matching_brands:
            default_brands = matching_brands

    # 사용 후 세션 상태 초기화 (다음 방문 시 영향 없도록)
    del st.session_state["target_product"]

# --------------------------------------------------------------------------------
# 4. 사이드바 (필터 영역)
# --------------------------------------------------------------------------------
st.sidebar.header("[FILTER] 검색 필터")

if df is not None:
    # (1) 국가 선택
    country_list = ['전체'] + sorted(df['country'].unique().tolist())
    
    # 기본값 설정: target_product가 있으면 해당 국가, 없으면 '전체'
    default_country_idx = 0
    if default_country != '전체' and default_country in country_list:
        default_country_idx = country_list.index(default_country)
    
    selected_country = st.sidebar.selectbox("원산지 선택", country_list, index=default_country_idx)

    # (2) 품목 선택
    if selected_country != '전체':
        part_options = sorted(df[df['country'] == selected_country]['part_clean'].unique())
    else:
        part_options = sorted(df['part_clean'].unique())
    
    # 기본값 설정: target_product가 있으면 해당 부위
    default_part_idx = 0
    if default_part and default_part in part_options:
        default_part_idx = part_options.index(default_part)
    
    selected_part = st.sidebar.selectbox("부위 선택", part_options, index=default_part_idx)

    # --------------------------------------------------------------------------------
    # (3) 브랜드 선택 (메이저 브랜드 자동 선택 기능)
    # --------------------------------------------------------------------------------
    # 해당 부위의 모든 브랜드 목록 추출
    available_brands = sorted(df[df['part_clean'] == selected_part]['brand_clean'].unique())
    
    # 핵심 로직: 기본 선택할 메이저 브랜드 키워드 정의
    major_keywords = ['IBP', '엑셀', '스위프트']
    
    # target_product에서 브랜드가 지정되었으면 해당 브랜드 우선 선택
    if default_brands and any(b in available_brands for b in default_brands):
        default_selection = [b for b in default_brands if b in available_brands]
    else:
        # 위 키워드가 이름에 포함된 브랜드만 찾아냄 (예: 'IBP(245)', '엑셀(86K)' 등)
        default_selection = [
            brand for brand in available_brands 
            if any(keyword in brand for keyword in major_keywords)
        ]
    
    # 만약 메이저 브랜드가 하나도 없는 품목이라면? -> 가장 상위 1개만 기본 선택 (빈 화면 방지)
    if not default_selection and available_brands:
        default_selection = [available_brands[0]]
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("[BRAND] 브랜드 필터")
    
    # 멀티 셀렉트 생성
    selected_brands_multi = st.sidebar.multiselect(
        "분석할 브랜드를 선택하세요 (메이저 자동 선택)",
        options=available_brands,
        default=default_selection,
        help="IBP, 엑셀, 스위프트는 기본 선택됩니다. 다른 브랜드는 클릭하여 추가하세요."
    )
    
    # 사용자가 다 지워서 하나도 선택 안 했을 경우 방어 로직
    if not selected_brands_multi:
        st.sidebar.error("최소 1개 이상의 브랜드를 선택해주세요.")
        # 강제로 메이저 리스트 혹은 첫 번째 것 선택
        if default_selection:
            selected_brands_multi = default_selection
        else:
            selected_brands_multi = available_brands[:1]

    # (4) 기간 선택
    st.sidebar.subheader("[DATE] 조회 기간")
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
    # 4. 데이터 필터링 로직
    # --------------------------------------------------------------------------------
    mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date) & (df['part_clean'] == selected_part)
    if selected_country != '전체':
        mask = mask & (df['country'] == selected_country)
    
    # 브랜드 필터 적용
    mask = mask & (df['brand_clean'].isin(selected_brands_multi))
    
    filtered_df = df[mask].copy()

    # 평균 산출
    chart_df = filtered_df.groupby('date')[['wholesale_price', 'ma7', 'ma30', 'min_total']].mean().reset_index()
    
    # 화면 표시 이름 설정 (타이틀용)
    if len(selected_brands_multi) == len(available_brands):
        display_name = f"{selected_country} {selected_part} (전체 평균)"
    elif len(selected_brands_multi) == 1:
        display_name = f"{selected_country} {selected_part} - {selected_brands_multi[0]}"
    else:
        # 선택된 브랜드가 여러 개일 때, 메이저 위주인지 확인
        is_major_only = all(any(k in b for k in major_keywords) for b in selected_brands_multi)
        if is_major_only:
            display_name = f"{selected_country} {selected_part} (메이저 3사 평균)"
        else:
            display_name = f"{selected_country} {selected_part} (선택 브랜드 평균)"

    # --------------------------------------------------------------------------------
    # 5. 메인 대시보드 화면 구성
    # --------------------------------------------------------------------------------
    st.title(f"[PRICE] {display_name} 시세 분석")
    st.markdown(f"기간: {start_date} ~ {end_date}")

    # 폰트 사이즈를 줄이는 CSS 주입
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
            st.success(f"[OK] **매수 기회!** 최저가({min_price_period:,}원)에 근접")
        elif current_price >= (max_price_period * 0.95):
            st.warning(f"[ALERT] **고점 주의!** 최고가({max_price_period:,}원)에 근접")
        else:
            st.info("비교적 평이한 가격 흐름입니다.")

        st.divider()

        # (2) 메인 차트 (Plotly)
        st.subheader("[CHART] 시세 추세 및 이동평균선")
        
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
        with st.expander("[DATA] 상세 데이터 보기 (클릭하여 펼치기)"):
            display_cols = ['date', 'wholesale_price', 'ma7', 'ma30']
            st.dataframe(chart_df[display_cols].sort_values(by='date', ascending=False),
                         use_container_width=True)
            
    else:
        st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")

else:
    st.error("데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다. 먼저 데이터 파이프라인을 실행해주세요.")
