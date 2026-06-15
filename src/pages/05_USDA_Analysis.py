# [파일 정의서]
# - 파일명: 05_USDA_Analysis.py
# - 역할: 시각화 (미국 USDA 도매가 시세)
# - 데이터 소스: data/1_processed/processed_usda_cost.csv (LM_XB403 환율 반영)
# - 주요 기능: Price Dashboard와 동일한 구조로 USDA 부위별 도매가 시세 표출
#   - 사이드바: 등급(Choice/Select 등) → 부위 → 기간 선택
#   - 전체 보기: 1년 기준 가격 변동폭이 큰 부위 Top 랭킹 (Drop / Rise)
#   - 상세 보기: KPI(현재가/기간 최고·최저) + 가격 추이 차트(7일·30일 이평선)

import re
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROCESSED_USDA_COST_CSV
from utils.part_mapping import USDA_CODE_TO_CANONICAL, get_part

# 거래 데이터가 너무 희박한 부위는 신뢰성이 낮으므로 Highlights에서 제외
# 최근 1년 기준 유효 가격(NaN/0 제외) 비율이 이 값 미만이면 후보에서 제외
MIN_DATA_COVERAGE = 0.3

st.set_page_config(page_title="USDA 도매가 시세", page_icon="", layout="wide")

USDA_CODE_PATTERN = re.compile(r"\(\s*([0-9]+[A-Z]?)\s+")

# USDA 원본에서 코드 표기가 누락된 항목용 키워드 폴백
# (예: 'Loin, strip loin bnls. 1x1 (  1)', 'Round, top inside, side off (  3)')
DESCRIPTION_KEYWORD_FALLBACK: tuple[tuple[str, str], ...] = (
    ("strip loin", "striploin"),
    ("top inside", "round"),
)


def _extract_code(description: str) -> str:
    m = USDA_CODE_PATTERN.search(str(description))
    return m.group(1).strip() if m else ""


def _korean_label(code: str, description: str = "") -> str:
    canonical_id = USDA_CODE_TO_CANONICAL.get(code)
    if not canonical_id and description:
        desc_lower = description.lower()
        for keyword, fallback_id in DESCRIPTION_KEYWORD_FALLBACK:
            if keyword in desc_lower:
                canonical_id = fallback_id
                break
    if not canonical_id:
        return ""
    spec = get_part(canonical_id)
    return spec.name_ko if spec else ""


@st.cache_data
def load_data():
    if not PROCESSED_USDA_COST_CSV.exists():
        return None
    usecols = [
        "Date", "item_description", "grade",
        "weighted_average_USD_kg", "Exchange_Rate",
    ]
    df = pd.read_csv(str(PROCESSED_USDA_COST_CSV), usecols=usecols, low_memory=False)
    df["date"] = pd.to_datetime(df["Date"])
    df = df.dropna(subset=["item_description"])

    # USDA 원본의 빈 가격이 전처리 과정에서 0으로 채워진 케이스를 결측치로 복원
    df["weighted_average_USD_kg"] = df["weighted_average_USD_kg"].replace(0, pd.NA)
    df["weighted_average_USD_kg"] = pd.to_numeric(df["weighted_average_USD_kg"], errors="coerce")

    df["usda_code"] = df["item_description"].astype(str).apply(_extract_code)
    df["korean_name"] = df.apply(
        lambda r: _korean_label(r["usda_code"], str(r["item_description"])), axis=1
    )

    def display_name(row):
        desc = str(row["item_description"]).strip()
        if row["korean_name"]:
            return f"[{row['korean_name']}] {desc}"
        return desc

    df["display_name"] = df.apply(display_name, axis=1)
    df["price_krw_kg"] = df["weighted_average_USD_kg"] * df["Exchange_Rate"]
    return df


df = load_data()
if df is None or df.empty:
    st.error(
        "USDA 도매가 데이터(processed_usda_cost.csv)를 찾을 수 없습니다. "
        "`python src/run_daily_update.py --full`을 먼저 실행하세요."
    )
    st.stop()

# --------------------------------------------------------------------------------
# 사이드바
# --------------------------------------------------------------------------------
st.sidebar.header("검색 필터")

grade_list = sorted(df["grade"].dropna().unique().tolist())
grade_default_index = grade_list.index("Choice") if "Choice" in grade_list else 0
selected_grade = st.sidebar.selectbox("등급(Grade) 선택", grade_list, index=grade_default_index)
df_grade = df[df["grade"] == selected_grade].copy()

# 표시 단위는 USD/kg 고정. 원/kg는 상세 차트에서 보조축으로 표출.
value_col = "weighted_average_USD_kg"
unit_label = "USD/kg"

def _part_sort_key(name: str):
    # 한글 라벨이 붙은 부위([..]로 시작)를 우선 노출
    has_korean = name.startswith("[")
    return (0 if has_korean else 1, name)


part_options = sorted(df_grade["display_name"].dropna().unique(), key=_part_sort_key)
selected_part = st.sidebar.selectbox(
    "부위(Cut) 선택",
    ["전체 보기 (가격 동향 요약)"] + part_options,
)


