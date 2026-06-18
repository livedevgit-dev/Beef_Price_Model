"""
[파일 정의서]
- 파일명: 06_Hanwoo_Dashboard.py
- 역할: 시각화 (한우 시장 종합 현황)
- 데이터 소스:
    - data/2_dashboard/hanwoo_dashboard_ready.csv (preprocess_hanwoo.py 산출)
    - data/2_dashboard/dashboard_ready_data.csv   (수입육 비교용)
- 구성: 단일 페이지 4섹션
    1. 한우 도매 경락가 현황 (EKAPE) — 등급별 추이 + KPI
    2. 공급 사이클 — 도축장별 경매두수(주간 합산) + 가격과의 역상관
    3. 수입육 vs 한우 — 가격 추이 동시 비교 + 가격차/배수
    4. 이상 신호 — 최근 30일 가격 급변(± 5% 이상) 등급/시장 리스트
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, HANWOO_DASHBOARD_CSV

st.set_page_config(page_title="한우 시장 종합", page_icon="", layout="wide")

GRADE_ORDER = ["1++", "1+", "1", "2", "3", "등외", "전체"]
GRADE_COLOR = {
    "1++": "#C62828",
    "1+": "#EF6C00",
    "1": "#FBC02D",
    "2": "#7CB342",
    "3": "#42A5F5",
    "등외": "#9E9E9E",
    "전체": "#37474F",
}


# --------------------------------------------------------------------------------
# 데이터 로드
# --------------------------------------------------------------------------------
@st.cache_data
def load_hanwoo() -> pd.DataFrame | None:
    if not HANWOO_DASHBOARD_CSV.exists():
        return None
    df = pd.read_csv(str(HANWOO_DASHBOARD_CSV))
    df["date"] = pd.to_datetime(df["date"])
    df["price_won_per_kg"] = pd.to_numeric(df["price_won_per_kg"], errors="coerce")
    df["head_count"] = pd.to_numeric(df["head_count"], errors="coerce")
    df["is_national_total"] = df["is_national_total"].fillna(False).astype(bool)
    df["is_regional_total"] = df["is_regional_total"].fillna(False).astype(bool)
    return df


@st.cache_data
def load_imported() -> pd.DataFrame | None:
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(str(DASHBOARD_READY_CSV))
    df["date"] = pd.to_datetime(df["date"])
    return df


hanwoo_df = load_hanwoo()
imp_df = load_imported()

if hanwoo_df is None or hanwoo_df.empty:
    st.error(
        "한우 대시보드 데이터(`hanwoo_dashboard_ready.csv`)를 찾을 수 없습니다.\n"
        "다음을 먼저 실행하세요:\n"
        "1. `python src/collectors/crawl_han_auction_api.py`\n"
        "2. `python src/collectors/collect_kamis_hanwoo.py`  (KAMIS 키 설정 시)\n"
        "3. `python src/utils/preprocess_hanwoo.py`"
    )
    st.stop()

# --------------------------------------------------------------------------------
# 사이드바
# --------------------------------------------------------------------------------
st.sidebar.header("조회 조건")
period_choice = st.sidebar.radio(
    "기간",
    ["3개월", "6개월", "12개월", "36개월", "전체"],
    index=2,
    horizontal=True,
)
PERIOD_DAYS = {"3개월": 90, "6개월": 180, "12개월": 365, "36개월": 365 * 3, "전체": None}
period_days = PERIOD_DAYS[period_choice]

latest_date = hanwoo_df["date"].max()
start_date = (latest_date - timedelta(days=period_days)) if period_days else hanwoo_df["date"].min()

# 표시 등급 선택 (1++/1+/1 기본)
available_grades = [g for g in GRADE_ORDER if g in hanwoo_df["grade"].unique()]
default_grades = [g for g in ["1++", "1+", "1"] if g in available_grades] or available_grades[:3]
selected_grades = st.sidebar.multiselect(
    "표시할 등급", available_grades, default=default_grades
)
if not selected_grades:
    selected_grades = default_grades

ekape = hanwoo_df[hanwoo_df["source"] == "ekape_auction"].copy()
kamis = hanwoo_df[hanwoo_df["source"].astype(str).str.startswith("kamis_")].copy()
ekape_national = ekape[ekape["is_national_total"]].copy()
ekape_period = ekape_national[
    (ekape_national["date"] >= start_date) & (ekape_national["date"] <= latest_date)
]
ekape_period_grade = ekape_period[ekape_period["grade"].isin(selected_grades)]

_active_sources = sorted(hanwoo_df["source"].dropna().unique().tolist())
_source_labels = {
    "ekape_auction": "EKAPE 경락·두수",
    "kamis_wholesale": "KAMIS 도매",
    "kamis_retail": "KAMIS 소매",
}
_active_labels = [_source_labels.get(s, s) for s in _active_sources]
if "kamis_wholesale" not in _active_sources and "kamis_retail" not in _active_sources:
    _kamis_note = (
        " · KAMIS: **미연동** (`.env`에 `KAMIS_CERT_KEY`/`KAMIS_CERT_ID` 입력 후 "
        "`collect_kamis_hanwoo.py` 실행 시 부위별 도·소매가 추가)"
    )
else:
    _kamis_note = ""

# --------------------------------------------------------------------------------
# 헤더
# --------------------------------------------------------------------------------
st.title("한우 시장 종합 대시보드")
st.caption(
    f"기준일: **{latest_date.strftime('%Y-%m-%d')}** · 조회 기간: "
    f"{start_date.strftime('%Y-%m-%d')} ~ {latest_date.strftime('%Y-%m-%d')} "
    f"· 연동 데이터: {', '.join(_active_labels) if _active_labels else '없음'}"
    f"{_kamis_note}"
)

# --------------------------------------------------------------------------------
# 섹션 1: 한우 도매 경락가 현황
# --------------------------------------------------------------------------------
st.divider()
st.header("1. 한우 도매 경락가 현황 (전국 기준)")

if ekape_period_grade.empty:
    st.warning("선택한 기간·등급에 해당하는 EKAPE 데이터가 없습니다.")
else:
    # KPI: 1++ 기준 최근가 / 30일 전 대비 / 1년 전 대비
    kpi_cols = st.columns(min(4, len(selected_grades)))
    for col, grade in zip(kpi_cols, selected_grades[:4]):
        g_df = ekape_national[ekape_national["grade"] == grade].sort_values("date")
        g_df = g_df.dropna(subset=["price_won_per_kg"])
        if g_df.empty:
            with col:
                st.metric(f"{grade}등급", "-", "데이터 없음")
            continue
        latest_row = g_df.iloc[-1]
        curr = latest_row["price_won_per_kg"]

        def _price_n_days_ago(days: int) -> float | None:
            target = latest_row["date"] - timedelta(days=days)
            window = g_df[
                (g_df["date"] >= target - timedelta(days=7))
                & (g_df["date"] <= target + timedelta(days=7))
            ]["price_won_per_kg"]
            return float(window.mean()) if not window.empty else None

        prev_30 = _price_n_days_ago(30)
        prev_365 = _price_n_days_ago(365)
        delta_pct_30 = ((curr - prev_30) / prev_30 * 100) if prev_30 else None
        delta_str = (
            f"{delta_pct_30:+.1f}% (30일 전 대비)"
            if delta_pct_30 is not None
            else "-"
        )
        with col:
            st.metric(
                f"{grade}등급 (원/kg)",
                f"{curr:,.0f}",
                delta_str,
                delta_color="inverse" if (delta_pct_30 or 0) > 0 else "normal",
            )
            if prev_365:
                yoy = (curr - prev_365) / prev_365 * 100
                st.caption(f"전년 동기 대비 {yoy:+.1f}%")

    # 가격 추이 차트
    fig = go.Figure()
    for grade in selected_grades:
        g_df = ekape_period_grade[ekape_period_grade["grade"] == grade].sort_values("date")
        if g_df.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=g_df["date"],
                y=g_df["price_won_per_kg"],
                mode="lines",
                name=f"{grade}",
                line=dict(color=GRADE_COLOR.get(grade, "#666"), width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>" + grade + ": %{y:,.0f}원/kg<extra></extra>",
            )
        )
    fig.update_layout(
        height=420,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=10, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis_title="경락가 (원/kg, 결함포함)",
    )
    st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------------
# 섹션 2: 공급 사이클 — 경매두수
# --------------------------------------------------------------------------------
st.divider()
st.header("2. 공급 사이클 — 도축(경매) 두수 추이")
st.caption(
    "EKAPE는 도매시장 경매 기준 두수입니다. 농가 도축실적과 강한 상관관계를 보이며, "
    "주간 합산해 단기 공급 변동을 평활화했습니다."
)

if ekape_period.empty:
    st.warning("선택 기간에 EKAPE 두수 데이터가 없습니다.")
else:
    head_df = ekape_period.dropna(subset=["head_count"]).copy()
    if head_df.empty:
        st.info("두수(head_count) 컬럼이 비어 있어 차트를 그릴 수 없습니다.")
    else:
        # 등급 합산 일별 두수 → 주간 합산
        daily_head = (
            head_df.groupby("date", as_index=False)["head_count"].sum()
            .sort_values("date")
        )
        daily_head["week"] = daily_head["date"] - pd.to_timedelta(
            daily_head["date"].dt.weekday, unit="D"
        )
        weekly_head = daily_head.groupby("week", as_index=False)["head_count"].sum()
        weekly_head = weekly_head.rename(columns={"week": "date"})

        # 가격(1++ 또는 가장 윗 등급)도 같이 주간 평균
        primary_grade = selected_grades[0] if selected_grades else "1++"
        price_df = (
            ekape_national[ekape_national["grade"] == primary_grade]
            .dropna(subset=["price_won_per_kg"])
            .copy()
        )
        price_df = price_df[
            (price_df["date"] >= start_date) & (price_df["date"] <= latest_date)
        ]
        if not price_df.empty:
            price_df["week"] = price_df["date"] - pd.to_timedelta(
                price_df["date"].dt.weekday, unit="D"
            )
            weekly_price = price_df.groupby("week", as_index=False)[
                "price_won_per_kg"
            ].mean()
            weekly_price = weekly_price.rename(columns={"week": "date"})
        else:
            weekly_price = pd.DataFrame(columns=["date", "price_won_per_kg"])

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(
            go.Bar(
                x=weekly_head["date"],
                y=weekly_head["head_count"],
                name="주간 경매두수 (전국)",
                marker_color="rgba(120,144,156,0.55)",
                hovertemplate="%{x|%Y-%m-%d} 주<br>두수: %{y:,}<extra></extra>",
            ),
            secondary_y=False,
        )
        if not weekly_price.empty:
            fig2.add_trace(
                go.Scatter(
                    x=weekly_price["date"],
                    y=weekly_price["price_won_per_kg"],
                    name=f"{primary_grade}등급 주간 평균가",
                    line=dict(color=GRADE_COLOR.get(primary_grade, "#C62828"), width=2),
                    mode="lines+markers",
                    hovertemplate="%{x|%Y-%m-%d} 주<br>가격: %{y:,.0f}원/kg<extra></extra>",
                ),
                secondary_y=True,
            )
        fig2.update_layout(
            height=420,
            hovermode="x unified",
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig2.update_yaxes(title_text="주간 경매두수", secondary_y=False)
        fig2.update_yaxes(title_text="가격 (원/kg)", secondary_y=True, showgrid=False)
        st.plotly_chart(fig2, use_container_width=True)

        # 상관계수: 같은 주 두수 vs 가격
        if not weekly_price.empty:
            merged = pd.merge(weekly_head, weekly_price, on="date", how="inner")
            if len(merged) > 4:
                corr_same = merged["head_count"].corr(merged["price_won_per_kg"])
                merged_lag = merged.copy()
                merged_lag["head_count_lag4"] = merged_lag["head_count"].shift(4)
                corr_lag = merged_lag["head_count_lag4"].corr(merged_lag["price_won_per_kg"])
                c1, c2 = st.columns(2)
                c1.metric(
                    "주간 두수 ↔ 가격 (동행)",
                    f"{corr_same:+.2f}",
                    "음(-)이면 공급-가격 역상관 정상",
                )
                c2.metric(
                    "두수(4주 전) ↔ 가격 (선행)",
                    f"{corr_lag:+.2f}",
                    "선행 효과 확인용",
                )

# --------------------------------------------------------------------------------
# 섹션 3: 수입육 vs 한우
# --------------------------------------------------------------------------------
st.divider()
st.header("3. 수입육 vs 한우 — 가격 비교")
st.caption(
    "한우는 EKAPE 1++ 전국 평균(원/kg, 도체), 수입육은 미트박스 dashboard_ready_data 평균(원/kg) 기준."
)

if imp_df is None or imp_df.empty:
    st.info("수입육 데이터(`dashboard_ready_data.csv`)가 없어 비교 차트를 건너뜁니다.")
else:
    han_compare = (
        ekape_national[ekape_national["grade"].isin(["1++", "1+", "1"])]
        .dropna(subset=["price_won_per_kg"])
        .copy()
    )
    han_compare = han_compare[
        (han_compare["date"] >= start_date) & (han_compare["date"] <= latest_date)
    ]
    if han_compare.empty:
        st.warning("선택 기간 한우 데이터가 없습니다.")
    else:
        # 등급별 일평균
        han_daily = (
            han_compare.groupby(["date", "grade"], as_index=False)["price_won_per_kg"].mean()
        )

        # 수입육: 동일 기간, 부위·브랜드 평균
        imp_daily = imp_df[
            (imp_df["date"] >= start_date) & (imp_df["date"] <= latest_date)
        ].copy()
        imp_avg = (
            imp_daily.groupby("date", as_index=False)["wholesale_price"].mean()
            .rename(columns={"wholesale_price": "imp_price"})
        )

        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        for grade in ["1++", "1+", "1"]:
            sub = han_daily[han_daily["grade"] == grade]
            if sub.empty:
                continue
            fig3.add_trace(
                go.Scatter(
                    x=sub["date"], y=sub["price_won_per_kg"],
                    name=f"한우 {grade}",
                    mode="lines",
                    line=dict(color=GRADE_COLOR.get(grade, "#666"), width=2),
                ),
                secondary_y=False,
            )
        if not imp_avg.empty:
            fig3.add_trace(
                go.Scatter(
                    x=imp_avg["date"], y=imp_avg["imp_price"],
                    name="수입육 평균 (보조축)",
                    mode="lines",
                    line=dict(color="#1565C0", width=2, dash="dash"),
                ),
                secondary_y=True,
            )
        fig3.update_layout(
            height=440,
            hovermode="x unified",
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig3.update_yaxes(title_text="한우 (원/kg)", secondary_y=False)
        fig3.update_yaxes(title_text="수입육 (원/kg)", secondary_y=True, showgrid=False)
        st.plotly_chart(fig3, use_container_width=True)

        # 한우/수입육 배수 추이
        if not imp_avg.empty:
            han_1pp = han_daily[han_daily["grade"] == "1++"][["date", "price_won_per_kg"]]
            han_1pp = han_1pp.rename(columns={"price_won_per_kg": "han_price"})
            merged_cmp = pd.merge(han_1pp, imp_avg, on="date", how="inner")
            merged_cmp = merged_cmp[merged_cmp["imp_price"] > 0]
            if not merged_cmp.empty:
                merged_cmp["ratio"] = merged_cmp["han_price"] / merged_cmp["imp_price"]
                fig_ratio = go.Figure()
                fig_ratio.add_trace(
                    go.Scatter(
                        x=merged_cmp["date"], y=merged_cmp["ratio"],
                        mode="lines", line=dict(color="#6A1B9A", width=2),
                        name="배수",
                    )
                )
                fig_ratio.update_layout(
                    height=260, margin=dict(l=20, r=20, t=10, b=20),
                    yaxis_title="한우 1++ / 수입육 평균 (배수)",
                )
                st.markdown("**한우 1++ / 수입육 평균 가격 배수**")
                st.plotly_chart(fig_ratio, use_container_width=True)
                latest_ratio = merged_cmp.iloc[-1]
                st.caption(
                    f"최근 기준 배수 {latest_ratio['ratio']:.2f}배 "
                    f"(한우 {latest_ratio['han_price']:,.0f}원/kg, "
                    f"수입육 {latest_ratio['imp_price']:,.0f}원/kg)"
                )

# --------------------------------------------------------------------------------
# 섹션 4: 이상 신호
# --------------------------------------------------------------------------------
st.divider()
st.header("4. 이상 신호 — 최근 30일 급변 등급/시장")
st.caption("최근 30일 변동률(현재가 vs 30일 평균)이 ±5% 이상인 (등급, 시장) 조합 노출.")

alert_threshold = 0.05
alerts: list[dict] = []
ekape_recent = ekape[ekape["date"] >= latest_date - timedelta(days=60)]
for (grade, market), grp in ekape_recent.groupby(["grade", "market_name"]):
    grp_v = grp.dropna(subset=["price_won_per_kg"]).sort_values("date")
    if len(grp_v) < 5:
        continue
    last = grp_v.iloc[-1]
    last_30 = grp_v[grp_v["date"] >= last["date"] - timedelta(days=30)]
    base = last_30["price_won_per_kg"].mean()
    if not base or base <= 0:
        continue
    change = (last["price_won_per_kg"] - base) / base
    if abs(change) >= alert_threshold:
        alerts.append({
            "등급": grade,
            "시장": market,
            "최근가": last["price_won_per_kg"],
            "30일 평균": base,
            "변동률": change,
            "최근 일자": last["date"].strftime("%Y-%m-%d"),
        })

if not alerts:
    st.success("최근 30일 기준 ±5% 이상의 급변 신호가 없습니다.")
else:
    alerts_df = pd.DataFrame(alerts).sort_values("변동률", key=lambda s: s.abs(), ascending=False)
    styled = (
        alerts_df.style
        .format({
            "최근가": "{:,.0f}원/kg",
            "30일 평균": "{:,.0f}원/kg",
            "변동률": "{:+.1%}",
        })
        .map(
            lambda v: (
                "background-color:#FFEBEE; color:#C62828; font-weight:bold"
                if isinstance(v, float) and v > 0
                else (
                    "background-color:#E3F2FD; color:#1565C0; font-weight:bold"
                    if isinstance(v, float) and v < 0
                    else ""
                )
            ),
            subset=["변동률"],
        )
    )
    st.dataframe(styled, hide_index=True, use_container_width=True)

# --------------------------------------------------------------------------------
# 섹션 5: KAMIS 부위별 한우 소매·도매가
# --------------------------------------------------------------------------------
st.divider()
st.header("5. KAMIS 부위별 한우 소·도매가")

if kamis.empty:
    st.info(
        "KAMIS 데이터가 없습니다. `.env`에 `KAMIS_CERT_KEY`/`KAMIS_CERT_ID` 입력 후 "
        "`collect_kamis_hanwoo.py` → `preprocess_hanwoo.py` 실행 시 부위별 도·소매가가 표시됩니다."
    )
else:
    st.caption(
        "KAMIS 부위별 한우 가격(원/kg, 100g 단위를 kg로 환산). EKAPE 경락가(도체 전체)와 달리 "
        "**부위·등급별 소비자/도매 가격**을 제공합니다. 과거 일자는 KAMIS 미게시일이 많아 값이 희소할 수 있습니다."
    )
    kamis_period = kamis[
        (kamis["date"] >= start_date) & (kamis["date"] <= latest_date)
    ].dropna(subset=["price_won_per_kg"]).copy()

    parts_avail = sorted(kamis_period["part"].dropna().unique())
    grades_avail_k = [g for g in GRADE_ORDER if g in kamis_period["grade"].unique()]

    if kamis_period.empty or not parts_avail or not grades_avail_k:
        st.warning("선택한 기간에 표시할 KAMIS 데이터가 없습니다. 기간을 넓혀 보세요.")
    else:
        c1, c2, c3 = st.columns(3)
        sel_parts = c1.multiselect("부위", parts_avail, default=parts_avail)
        sel_grade_k = c2.selectbox("등급", grades_avail_k, index=0)
        channels = []
        if "kamis_retail" in kamis_period["source"].unique():
            channels.append("소매")
        if "kamis_wholesale" in kamis_period["source"].unique():
            channels.append("도매")
        sel_channel = c3.radio("구분", channels, horizontal=True) if channels else "소매"
        src_key = "kamis_retail" if sel_channel == "소매" else "kamis_wholesale"

        if not sel_parts:
            sel_parts = parts_avail

        view_k = kamis_period[
            (kamis_period["source"] == src_key)
            & (kamis_period["grade"] == sel_grade_k)
            & (kamis_period["part"].isin(sel_parts))
        ].sort_values("date")

        if view_k.empty:
            st.warning("선택 조건(부위/등급/구분)에 해당하는 KAMIS 데이터가 없습니다.")
        else:
            # KPI: 부위별 최신가
            latest_k = view_k.groupby("part").last()
            kpi_cols = st.columns(min(len(sel_parts), 5) or 1)
            for i, p in enumerate(sel_parts):
                if p in latest_k.index:
                    with kpi_cols[i % len(kpi_cols)]:
                        st.metric(
                            f"{p} ({sel_grade_k}, {sel_channel})",
                            f"{latest_k.loc[p, 'price_won_per_kg']:,.0f} 원/kg",
                        )

            # 부위별 가격 추이
            figk = go.Figure()
            for p in sel_parts:
                gp = view_k[view_k["part"] == p]
                if gp.empty:
                    continue
                figk.add_trace(
                    go.Scatter(
                        x=gp["date"], y=gp["price_won_per_kg"],
                        mode="lines+markers", name=p,
                        hovertemplate="%{x|%Y-%m-%d}<br>" + p + ": %{y:,.0f}원/kg<extra></extra>",
                    )
                )
            figk.update_layout(
                height=420, hovermode="x unified",
                margin=dict(l=20, r=20, t=10, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis_title=f"{sel_channel}가 (원/kg)",
            )
            st.plotly_chart(figk, width="stretch")
