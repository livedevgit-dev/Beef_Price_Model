import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import BEEF_STOCK_XLSX, MASTER_IMPORT_VOLUME_CSV

# [파일 정의서]
# - 파일명: 03_Inventory_Management.py
# - 역할: 재고 현황 요약 및 부위별 상세 시계열 분석
# - 업데이트: 수입량 '합계' 데이터 생성 로직 추가 (라인 차트 미표출 오류 해결)

# --------------------------------------------------------------------------------
# 1. 페이지 및 데이터 로드 설정
# --------------------------------------------------------------------------------
st.set_page_config(page_title="재고 관리 및 수급 분석", page_icon="🏭", layout="wide")

def _data_files_mtime():
    """재고/수입 데이터 파일의 최종 수정 시각. 캐시 키로 사용해 파일 갱신 시 자동 재로드."""
    t1 = BEEF_STOCK_XLSX.stat().st_mtime if BEEF_STOCK_XLSX.exists() else 0
    t2 = MASTER_IMPORT_VOLUME_CSV.stat().st_mtime if MASTER_IMPORT_VOLUME_CSV.exists() else 0
    return max(t1, t2)

@st.cache_data
def load_data(_cache_key):
    """
    재고(Inventory) 및 수입(Import) 데이터를 로드하고 전처리합니다.
    _cache_key: 파일 수정 시각으로, 크롤러 등으로 CSV가 갱신되면 캐시가 갱신됩니다.
    """
    if not BEEF_STOCK_XLSX.exists():
        return None, None

    try:
        df_inv = pd.read_excel(str(BEEF_STOCK_XLSX))
    except:
        df_inv = pd.read_csv(str(BEEF_STOCK_XLSX))

    col_map = {}
    for col in df_inv.columns:
        if '기준년월' in col: col_map[col] = 'date'
        elif '부위별' in col: col_map[col] = 'part'
        elif '조사재고량' in col: col_map[col] = 'inventory'
    
    df_inv = df_inv.rename(columns=col_map)
    
    if 'inventory' in df_inv.columns:
        df_inv = df_inv[~df_inv['inventory'].astype(str).str.contains("없습니다|자료가", na=False)]
        df_inv['inventory'] = df_inv['inventory'].astype(str).str.replace(',', '').astype(float)
    
    df_inv['date'] = pd.to_datetime(df_inv['date'])
    
    # --- 2. 수입량 데이터 로드 ---
    df_imp = pd.DataFrame()
    if MASTER_IMPORT_VOLUME_CSV.exists():
        df_imp = pd.read_csv(str(MASTER_IMPORT_VOLUME_CSV))
        df_imp['date'] = pd.to_datetime(df_imp['std_date'])
        
        # Melt 수행
        id_vars = ['date', '구분']
        val_vars = [c for c in df_imp.columns if '부위별_' in c and '계_합계' not in c]
        
        if val_vars:
            df_melt = df_imp.melt(id_vars=id_vars, value_vars=val_vars, var_name='part_raw', value_name='import_vol')
            df_melt['part'] = df_melt['part_raw'].str.replace('부위별_', '').str.replace('_합계', '')
            
            # (1) 부위별 합계 (국가 구분 없이 합침)
            df_by_part = df_melt.groupby(['date', 'part'])['import_vol'].sum().reset_index()
            
            # (2) [수정] 전체 합계(Total) 계산 후 추가
            df_total = df_melt.groupby('date')['import_vol'].sum().reset_index()
            df_total['part'] = '합계'
            
            # (3) 데이터 병합
            df_imp = pd.concat([df_by_part, df_total], ignore_index=True)

    return df_inv, df_imp

df_inv, df_imp = load_data(_data_files_mtime())

if df_inv is None:
    st.error("재고 데이터 파일이 없습니다.")
    st.stop()

# --------------------------------------------------------------------------------
# 2. 사이드바 (필터링 컨트롤)
# --------------------------------------------------------------------------------
st.sidebar.header("🥩 부위 선택")

# 2-1. 부위 선택
raw_parts = [p for p in df_inv['part'].unique() if p not in ['합계', '기타', '부산물']]
options = ["전체 보기"] + raw_parts
selected_option = st.sidebar.selectbox("분석할 부위", options, index=0)