def _fmt_usd(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"${value:,.2f}"


def _fmt_usd_diff(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"${value:+,.2f}"


# --------------------------------------------------------------------------------
# CASE A: 전체 보기 (Highlights)
# --------------------------------------------------------------------------------
if selected_part == "전체 보기 (가격 동향 요약)":
    st.title("USDA Market Highlights")
    st.caption(
        f"최근 1년간 가격 변동폭이 큰 부위 (등급: {selected_grade}, 단위: {unit_label}). "
        f"거래 데이터가 30% 미만인 부위는 신뢰도가 낮아 제외됩니다."
    )

    st.markdown(
        """
        <style>
        .stMarkdown p { margin-bottom: 0.2rem; }
        [data-testid="column"] { padding: 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    latest_date = df_grade["date"].max()
    active_cutoff = latest_date - timedelta(days=30)
    one_year_ago = latest_date - timedelta(days=365)
    df_1y = df_grade[df_grade["date"] >= one_year_ago]

    highlights = []
    skipped_sparse = []
    for desc, gdf in df_1y.groupby("display_name"):
        total_rows = len(gdf)
        traded = gdf.dropna(subset=[value_col])
        coverage = len(traded) / total_rows if total_rows else 0
        if coverage < MIN_DATA_COVERAGE or len(traded) < 2:
            skipped_sparse.append((desc, coverage))
            continue
        last_trade_date = traded["date"].max()
        if last_trade_date < active_cutoff:
            continue
        current_price = traded[traded["date"] == last_trade_date][value_col].mean()
        max_price = traded[value_col].max()
        min_price = traded[value_col].min()
        drop_rate = (current_price - max_price) / max_price if max_price else 0
        rise_rate = (current_price - min_price) / min_price if min_price else 0
        highlights.append({
            "display_name": desc,
            "current_price": current_price,
            "max_price": max_price,
            "min_price": min_price,
            "drop_rate": drop_rate,
            "rise_rate": rise_rate,
            "coverage": coverage,
        })

    if not highlights:
        st.info("데이터가 충분하지 않아 순위를 계산할 수 없습니다.")
        st.stop()

    hi_df = pd.DataFrame(highlights)
    drops = hi_df[hi_df["drop_rate"] < 0].sort_values("drop_rate", ascending=True)
    rises = hi_df[hi_df["rise_rate"] > 0].sort_values("rise_rate", ascending=False)

    def _render_row(row, color: str, rate_key: str, prefix: str):
        c1, c2, c3 = st.columns([4, 1.5, 1.5])
        with c1:
            st.markdown(f"**{row['display_name']}**")
        with c2:
            st.markdown(
                f"<div style='padding-top:5px'>{_fmt_usd(row['current_price'])}</div>",
                unsafe_allow_html=True,
            )
        with c3:
            sign = "" if row[rate_key] < 0 else "+"
            st.markdown(
                f"<div style='color:{color}; padding-top:5px'><b>{sign}{row[rate_key]*100:.1f}%</b></div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            "<hr style='margin:0.2em 0;border:none;border-bottom:1px solid #f0f0f0;'>",
            unsafe_allow_html=True,
        )

    col_drop, _spacer, col_rise = st.columns([1, 0.05, 1])

    with col_drop:
        st.markdown(f"#### Price Drop ({len(drops)}건)")
        h1, h2, h3 = st.columns([4, 1.5, 1.5])
        h1.markdown(":grey[**부위 (cut)**]")
        h2.markdown(":grey[**현재가**]")
        h3.markdown(":grey[**하락률**]")
        st.markdown(
            "<hr style='margin:0;border:none;border-bottom:2px solid #ddd;'>",
            unsafe_allow_html=True,
        )
        for idx, row in drops.iloc[:10].iterrows():
            _render_row(row, "blue", "drop_rate", f"d_{idx}")
        if len(drops) > 10:
            with st.expander("목록 전체 펼치기"):
                for idx, row in drops.iloc[10:].iterrows():
                    _render_row(row, "blue", "drop_rate", f"d_exp_{idx}")

    with col_rise:
        st.markdown(f"#### Price Rise ({len(rises)}건)")
        h1, h2, h3 = st.columns([4, 1.5, 1.5])
        h1.markdown(":grey[**부위 (cut)**]")
        h2.markdown(":grey[**현재가**]")
        h3.markdown(":grey[**상승률**]")
        st.markdown(
            "<hr style='margin:0;border:none;border-bottom:2px solid #ddd;'>",
            unsafe_allow_html=True,
        )
        for idx, row in rises.iloc[:10].iterrows():
            _render_row(row, "red", "rise_rate", f"r_{idx}")
        if len(rises) > 10:
            with st.expander("목록 전체 펼치기"):
                for idx, row in rises.iloc[10:].iterrows():
                    _render_row(row, "red", "rise_rate", f"r_exp_{idx}")

    if skipped_sparse:
        with st.expander(f"제외된 부위 ({len(skipped_sparse)}건) — 거래 데이터 부족"):
            sparse_df = (
                pd.DataFrame(skipped_sparse, columns=["display_name", "coverage"])
                .sort_values("coverage")
            )
            sparse_df["coverage"] = (sparse_df["coverage"] * 100).round(1).astype(str) + "%"
            sparse_df.columns = ["부위 (cut)", "최근 1년 거래율"]
            st.dataframe(sparse_df, hide_index=True, use_container_width=True)
            st.caption(
                "USDA LM_XB403 일일 보고서에서 해당 cut의 거래량이 적어 가격 미보고일이 많은 부위. "
                "원본 데이터에는 빈 값으로 들어옴 (API 오류 아님)."
            )

# --------------------------------------------------------------------------------
# CASE B: 상세 분석
# --------------------------------------------------------------------------------
else:
    df_part = df_grade[df_grade["display_name"] == selected_part]

    st.sidebar.markdown("---")
    st.sidebar.subheader("조회 기간")
    period_options = ["3개월", "12개월", "36개월", "전체"]
    selected_period = st.sidebar.radio(
        "기간 선택",
        period_options,
        index=1,
        horizontal=True,
        label_visibility="collapsed",
    )

    # 결측 가격은 평균 계산에서 제외
    df_part_valid = df_part.dropna(subset=[value_col])
    if df_part_valid.empty:
        st.warning("해당 부위는 USDA에서 가격 보고가 없는 상태입니다.")
        st.stop()

    max_date = df_part_valid["date"].max()
    min_date = df_part_valid["date"].min()
    if selected_period == "3개월":
        start_date = max_date - timedelta(days=90)
    elif selected_period == "12개월":
        start_date = max_date - timedelta(days=365)
    elif selected_period == "36개월":
        start_date = max_date - timedelta(days=365 * 3)
    else:
        start_date = min_date

    period_df = df_part_valid[
        (df_part_valid["date"] >= start_date) & (df_part_valid["date"] <= max_date)
    ]
    chart_df = (
        period_df.groupby("date", as_index=False)
        .agg({value_col: "mean", "price_krw_kg": "mean"})
        .sort_values("date")
    )

    if not chart_df.empty:
        chart_df["ma7"] = chart_df[value_col].rolling(window=7, min_periods=1).mean()
        chart_df["ma30"] = chart_df[value_col].rolling(window=30, min_periods=1).mean()

    st.title(f"USDA {selected_part}")
    st.markdown(
        f"등급: **{selected_grade}** | 주축: **USD/kg** · 보조축: **원/kg(환율 반영)** | "
        f"조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')}"
    )

    st.markdown(
        """
        <style>
        div[data-testid="stMetricValue"] { font-size: 24px !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if chart_df.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")
        st.stop()

    latest = chart_df.iloc[-1]
    curr_price = latest[value_col]

    if len(chart_df) > 1:
        prev = chart_df.iloc[-2][value_col]
        diff = curr_price - prev
        diff_pct = (diff / prev) * 100 if prev else 0
    else:
        diff, diff_pct = 0, 0

    period_max = chart_df[value_col].max()
    period_min = chart_df[value_col].min()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "현재가 (직전 보고일 대비)",
            _fmt_usd(curr_price),
            f"{_fmt_usd_diff(diff)} ({diff_pct:+.1f}%)",
        )
    with col2:
        st.metric(
            "기간 최고가",
            _fmt_usd(period_max),
            f"{_fmt_usd_diff(curr_price - period_max)} (괴리율)",
            delta_color="inverse",
        )
    with col3:
        st.metric(
            "기간 최저가",
            _fmt_usd(period_min),
            f"{_fmt_usd_diff(curr_price - period_min)} (괴리율)",
            delta_color="normal",
        )

    st.divider()

    st.subheader("가격 추이 분석")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=chart_df["date"], y=chart_df[value_col],
            mode="lines+markers", name="도매가 (USD/kg)",
            line=dict(color="#1565C0", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>USD/kg: %{y:.2f}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df["date"], y=chart_df["ma7"],
            mode="lines", name="7일 이동평균",
            line=dict(color="#FFA15A", width=1, dash="dot"),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df["date"], y=chart_df["ma30"],
            mode="lines", name="30일 이동평균",
            line=dict(color="#9E9E9E", width=1, dash="dash"),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=chart_df["date"], y=chart_df["price_krw_kg"],
            mode="lines", name="원/kg (보조축)",
            line=dict(color="#C62828", width=1),
            opacity=0.55,
            hovertemplate="%{x|%Y-%m-%d}<br>원/kg: %{y:,.0f}<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_layout(
        hovermode="x unified",
        height=520,
        margin=dict(l=20, r=20, t=10, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(title_text="날짜")
    fig.update_yaxes(title_text="USD/kg", secondary_y=False)
    fig.update_yaxes(title_text="원/kg (환율 반영)", secondary_y=True, showgrid=False)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("원본 데이터 보기 (최근 30일)"):
        view = chart_df.tail(30)[["date", value_col, "price_krw_kg", "ma7", "ma30"]].rename(
            columns={
                value_col: "USD/kg",
                "price_krw_kg": "원/kg",
                "ma7": "7일MA(USD/kg)",
                "ma30": "30일MA(USD/kg)",
            }
        )
        st.dataframe(view, hide_index=True, use_container_width=True)
