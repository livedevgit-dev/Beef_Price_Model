import streamlit as st
import pandas as pd
import plotly.express as px
import os

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py
# - 역할: 시각화 (상세 대시보드)
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
# - 주요 기능: 3대 패커 평균 대비 브랜드별 가격 비교

st.set_page_config(page_title="Price Dashboard", page_icon="📈", layout="wide")

# --------------------------------------------------------------------------------
# 1. 데이터 로드
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
    st.error("데이터 파일을 찾을 수 없습니다.")
    st.stop()

# --------------------------------------------------------------------------------
# 2. 필터링 로직 (Home 연동)
# --------------------------------------------------------------------------------
default_cat, default_part, default_brand = "전체", "전체", "전체"

if "target_product" in st.session_state:
    target = st.session_state["target_product"]
    if target['category'] in df['category'].unique():
        default_cat = target['category']
    if target['part'] in df['part'].unique():
        default_part = target['part']
    if target['brand'] in df['brand'].unique():
        default_brand = target['brand']

# --------------------------------------------------------------------------------
# 3. 사이드바 설정
# --------------------------------------------------------------------------------
st.sidebar.header("Filter Options")

# 원산지
cat_list = ['전체'] + sorted(df['category'].unique().tolist())
cat_idx = cat_list.index(default_cat) if default_cat in cat_list else 0
sel_cat = st.sidebar.selectbox("원산지 (Origin)", cat_list, index=cat_idx)

# 부위 (원산지 종속)
if sel_cat != '전체':
    df_cat = df[df['category'] == sel_cat]
else:
    df_cat = df

part_list = ['전체'] + sorted(df_cat['part'].unique().tolist())
part_idx = part_list.index(default_part) if default_part in part_list else 0
sel_part = st.sidebar.selectbox("부위 (Part)", part_list, index=part_idx)

# 브랜드 (부위 종속)
if sel_part != '전체':
    df_part = df_cat[df_cat['part'] == sel_part]
else:
    df_part = df_cat

brand_list = ['전체'] + sorted(df_part['brand'].unique().tolist())
brand_idx = brand_list.index(default_brand) if default_brand in brand_list else 0
sel_brand = st.sidebar.selectbox("브랜드 (Brand)", brand_list, index=brand_idx)

# --------------------------------------------------------------------------------
# 4. 차트 데이터 가공 (핵심 로직 변경)
# --------------------------------------------------------------------------------
st.title("📈 Beef Price Dashboard")
st.markdown(f"**Selected:** {sel_cat} > {sel_part} > {sel_brand}")

# 4-1. 기본 데이터 필터링 (원산지, 부위까지만)
base_df = df.copy()
if sel_cat != '전체':
    base_df = base_df[base_df['category'] == sel_cat]
if sel_part != '전체':
    base_df = base_df[base_df['part'] == sel_part]

if base_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
else:
    # 4-2. [Baseline] 3대 패커 평균 계산
    major_keywords = ['IBP', 'Excel', 'Swift', '엑셀', '스위프트']
    mask_major = base_df['brand'].str.contains('|'.join(major_keywords), case=False)
    
    df_major = base_df[mask_major]
    
    # 날짜별 평균 산출
    if not df_major.empty:
        major_daily = df_major.groupby('date')['wholesale_price'].mean().reset_index()
        major_daily['brand'] = 'Major 3 Avg (IBP/Excel/Swift)' # 범례 이름
        major_daily['type'] = 'Baseline'
    else:
        major_daily = pd.DataFrame() # 3대 패커 데이터가 없는 부위일 경우

    # 4-3. [Comparison] 비교 대상 데이터 준비
    plot_df = major_daily.copy() # 일단 3대 패커 평균을 넣음
    
    if sel_brand == '전체':
        # 전체 선택 시: 시장 전체 평균(Market Avg)을 비교 대상으로 추가
        market_daily = base_df.groupby('date')['wholesale_price'].mean().reset_index()
        market_daily['brand'] = 'Market Avg (Total)'
        market_daily['type'] = 'Comparison'
        
        # 3대 패커 데이터가 있으면 합치고, 없으면 시장 평균만 보여줌
        if not plot_df.empty:
            plot_df = pd.concat([plot_df, market_daily])
        else:
            plot_df = market_daily
            
    else:
        # 특정 브랜드 선택 시: 해당 브랜드 데이터만 추가
        target_df = base_df[base_df['brand'] == sel_brand].copy()
        target_df['type'] = 'Comparison'
        
        # 날짜별로 데이터가 여러 개일 수 있으니(같은 브랜드 다른 스펙 등) 평균 처리
        target_daily = target_df.groupby('date')['wholesale_price'].mean().reset_index()
        target_daily['brand'] = sel_brand # 범례 이름 유지
        
        plot_df = pd.concat([plot_df, target_daily])

    # --------------------------------------------------------------------------------
    # 5. 시각화
    # --------------------------------------------------------------------------------
    # 색상 지정: Major 3는 파란색/검정색 계열, 비교 대상은 빨간색 계열
    color_map = {
        'Major 3 Avg (IBP/Excel/Swift)': '#1f77b4', # 파란색
        'Market Avg (Total)': '#ff7f0e',           # 주황색
        sel_brand: '#d62728'                       # 빨간색 (선택 브랜드)
    }

    fig = px.line(
        plot_df, 
        x='date', 
        y='wholesale_price', 
        color='brand',
        title=f"{sel_part} 가격 비교: 3대 패커 vs {sel_brand}",
        color_discrete_map=color_map
    )

    # 라인 스타일 커스텀
    fig.update_traces(line=dict(width=3)) # 선 굵게
    fig.update_layout(
        xaxis_title="",
        yaxis_title="도매가 (원/kg)",
        legend_title="구분",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    # --------------------------------------------------------------------------------
    # 6. 상세 데이터 테이블 (옵션)
    # --------------------------------------------------------------------------------
    with st.expander("📊 데이터 상세 보기"):
        st.caption("선택한 조건의 Raw Data입니다.")
        # 테이블은 필터링된 원본을 보여줌
        display_df = base_df.copy()
        if sel_brand != '전체':
            display_df = display_df[display_df['brand'] == sel_brand]
        
        st.dataframe(
            display_df[['date', 'category', 'part', 'brand', 'wholesale_price']]
            .sort_values(by='date', ascending=False)
            .reset_index(drop=True),
            use_container_width=True
        )