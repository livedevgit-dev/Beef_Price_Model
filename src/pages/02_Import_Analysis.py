import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime, timedelta

# [파일 정의서]
# - 파일명: 02_Import_Analysis.py
# - 역할: 수입량 데이터 시각화
# - 데이터 소스: data/0_raw/master_import_volume.csv
# - 주요 기능: 국가별/부위별 교차 분석, YoY(전년 대비) 비교, 기간 필터링

# --------------------------------------------------------------------------------
# 1. 페이지 설정 및 데이터 로드
# --------------------------------------------------------------------------------
st.set_page_config(page_title="수입량 분석", page_icon="🚢", layout="wide")

@st.cache_data
def load_data():
    # 경로 설정 (pages 폴더 안에 있으므로 상위 폴더로 이동 필요)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    file_path = os.path.join(project_root, "data", "0_raw", "master_import_volume.csv")
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path)
    
    # 컬럼명 정리 ('부위별_' 접두어 제거 등 시각화용 전처리)
    # 현재 컬럼: std_date, 구분, 부위별_갈비_합계, ...
    
    # 멜트(Melt)를 통해 분석하기 좋은 형태로 변환 (Long Format)
    # 변환 후: [std_date, country, part, volume]
    id_vars = ['std_date', '구분']
    value_vars = [c for c in df.columns if '부위별_' in c and '계_합계' not in c] # '계'는 제외하고 부위만
    
    df_long = df.melt(id_vars=id_vars, value_vars=value_vars, var_name='part_raw', value_name='volume')
    
    # 전처리
    df_long['date'] = pd.to_datetime(df_long['std_date'])
    df_long['country'] = df_long['구분']
    df_long['part'] = df_long['part_raw'].str.replace('부위별_', '').str.replace('_합계', '')
    df_long['year'] = df_long['date'].dt.year
    df_long['month'] = df_long['date'].dt.month
    
    # 필요한 컬럼만 남기기
    final_df = df_long[['date', 'year', 'month', 'country', 'part', 'volume']].sort_values('date')
    
    return final_df

df = load_data()

if df is None:
    st.error("데이터 파일(master_import_volume.csv)을 찾을 수 없습니다.")
    st.stop()

# --------------------------------------------------------------------------------
# 2. 사이드바 (필터)
# --------------------------------------------------------------------------------
st.sidebar.header("📅 조회 설정")

# 기간 선택 버튼
period_options = ["3개월", "6개월", "12개월", "36개월", "전체"]
selected_period = st.sidebar.radio("조회 기간", period_options, index=2) # 기본 12개월

# 날짜 필터링 로직
max_date = df['date'].max()

if selected_period == "3개월":
    start_date = max_date - pd.DateOffset(months=3)
elif selected_period == "6개월":
    start_date = max_date - pd.DateOffset(months=6)
elif selected_period == "12개월":
    start_date = max_date - pd.DateOffset(months=12)
elif selected_period == "36개월":
    start_date = max_date - pd.DateOffset(months=36)
else:
    start_date = df['date'].min()

# 데이터 필터링 (기간 기준)
filtered_df = df[df['date'] >= start_date].copy()

# --------------------------------------------------------------------------------
# 3. KPI 요약 (전년 동기 대비)
# --------------------------------------------------------------------------------
st.title("🚢 수입 소고기 물량 분석")
st.markdown(f"**조회 기간:** {start_date.strftime('%Y-%m')} ~ {max_date.strftime('%Y-%m')}")

# KPI 계산을 위한 데이터 준비
current_month_date = max_date
last_year_date = max_date - pd.DateOffset(years=1)

# (1) 당월 총 수입량
curr_vol = df[df['date'] == current_month_date]['volume'].sum()
last_year_vol = df[df['date'] == last_year_date]['volume'].sum()

if last_year_vol > 0:
    yoy_pct = ((curr_vol - last_year_vol) / last_year_vol) * 100
else:
    yoy_pct = 0

# (2) 연간 누적(YTD) 수입량
current_year = max_date.year
curr_ytd_vol = df[df['year'] == current_year]['volume'].sum()
last_ytd_vol = df[(df['year'] == current_year - 1) & (df['date'] <= last_year_date)]['volume'].sum()

if last_ytd_vol > 0:
    ytd_pct = ((curr_ytd_vol - last_ytd_vol) / last_ytd_vol) * 100
else:
    ytd_pct = 0

