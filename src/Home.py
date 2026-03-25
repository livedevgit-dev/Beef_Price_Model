import streamlit as st
import pandas as pd
from datetime import timedelta

from config import DASHBOARD_READY_CSV

# [파일 정의서]
# - 파일명: Home.py
# - 역할: 시각화 (Dashboard Landing)
# - 대상: 공통
# - 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
# - 주요 기능: 시스템 메인 화면, 부위별 시세 변동 요약 테이블 (거시적 뷰)

st.set_page_config(
    page_title="Beef Data Insight Platform",
    page_icon="🥩",
    layout="wide"
)

# --------------------------------------------------------------------------------
# 데이터 로드 함수 (캐싱 적용)
# --------------------------------------------------------------------------------
@st.cache_data
def load_dashboard_data():
    """정제된 dashboard_ready_data.csv 로드"""
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(str(DASHBOARD_READY_CSV))
    df['date'] = pd.to_datetime(df['date'])
    return df

# --------------------------------------------------------------------------------
# 메인 UI 구성
# --------------------------------------------------------------------------------
st.title("Beef Data Insight Platform")
st.divider()

st.subheader("📉 부위별 시세 변동 요약")

df = load_dashboard_data()

if df is not None:
    # 브랜드 통합 평균 가격: 날짜 × 부위별 groupby
    df_avg = df.groupby(['date', 'part'])['wholesale_price'].mean().reset_index()

    latest_date = df_avg['date'].max()
    st.markdown(f"**기준일:** {latest_date.strftime('%Y-%m-%d')} | **기준:** 브랜드 통합 평균가")

    date_3m = latest_date - timedelta(days=90)
    date_6m = latest_date - timedelta(days=180)
    date_12m = latest_date - timedelta(days=365)

    part_options = sorted(df_avg['part'].unique())
    summary_list = []

    for part_name in part_options:
        part_df = df_avg[df_avg['part'] == part_name].sort_values('date')

        # 현재 가격: latest_date 기준 과거 7일 이내 유효한 최신 가격
        recent_window = part_df[
            (part_df['date'] >= latest_date - timedelta(days=7))
            & (part_df['date'] <= latest_date)
            & (part_df['wholesale_price'].notna())
            & (part_df['wholesale_price'] != 0)
        ].sort_values('date', ascending=False)
        if recent_window.empty:
            continue
        curr_price = recent_window.iloc[0]['wholesale_price']

        def get_price_at_date(target_date):
            window_start = target_date - timedelta(days=7)
            window_end = target_date + timedelta(days=7)
            window_data = part_df[
                (part_df['date'] >= window_start) & (part_df['date'] <= window_end)
            ]['wholesale_price'].dropna()
            if window_data.empty:
                return None
            return window_data.mean()

        price_3m = get_price_at_date(date_3m)
        price_6m = get_price_at_date(date_6m)
        price_12m = get_price_at_date(date_12m)

        def calc_pct(curr, past):
            if past is None or past == 0:
                return None
            return ((curr - past) / past) * 100

        summary_list.append({
            "부위": part_name,
            "현재가": curr_price,
            "3개월 전 대비": calc_pct(curr_price, price_3m),
            "6개월 전 대비": calc_pct(curr_price, price_6m),
            "1년 전 대비": calc_pct(curr_price, price_12m),
            "_sort_key": calc_pct(curr_price, price_6m) if price_6m else 0
        })

    df_summary = pd.DataFrame(summary_list)

    if not df_summary.empty:
        df_summary = df_summary.sort_values(by="_sort_key", ascending=True)
        df_display = df_summary.drop(columns=["_sort_key"])

        def style_variance(val):
            if pd.isna(val):
                return ""
            if val > 0:
                return 'color: #D32F2F; background-color: #FFEBEE; font-weight: bold'
            elif val < 0:
                return 'color: #1976D2; background-color: #E3F2FD; font-weight: bold'
            return ""

        def format_pct(val):
            if pd.isna(val):
                return "-"
            return f"{val:+.1f}%"

        st.dataframe(
            df_display.style
            .format({"현재가": "{:,.0f}원"})
            .format(format_pct, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"])
            .map(style_variance, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"]),
            use_container_width=True,
            height=(len(df_display) + 1) * 35 + 3,
            hide_index=True
        )

        st.info("💡 **Tip:** '6개월 전 대비' 하락폭이 큰 순서대로 정렬되어 있습니다. 브랜드별 상세 분석은 Price Dashboard에서 확인하세요.")
    else:
        st.warning("분석할 데이터가 충분하지 않습니다.")
else:
    st.warning("⚠️ 데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다.")

st.markdown("---")

# 하단 네비게이션
c1, c2, c3 = st.columns(3)
c1.metric("📊 Price Analysis", "Active", "Update 09:00")
c2.metric("🚢 Import Volume", "Coming Soon", delta_color="off")
c3.metric("📦 Inventory", "Coming Soon", delta_color="off")