# 선택에 따른 필터링 타겟 설정
if selected_option == "전체 보기":
    target_parts_for_table = ['합계'] + raw_parts
    chart_target_part = '합계'
else:
    target_parts_for_table = [selected_option]
    chart_target_part = selected_option

# 2-2. 기간 선택
st.sidebar.markdown("---")
period_option = st.sidebar.radio(
    "조회 기간",
    ["6개월", "12개월", "36개월", "전체"],
    index=1 
)

# --------------------------------------------------------------------------------
# 3. 데이터 필터링 로직
# --------------------------------------------------------------------------------
latest_date = df_inv['date'].max()
start_date = df_inv['date'].min()

if period_option == "6개월":
    start_date = latest_date - pd.DateOffset(months=5)
elif period_option == "12개월":
    start_date = latest_date - pd.DateOffset(months=11)
elif period_option == "36개월":
    start_date = latest_date - pd.DateOffset(months=35)

df_inv_filtered = df_inv[df_inv['date'] >= start_date].copy()
df_imp_filtered = df_imp[df_imp['date'] >= start_date].copy() if not df_imp.empty else pd.DataFrame()

# --------------------------------------------------------------------------------
# 4. 메인 화면: 인사이트 테이블
# --------------------------------------------------------------------------------
st.title("🏭 재고(Inventory) 인사이트")
st.markdown(f"**기준 시점:** {latest_date.strftime('%Y년 %m월')} (최신 업데이트)")
st.caption("💡 기준 시점은 재고 데이터(beef_stock_data.xlsx) 기준입니다. 최신 월이 안 나오면 `src/collectors/crawl_imp_stock_monthly.py`를 실행한 뒤 이 페이지를 새로고침하세요.")

# 날짜 계산
date_3m_ago = latest_date - pd.DateOffset(months=3)
date_6m_ago = latest_date - pd.DateOffset(months=6)
date_12m_ago = latest_date - pd.DateOffset(months=12)

# 요약 테이블 생성 함수
def calculate_changes_list(df, target_date, comp_dates, target_parts):
    data_list = []
    
    for part in target_parts:
        part_df = df[df['part'] == part]
        curr_row = part_df[part_df['date'] == target_date]
        if curr_row.empty: continue
        curr_val = curr_row['inventory'].values[0]
        
        row_dict = {
            "부위": part,
            "현재고(톤)": curr_val
        }
        
        for label, comp_date in comp_dates.items():
            comp_row = part_df[part_df['date'] == comp_date]
            if not comp_row.empty:
                prev_val = comp_row['inventory'].values[0]
                pct = ((curr_val - prev_val) / prev_val) * 100 if prev_val > 0 else 0
                row_dict[label] = pct
            else:
                row_dict[label] = None
        
        data_list.append(row_dict)
    return pd.DataFrame(data_list)

comp_dates = {
    "3개월 전 대비": date_3m_ago,
    "6개월 전 대비": date_6m_ago,
    "1년 전 대비": date_12m_ago
}

df_insight = calculate_changes_list(df_inv, latest_date, comp_dates, target_parts_for_table)

# --- [스타일링: 주식 시장 스타일] ---
def format_trend_text(val):
    if pd.isna(val): return "-"
    if val > 0:
        return f"{val:,.1f}% 상승"
    elif val < 0:
        return f"{abs(val):,.1f}% 하락"
    else:
        return "변동 없음"

def color_variant(val):
    if pd.isna(val): return ''
    if val > 0:
        # 🔴 상승 (재고 증가) = 경고성 붉은색
        return 'background-color: #FFEBEE; color: #D32F2F; font-weight: bold'
    elif val < 0:
        # 🔵 하락 (재고 감소) = 안정성 파란색
        return 'background-color: #E3F2FD; color: #1976D2; font-weight: bold'
    return ''

st.subheader(f"📋 {selected_option} 재고 변동 현황")

table_height = (len(df_insight) + 1) * 35 + 3

