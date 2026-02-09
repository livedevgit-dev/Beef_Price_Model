import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# [파일 정의서]
# - 파일명: Home.py
# - 역할: 시각화 (Dashboard Landing)
# - 대상: 공통
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
# - 수집/가공 주기: N/A
# - 주요 기능: 시스템 메인 화면, 주요 시세 등락 포착(Top 10 Compact View)

st.set_page_config(
    page_title="Beef Data Insight Platform",
    page_icon="🥩",
    layout="wide"
)

# --------------------------------------------------------------------------------
# 스타일 커스텀 (여백 줄이기)
# --------------------------------------------------------------------------------
st.markdown("""
    <style>
        /* 버튼 여백 최소화 */
        .stButton > button {
            height: 2em;
            padding-top: 0;
            padding-bottom: 0;
            min-height: 2.2rem;
        }
        /* 마크다운 텍스트 여백 줄이기 */
        .stMarkdown p {
            margin-bottom: 0.2rem;
        }
        /* 컬럼 간격 좁히기 */
        [data-testid="column"] {
            padding: 0;
        }
    </style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# 데이터 로드 함수 (캐싱 적용)
# --------------------------------------------------------------------------------
@st.cache_data
def load_dashboard_data():
    """정제된 dashboard_ready_data.csv 로드"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    file_path = os.path.join(project_root, "data", "2_dashboard", "dashboard_ready_data.csv")
    
    if not os.path.exists(file_path):
        return None
    
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    
    # 최근 날짜 기준 1년치 데이터 필터링
    latest_date = df['date'].max()
    one_year_ago = latest_date - timedelta(days=365)
    df = df[df['date'] >= one_year_ago].copy()
    
    return df

def calculate_market_highlights(df):
    """각 품목별 지표 계산 및 Top 10 추출"""
    if df is None or df.empty:
        return None, None
    
    # 그룹 기준: 원산지(category), 브랜드(brand), 부위(part)
    product_groups = df.groupby(['category', 'brand', 'part'])
    
    highlights = []
    
    for (category, brand, part), group_df in product_groups:
        if len(group_df) < 2: 
            continue
            
        latest_date = group_df['date'].max()
        current_price = group_df[group_df['date'] == latest_date]['wholesale_price'].mean()
        
        max_price_12m = group_df['wholesale_price'].max()
        min_price_12m = group_df['wholesale_price'].min()
        
        drop_rate = (current_price - max_price_12m) / max_price_12m if max_price_12m > 0 else 0
        rise_rate = (current_price - min_price_12m) / min_price_12m if min_price_12m > 0 else 0
        
        highlights.append({
            'category': category,
            'brand': brand,
            'part': part,
            'current_price': current_price,
            'max_12m': max_price_12m,
            'min_12m': min_price_12m,
            'drop_rate': drop_rate,
            'rise_rate': rise_rate
        })
    
    if not highlights:
        return None, None
    
    highlights_df = pd.DataFrame(highlights)
    
    # Top 10 추출
    top_drops = highlights_df.nsmallest(10, 'drop_rate')
    top_rises = highlights_df.nlargest(10, 'rise_rate')
    
    return top_drops, top_rises

# --------------------------------------------------------------------------------
# 메인 UI 구성
# --------------------------------------------------------------------------------
st.title("Beef Data Insight Platform")
st.divider()

# Market Highlights 섹션
st.subheader("📊 Market Highlights (Top 10)")
st.caption("최근 1년간 가격 변동폭이 큰 품목 (3대 패커 기준)")

df_dashboard = load_dashboard_data()

if df_dashboard is not None:
    top_drops, top_rises = calculate_market_highlights(df_dashboard)
    
    if top_drops is not None and top_rises is not None:
        col_drop, spacer, col_rise = st.columns([1, 0.05, 1]) # 가운데 여백(spacer) 추가
        
        # ------------------------------------------------------------------------
        # [Left Column] Top 10 Price Drop (📉)
        # ------------------------------------------------------------------------
        with col_drop:
            st.markdown("#### 📉 Price Drop Top 10")
            
            # 헤더
            h1, h2, h3, h4 = st.columns([3.5, 1.5, 1.5, 1])
            h1.markdown(":grey[**품목 (브랜드)**]")
            h2.markdown(":grey[**현재가**]")
            h3.markdown(":grey[**하락률**]")
            h4.markdown("")
            st.markdown("<hr style='margin: 0; border: none; border-bottom: 2px solid #ddd;'>", unsafe_allow_html=True)
            
            for idx, row in top_drops.iterrows():
                # 행 간격 조절을 위한 custom css div 사용 안함 (Streamlit native로 최대한 구현)
                c1, c2, c3, c4 = st.columns([3.5, 1.5, 1.5, 1])
                
                with c1:
                    # 마크다운으로 두 줄을 한 번에 써서 간격 줄임
                    st.markdown(f"**{row['part']}**<br><span style='font-size:0.8em; color:grey'>{row['brand']} ({row['category']})</span>", unsafe_allow_html=True)
                
                with c2:
                    st.markdown(f"<div style='padding-top:5px'>{int(row['current_price']):,}원</div>", unsafe_allow_html=True)
                    
                with c3:
                    st.markdown(f"<div style='color:blue; padding-top:5px'><b>{row['drop_rate']*100:.1f}%</b></div>", unsafe_allow_html=True)
                
                with c4:
                    if st.button("🔍", key=f"d_{idx}"):
                        st.session_state["target_product"] = {
                            "category": row['category'], "brand": row['brand'], "part": row['part']
                        }
                        st.switch_page("pages/01_Price_Dashboard.py")
                
                # [핵심] st.divider() 대신 얇은 HTML 선 사용 (margin 조절 가능)
                st.markdown("<hr style='margin: 0.2em 0; border: none; border-bottom: 1px solid #f0f0f0;'>", unsafe_allow_html=True)

        # ------------------------------------------------------------------------
        # [Right Column] Top 10 Price Rise (🚀)
        # ------------------------------------------------------------------------
        with col_rise:
            st.markdown("#### 🚀 Price Rise Top 10")
            
            # 헤더
            h1, h2, h3, h4 = st.columns([3.5, 1.5, 1.5, 1])
            h1.markdown(":grey[**품목 (브랜드)**]")
            h2.markdown(":grey[**현재가**]")
            h3.markdown(":grey[**상승률**]")
            h4.markdown("")
            st.markdown("<hr style='margin: 0; border: none; border-bottom: 2px solid #ddd;'>", unsafe_allow_html=True)
            
            for idx, row in top_rises.iterrows():
                c1, c2, c3, c4 = st.columns([3.5, 1.5, 1.5, 1])
                
                with c1:
                    st.markdown(f"**{row['part']}**<br><span style='font-size:0.8em; color:grey'>{row['brand']} ({row['category']})</span>", unsafe_allow_html=True)
                
                with c2:
                    st.markdown(f"<div style='padding-top:5px'>{int(row['current_price']):,}원</div>", unsafe_allow_html=True)
                    
                with c3:
                    st.markdown(f"<div style='color:red; padding-top:5px'><b>+{row['rise_rate']*100:.1f}%</b></div>", unsafe_allow_html=True)
                
                with c4:
                    if st.button("🔍", key=f"r_{idx}"):
                        st.session_state["target_product"] = {
                            "category": row['category'], "brand": row['brand'], "part": row['part']
                        }
                        st.switch_page("pages/01_Price_Dashboard.py")
                
                st.markdown("<hr style='margin: 0.2em 0; border: none; border-bottom: 1px solid #f0f0f0;'>", unsafe_allow_html=True)

    else:
        st.info("데이터가 충분하지 않아 순위를 계산할 수 없습니다.")
else:
    st.warning("⚠️ 데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다.")

st.markdown("---")

# 하단 네비게이션
c1, c2, c3 = st.columns(3)
c1.metric("📊 Price Analysis", "Active", "Update 09:00")
c2.metric("🚢 Import Volume", "Coming Soon", delta_color="off")
c3.metric("📦 Inventory", "Coming Soon", delta_color="off")