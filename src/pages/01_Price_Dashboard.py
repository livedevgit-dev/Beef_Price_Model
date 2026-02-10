import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta

# [파일 정의서]
# - 파일명: 01_Price_Dashboard.py
# - 역할: 시각화 (상세 대시보드)
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
# - 주요 기능: 필터링(원산지/부위/브랜드), 시계열 차트, 이동평균선 비교

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
    st.error("데이터 파일을 찾을 수 없습니다. (data/2_dashboard/dashboard_ready_data.csv)")
    st.stop()

# --------------------------------------------------------------------------------
# 2. Session State 확인 (Home에서 넘어온 경우 처리)
# --------------------------------------------------------------------------------
default_category = "전체"
default_part = "전체"
default_brand = "전체"

if "target_product" in st.session_state:
    target = st.session_state["target_product"]
    # 데이터에 해당 값이 있는지 확인 후 설정
    if target['category'] in df['category'].unique():
        default_category = target['category']
    if target['part'] in df['part'].unique():
        default_part = target['part']
    if target['brand'] in df['brand'].unique():
        default_brand = target['brand']
    
    # 사용 후 세션 초기화 (새로고침 시 필터 풀림 방지를 위해 유지할 수도 있음)
    # del st.session_state["target_product"] 

# --------------------------------------------------------------------------------
# 3. 사이드바 필터링
# --------------------------------------------------------------------------------
st.sidebar.header("Filter Options")

# 3-1. 원산지 (Category) 선택
# 'country' 대신 'category' 컬럼 사용
category_list = ['전체'] + sorted(df['category'].unique().tolist())
# default_index 계산
cat_idx = 0
if default_category != "전체" and default_category in category_list:
    cat_idx = category_list.index(default_category)

selected_category = st.sidebar.selectbox("원산지 (Origin)", category_list, index=cat_idx)

# 3-2. 부위 (Part) 선택 - 원산지에 종속
if selected_category != '전체':
    filtered_df_cat = df[df['category'] == selected_category]
else:
    filtered_df_cat = df

part_list = ['전체'] + sorted(filtered_df_cat['part'].unique().tolist())
part_idx = 0
if default_part != "전체" and default_part in part_list:
    part_idx = part_list.index(default_part)

selected_part = st.sidebar.selectbox("부위 (Part)", part_list, index=part_idx)

# 3-3. 브랜드 (Brand) 선택 - 부위에 종속
if selected_part != '전체':
    filtered_df_part = filtered_df_cat[filtered_df_cat['part'] == selected_part]
else:
    filtered_df_part = filtered_df_cat

brand_list = ['전체'] + sorted(filtered_df_part['brand'].unique().tolist())
brand_idx = 0
if default_brand != "전체" and default_brand in brand_list:
    brand_idx = brand_list.index(default_brand)

selected_brand = st.sidebar.selectbox("브랜드 (Brand)", brand_list, index=brand_idx)

# --------------------------------------------------------------------------------
# 4. 데이터 필터링 및 시각화
# --------------------------------------------------------------------------------
# 최종 필터링
final_df = df.copy()
if selected_category != '전체':
    final_df = final_df[final_df['category'] == selected_category]
if selected_part != '전체':
    final_df = final_df[final_df['part'] == selected_part]
if selected_brand != '전체':
    final_df = final_df[final_df['brand'] == selected_brand]

st.title("📈 Beef Price Dashboard")
st.markdown(f"**Selected:** {selected_category} > {selected_part} > {selected_brand}")

if final_df.empty:
    st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
else:
    # 차트 그리기
    fig = px.line(
        final_df, 
        x='date', 
        y='wholesale_price', 
        color='brand',
        title=f"{selected_part} 가격 추이 ({selected_category})",
        labels={'wholesale_price': '도매가(원)', 'date': '날짜', 'brand': '브랜드'},
        hover_data=['ma7', 'ma30']
    )
    
    # 차트 스타일 개선
    fig.update_layout(
        xaxis_title="",
        yaxis_title="가격 (원)",
        legend_title="브랜드",
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # 데이터 테이블 표시
    with st.expander("데이터 상세 보기"):
        st.dataframe(final_df.sort_values(by='date', ascending=False))