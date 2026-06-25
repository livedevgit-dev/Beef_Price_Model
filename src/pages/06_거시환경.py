# [파일 정의서]
# - 파일명: 07_Macro_Environment.py
# - 역할: 시각화 (거시경제 환경 — 금리·CPI·PPI·옥수수·WTI)
# - 데이터 소스: data/1_processed/macro_indicators_daily.csv (long: value/ma30/yoy_pct/mom_pct)
# - 주요 기능:
#   - 사이드바: 지표(indicator) 다중선택 + 기간 선택
#   - 지표별 추이 차트(value + 30일 이동평균)
#   - 전년동월 대비(YoY) 추이
#   * 데이터(키 미설정 등)가 없으면 안내만 표시하고 graceful 하게 종료

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MACRO_PROCESSED_CSV

st.set_page_config(page_title="거시환경", page_icon="", layout="wide")


@st.cache_data
def load_data():
    if not MACRO_PROCESSED_CSV.exists():
        return None
    df = pd.read_csv(str(MACRO_PROCESSED_CSV), low_memory=False)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df


def main():
    st.title("거시경제 환경 (Macro)")
    st.caption("금리 · 물가(CPI) · PPI · 옥수수 · WTI 추이 — FRED / ECOS")

    df = load_data()
    if df is None:
        st.info(
            "거시지표 데이터가 아직 없습니다.\n\n"
            "`.env` 에 `FRED_API_KEY` / `ECOS_API_KEY` 를 설정한 뒤 아래를 실행하세요:\n\n"
            "```\n"
            "python src/collectors/collect_macro_fred.py\n"
            "python src/collectors/collect_macro_ecos.py\n"
            "python src/utils/preprocess_macro.py\n"
            "```"
        )
        return

    # indicator_id → 표시명 매핑
    name_map = (
        df.drop_duplicates("indicator_id")
        .set_index("indicator_id")["indicator_name"]
        .to_dict()
    )
    all_ids = sorted(df["indicator_id"].unique())

    # 사이드바
    st.sidebar.header("필터")
    selected = st.sidebar.multiselect(
        "지표 선택",
        options=all_ids,
        default=all_ids,
        format_func=lambda i: f"{i} — {name_map.get(i, '')}",
    )

    min_d = df["date"].min().date()
    max_d = df["date"].max().date()
    default_start = max(min_d, (df["date"].max() - timedelta(days=365 * 2)).date())
    date_range = st.sidebar.date_input(
        "기간",
        value=(default_start, max_d),
        min_value=min_d,
        max_value=max_d,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_d, end_d = date_range
    else:
        start_d, end_d = default_start, max_d

    if not selected:
        st.warning("지표를 1개 이상 선택하세요.")
        return

    mask = (
        df["indicator_id"].isin(selected)
        & (df["date"].dt.date >= start_d)
        & (df["date"].dt.date <= end_d)
    )
    view = df.loc[mask].copy()
    if view.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
        return

    # KPI: 지표별 최신값
    st.subheader("최신값")
    latest = view.sort_values("date").groupby("indicator_id").last()
    cols = st.columns(min(len(selected), 4) or 1)
    for idx, ind in enumerate(selected):
        if ind not in latest.index:
            continue
        row = latest.loc[ind]
        with cols[idx % len(cols)]:
            yoy = row.get("yoy_pct")
            delta = f"{yoy:+.1f}% YoY" if pd.notna(yoy) else None
            st.metric(
                label=f"{ind}",
                value=f"{row['value']:,.2f} {row.get('unit', '')}",
                delta=delta,
            )

    # 지표별 추이 (value + ma30)
    st.subheader("추이 (값 + 30일 이동평균)")
    for ind in selected:
        g = view[view["indicator_id"] == ind].sort_values("date")
        if g.empty:
            continue
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=g["date"], y=g["value"], name="값", mode="lines"))
        if "ma30" in g.columns:
            fig.add_trace(go.Scatter(x=g["date"], y=g["ma30"], name="MA30",
                                     mode="lines", line=dict(dash="dash")))
        fig.update_layout(
            title=f"{ind} — {name_map.get(ind, '')}",
            height=320, margin=dict(l=10, r=10, t=40, b=10),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, width="stretch")

    # YoY 비교
    if "yoy_pct" in view.columns:
        st.subheader("전년동월 대비 (YoY %)")
        fig = go.Figure()
        for ind in selected:
            g = view[view["indicator_id"] == ind].sort_values("date")
            fig.add_trace(go.Scatter(x=g["date"], y=g["yoy_pct"], name=ind, mode="lines"))
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10),
                          legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")


if __name__ == "__main__":
    main()
