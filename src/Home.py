import sys
from pathlib import Path
from datetime import timedelta

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 실행 환경 무관하게 src/ 를 모듈 경로에 보장
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DASHBOARD_READY_CSV, DATA_DASHBOARD, MACRO_PROCESSED_CSV, FAS_SIGNAL_CSV

# [파일 정의서]
# - 파일명: Home.py
# - 역할: 시각화 (메인 대시보드 — 주요 정보 한눈에)
# - 데이터 소스: data/2_dashboard/ 의 가격·예측·경보·시그널 + macro
# - 주요 기능: 삼겹양지 예측·공급경보·핵심 거시·매수후보 요약 + 부위별 시세 변동표

st.set_page_config(page_title="수입육·한우 인사이트", page_icon="", layout="wide")


def _load(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


st.title("수입육 · 한우 가격 인사이트 플랫폼")
st.caption("주요 지표 요약 — 상세 분석은 좌측 메뉴 참고")
st.divider()

# ============================================================
# A. 주요 정보 요약 (한눈에)
# ============================================================
st.subheader("📌 주요 정보 요약")

c1, c2, c3, c4 = st.columns(4)

# 1) 삼겹양지 최신가 + 다음달 예측
fc = _load(DATA_DASHBOARD / "samgyup_forecast.csv")
with c1:
    if fc is not None and not fc.empty:
        fc["date"] = pd.to_datetime(fc["date"])
        act = fc[fc["type"] == "actual"].sort_values("date")
        fut = fc[fc["type"] == "forecast"].sort_values("date")
        cur = act["base"].iloc[-1] if not act.empty else None
        nxt = fut["base"].iloc[0] if not fut.empty else None
        if cur is not None:
            delta = f"{(nxt-cur)/cur*100:+.1f}% (익월 예측)" if nxt else None
            st.metric("삼겹양지 (원/kg)", f"{int(cur):,}", delta)
        else:
            st.metric("삼겹양지", "-")
    else:
        st.metric("삼겹양지", "데이터 없음")

# 2) 공급 조기경보 (FAS)
fas = _load(FAS_SIGNAL_CSV)
with c2:
    if fas is not None and fas.get("alert_level") is not None and fas["alert_level"].notna().any():
        last = fas.dropna(subset=["alert_level"]).iloc[-1]
        tag = {0: "🟢 정상", 1: "🟡 주의", 2: "🔴 경보"}.get(int(last["alert_level"]), "-")
        st.metric("공급 경보 (미·중/한)", tag)
    else:
        st.metric("공급 경보", "-")

# 3) 환율
mac = _load(MACRO_PROCESSED_CSV)
with c3:
    if mac is not None and "indicator_id" in mac.columns:
        fx = mac[mac["indicator_id"] == "us_wti"]  # placeholder if needed
        fxrow = None
        # 환율은 macro에 없으므로 기준금리로 대체 표시
        br = mac[mac["indicator_id"] == "kr_base_rate"]
        if not br.empty:
            v = br.sort_values("date")["value"].iloc[-1]
            st.metric("한국 기준금리", f"{v:.2f}%")
        else:
            st.metric("기준금리", "-")
    else:
        st.metric("기준금리", "-")

# 4) 매수 후보 (전환 시그널 저평가 1위)
sw = _load(DATA_DASHBOARD / "switch_signal.csv")
with c4:
    if sw is not None and not sw.empty and "pct_rank" in sw.columns:
        buy = sw.sort_values("pct_rank").iloc[0]
        st.metric("저평가 매수후보", str(buy["part"]), f"이력 {int(buy['pct_rank'])}% 수준")
    else:
        st.metric("매수후보", "-")

# 삼겹양지 예측 미니 차트
if fc is not None and not fc.empty:
    act = fc[fc["type"] == "actual"].sort_values("date").tail(24)
    fut = fc[fc["type"] == "forecast"].sort_values("date")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=act["date"], y=act["base"], name="실측", mode="lines",
                             line=dict(color="#37474F", width=2)))
    if not fut.empty:
        fig.add_trace(go.Scatter(x=fut["date"], y=fut["base"], name="예측", mode="lines+markers",
                                 line=dict(color="#C62828", width=2, dash="dash")))
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10),
                      title="삼겹양지 가격 추이·예측 (원/kg)", legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")

st.divider()

# ============================================================
# B. 부위별 시세 변동 요약 (기존)
# ============================================================
st.subheader("부위별 시세 변동 요약")

df = _load(DASHBOARD_READY_CSV)
if df is not None:
    df["date"] = pd.to_datetime(df["date"])
    df_avg = df.groupby(["date", "part"])["wholesale_price"].mean().reset_index()
    latest_date = df_avg["date"].max()
    st.markdown(f"**기준일:** {latest_date.strftime('%Y-%m-%d')} | **기준:** 브랜드 통합 평균가")

    date_3m, date_6m, date_12m = (latest_date - timedelta(days=d) for d in (90, 180, 365))
    summary_list = []
    for part_name in sorted(df_avg["part"].unique()):
        part_df = df_avg[df_avg["part"] == part_name].sort_values("date")
        recent = part_df[(part_df["date"] >= latest_date - timedelta(days=7)) &
                         (part_df["wholesale_price"].notna()) & (part_df["wholesale_price"] != 0)]
        if recent.empty:
            continue
        curr_price = recent.sort_values("date").iloc[-1]["wholesale_price"]

        def price_at(td):
            w = part_df[(part_df["date"] >= td - timedelta(days=7)) &
                        (part_df["date"] <= td + timedelta(days=7))]["wholesale_price"].dropna()
            return w.mean() if not w.empty else None

        def pct(c, p):
            return ((c - p) / p) * 100 if (p and p != 0) else None

        p6 = price_at(date_6m)
        summary_list.append({
            "부위": part_name, "현재가": curr_price,
            "3개월 전 대비": pct(curr_price, price_at(date_3m)),
            "6개월 전 대비": pct(curr_price, p6),
            "1년 전 대비": pct(curr_price, price_at(date_12m)),
            "_sort": pct(curr_price, p6) if p6 else 0,
        })

    ds = pd.DataFrame(summary_list)
    if not ds.empty:
        ds = ds.sort_values("_sort").drop(columns="_sort")

        def style_var(v):
            if pd.isna(v):
                return ""
            return ("color:#D32F2F;background-color:#FFEBEE;font-weight:bold" if v > 0
                    else "color:#1976D2;background-color:#E3F2FD;font-weight:bold" if v < 0 else "")

        def fmt(v):
            return "-" if pd.isna(v) else f"{v:+.1f}%"

        st.dataframe(
            ds.style.format({"현재가": "{:,.0f}원"})
              .format(fmt, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"])
              .map(style_var, subset=["3개월 전 대비", "6개월 전 대비", "1년 전 대비"]),
            width="stretch", height=(len(ds) + 1) * 35 + 3, hide_index=True,
        )
        st.info("'6개월 전 대비' 하락폭이 큰 순으로 정렬. 상세는 좌측 **가격 대시보드** 참고.")
    else:
        st.warning("분석할 데이터가 충분하지 않습니다.")
else:
    st.warning("데이터 파일(dashboard_ready_data.csv)을 찾을 수 없습니다.")