st.dataframe(
    df_insight.style
    .format({"현재고(톤)": "{:,.0f}"})
    .format(format_trend_text, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"])
    .map(color_variant, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"]),
    use_container_width=True,
    height=table_height,
    hide_index=True
)

st.caption("※ 배경색 가이드: 🔴 붉은색(재고 상승/증가), 🔵 파란색(재고 하락/감소)")
st.divider()

# --------------------------------------------------------------------------------
# 5. 상세 분석 탭
# --------------------------------------------------------------------------------
chart_title_part = "전체 합계(Total)" if selected_option == "전체 보기" else selected_option

tab1, tab2 = st.tabs(["📊 상세 추이 분석", "⚖️ 수입 vs 재고 비교"])

# [Tab 1] 재고 추이 (막대 차트)
with tab1:
    st.subheader(f"{chart_title_part} 재고 추이 ({period_option})")
    
    chart_data = df_inv_filtered[df_inv_filtered['part'] == chart_target_part].sort_values('date')
    
    if chart_data.empty:
        st.info("표시할 데이터가 없습니다.")
    else:
        fig = px.bar(chart_data, x='date', y='inventory',
                    title=f"{chart_title_part} 월별 재고량",
                    text_auto=',.0f',
                    labels={'date': '기준년월', 'inventory': '재고량(톤)'})
        
        fig.update_xaxes(dtick="M1", tickformat="%Y-%m", tickangle=-45)
        # 색상: 인디고 계열 (중립적)
        fig.update_traces(marker_color='#5C6BC0') 
        
        st.plotly_chart(fig, use_container_width=True)

# [Tab 2] 수입 vs 재고 (재고=Bar, 수입=Line)
with tab2:
    st.subheader(f"{chart_title_part} 수급(Supply vs Stock) 분석")
    
    if df_imp_filtered.empty:
        st.warning(f"'{chart_target_part}'에 대한 수입량 데이터가 없습니다.")
    else:
        # 데이터 추출
        inv_series = df_inv_filtered[df_inv_filtered['part'] == chart_target_part].set_index('date')['inventory']
        imp_series = df_imp_filtered[df_imp_filtered['part'] == chart_target_part].set_index('date')['import_vol']
        
        # 병합 (Index 기준 Outer Join)
        merged = pd.concat([inv_series, imp_series], axis=1).sort_index()
        merged.columns = ['재고량(톤)', '수입량(kg)']
        
        # 차트 그리기
        fig_dual = go.Figure()
        
        # 1. 재고량 (Bar) - Base
        fig_dual.add_trace(go.Bar(
            x=merged.index, 
            y=merged['재고량(톤)'],
            name='재고량(톤)', 
            marker_color='#90CAF9', # 연한 파랑
            opacity=0.6,
            yaxis='y1'
        ))
        
        # 2. 수입량 (Line) - Trend
        # 데이터가 끊겨 보이지 않도록 connectgaps=True 옵션 고려 가능하나, 
        # 데이터의 신뢰성을 위해 있는 데이터만 점으로 연결
        fig_dual.add_trace(go.Scatter(
            x=merged.index, 
            y=merged['수입량(kg)'],
            name='수입량(kg)', 
            mode='lines+markers',
            line=dict(color='#D32F2F', width=3), # 붉은 선
            yaxis='y2'
        ))
        
        fig_dual.update_layout(
            title=f"{chart_title_part} - 재고량(막대) vs 수입량(선) 비교",
            xaxis=dict(
                tickformat="%Y-%m",
                dtick="M1" if period_option in ["6개월", "12개월"] else "M3"
            ),
            # Y축 1 (왼쪽: 재고량)
            yaxis=dict(
                title="재고량 (톤)", 
                side='left',
                showgrid=False
            ),
            # Y축 2 (오른쪽: 수입량)
            yaxis2=dict(
                title="수입량 (kg)", 
                side='right', 
                overlaying='y',
                showgrid=False
            ),
            legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.5)'),
            hovermode="x unified"
        )
        
        st.plotly_chart(fig_dual, use_container_width=True)
        
        # 데이터 시차 안내 문구
        if not merged['재고량(톤)'].dropna().empty:
            last_inv_date = merged['재고량(톤)'].dropna().index.max().strftime('%Y-%m')
            st.caption(f"💡 참고: 재고 데이터는 {last_inv_date}까지만 제공됩니다. (이후 구간은 수입량만 표시됨)")