# (3) 국가별 비중 (조회 기간 내)
total_period_vol = filtered_df['volume'].sum()
us_vol = filtered_df[filtered_df['country'] == '미국']['volume'].sum()
au_vol = filtered_df[filtered_df['country'] == '호주']['volume'].sum()

us_share = (us_vol / total_period_vol * 100) if total_period_vol > 0 else 0
au_share = (au_vol / total_period_vol * 100) if total_period_vol > 0 else 0

# KPI 카드 출력
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("당월 총 수입량", f"{int(curr_vol):,} ton", f"{yoy_pct:.1f}% (YoY)")
with col2:
    st.metric("연간 누적(YTD)", f"{int(curr_ytd_vol):,} ton", f"{ytd_pct:.1f}% (YoY)")
with col3:
    st.metric("미국산 비중", f"{us_share:.1f}%", f"{int(us_vol):,} ton")
with col4:
    st.metric("호주산 비중", f"{au_share:.1f}%", f"{int(au_vol):,} ton")

st.divider()

# --------------------------------------------------------------------------------
# 4. 상세 분석 (탭 구조)
# --------------------------------------------------------------------------------
tab1, tab2 = st.tabs(["🌏 국가별 분석 (Country View)", "🥩 부위별 분석 (Part View)"])

# [Tab 1] 국가별 분석: 특정 국가를 선택하면 그 나라의 부위별 구성을 보여줌
with tab1:
    st.subheader("국가별 수입 트렌드 및 부위 구성")
    
    # 국가 선택
    country_list = df['country'].unique().tolist()
    selected_country = st.selectbox("분석할 국가를 선택하세요:", country_list, index=0)
    
    # 해당 국가 데이터 필터링
    country_df = filtered_df[filtered_df['country'] == selected_country]
    
    # 차트 1: 월별 총 수입량 추이 (Line)
    daily_vol = country_df.groupby('date')['volume'].sum().reset_index()
    fig_line = px.line(daily_vol, x='date', y='volume', markers=True, 
                       title=f"{selected_country} 월별 총 수입량 추이")
    fig_line.update_layout(height=400)
    st.plotly_chart(fig_line, use_container_width=True)
    
    # 차트 2: 부위별 구성비 (Stacked Bar)
    # 너무 많은 부위가 있으면 복잡하므로, 상위 5개 외에는 '기타'로 묶을 수도 있음 (여기선 전체 표출)
    fig_bar = px.bar(country_df, x='date', y='volume', color='part', 
                     title=f"{selected_country} 부위별 수입 구성",
                     text_auto='.2s')
    fig_bar.update_layout(height=500, barmode='stack')
    st.plotly_chart(fig_bar, use_container_width=True)

# [Tab 2] 부위별 분석: 특정 부위를 선택하면 미국 vs 호주 경쟁 현황을 보여줌
with tab2:
    st.subheader("주요 부위별 국가 간 경쟁 현황")
    
    # 부위 선택
    part_list = sorted(df['part'].unique().tolist())
    # 기본값으로 '갈비'가 있으면 선택
    default_index = part_list.index('갈비') if '갈비' in part_list else 0
    selected_part = st.selectbox("분석할 부위를 선택하세요:", part_list, index=default_index)
    
    # 해당 부위 데이터 필터링
    part_df = filtered_df[filtered_df['part'] == selected_part]
    
    # 차트 1: 국가별 경쟁 추이 (Multi-Line)
    fig_comp = px.line(part_df, x='date', y='volume', color='country', markers=True,
                       title=f"{selected_part} - 국가별 수입량 비교")
    fig_comp.update_layout(height=450)
    st.plotly_chart(fig_comp, use_container_width=True)
    
    # 차트 2: 기간 내 점유율 (Pie Chart)
    total_part_vol = part_df.groupby('country')['volume'].sum().reset_index()
    fig_pie = px.pie(total_part_vol, values='volume', names='country', 
                     title=f"조회 기간 내 {selected_part} 국가별 점유율",
                     hole=0.4)
    st.plotly_chart(fig_pie, use_container_width=True)

# --------------------------------------------------------------------------------
# 5. 데이터 테이블 (다운로드용)
# --------------------------------------------------------------------------------
with st.expander("📊 원본 데이터 확인하기"):
    st.dataframe(filtered_df.sort_values(by=['date', 'country', 'part'], ascending=[False, True, True]), 
                 use_container_width=True)