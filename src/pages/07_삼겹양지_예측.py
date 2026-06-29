# [파일 정의서]
# - 파일명: 08_Samgyup_Forecast.py
# - 역할: 시각화 (삼겹양지 가격 예측 · 공급 조기경보 · 변수 영향력 · 품목 전환)
# - 데이터 소스: data/2_dashboard/ 의 samgyup_forecast.csv, fas_supply_signal.csv,
#                samgyup_feature_importance.csv, switch_signal.csv
# - 비고: plotly.graph_objects만 사용(환경 호환), 각 파일 없으면 안내 후 건너뜀

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_DASHBOARD, FAS_SIGNAL_CSV

st.set_page_config(page_title="삼겹양지 예측·시그널", page_icon="", layout="wide")
st.title("삼겹양지 가격 예측 · 공급 조기경보")
st.caption("수입육 삼겹양지(미국산 Short Plate) 월별 예측 + 미·중/한 수출 기반 공급경보 + 변수 영향력 + 품목 전환 시그널")


def _load(path):
    p = Path(path)
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


# ── 1. 가격 예측 ─────────────────────────────────────────────
st.divider()
st.header("1. 삼겹양지 가격 예측 (월별)")
fc = _load(DATA_DASHBOARD / "samgyup_forecast.csv")
if fc is None or fc.empty:
    st.info("예측 데이터 없음 — `python src/utils/build_samgyup_model.py` 실행 필요")
else:
    fc["date"] = pd.to_datetime(fc["date"])
    act = fc[fc["type"] == "actual"]
    fut = fc[fc["type"] == "forecast"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=act["date"], y=act["base"], name="실측", mode="lines",
                             line=dict(color="#37474F", width=2)))
    if not fut.empty:
        fig.add_trace(go.Scatter(x=fut["date"], y=fut["high"], name="상단", mode="lines",
                                 line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=fut["date"], y=fut["low"], name="예측 밴드", mode="lines",
                                 line=dict(width=0), fill="tonexty", fillcolor="rgba(198,40,40,0.15)"))
        fig.add_trace(go.Scatter(x=fut["date"], y=fut["base"], name="예측(중심)", mode="lines+markers",
                                 line=dict(color="#C62828", width=2, dash="dash")))
    fig.update_layout(height=420, hovermode="x unified", margin=dict(l=20, r=20, t=10, b=20),
                      yaxis_title="원/kg", legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")
    if not fut.empty:
        c = st.columns(min(len(fut), 6) or 1)
        for i, (_, r) in enumerate(fut.iterrows()):
            with c[i % len(c)]:
                st.metric(r["date"].strftime("%Y-%m"), f"{int(r['base']):,}",
                          f"{int(r['low']):,}~{int(r['high']):,}")


# ── 2. 공급 조기경보 (FAS) ───────────────────────────────────
st.divider()
st.header("2. 공급 조기경보 — 미국산 수출 (중국 vs 한국)")
st.caption("중국행 급감 + 한국행 과잉 → 한국 공급과잉·가격 하방 위험 (2025년 덤핑 사태 패턴)")
fas = _load(FAS_SIGNAL_CSV)
if fas is None or fas.empty:
    st.info("FAS 신호 없음 — `collect_fas_export_sales.py` → `preprocess_fas_signal.py` 실행 필요")
else:
    fas["date"] = pd.to_datetime(fas["date"])
    last = fas.dropna(subset=["china_vs_med"]).iloc[-1] if fas["china_vs_med"].notna().any() else None
    if last is not None:
        tag = {0: "🟢 정상", 1: "🟡 주의", 2: "🔴 경보"}.get(int(last["alert_level"]), "-")
        st.subheader(f"현재 경보: {tag}  ({last['date'].strftime('%Y-%m')})")
        st.caption(str(last["note"]))
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=fas["date"], y=fas["china_exp"], name="→중국", mode="lines",
                              line=dict(color="#C62828", width=2)))
    fig2.add_trace(go.Scatter(x=fas["date"], y=fas["korea_exp"], name="→한국", mode="lines",
                              line=dict(color="#1565C0", width=2)))
    fig2.update_layout(height=360, hovermode="x unified", margin=dict(l=20, r=20, t=10, b=20),
                       yaxis_title="미국 beef 주간수출 합(월)", legend=dict(orientation="h"))
    st.plotly_chart(fig2, width="stretch")


# ── 3. 변수 영향력 ───────────────────────────────────────────
st.divider()
st.header("3. 가격 변수 영향력 (표준화 릿지)")
st.caption("음(-): 값↑ → 가격↓ / 양(+): 값↑ → 가격↑. 추세 공유·소표본으로 방향성 해석용.")
imp = _load(DATA_DASHBOARD / "samgyup_feature_importance.csv")
if imp is None or imp.empty:
    st.info("영향력 데이터 없음 — build_samgyup_model.py 실행 필요")
else:
    imp = imp.sort_values("std_coef")
    colors = ["#1565C0" if v < 0 else "#C62828" for v in imp["std_coef"]]
    fig3 = go.Figure(go.Bar(x=imp["std_coef"], y=imp["feature"], orientation="h", marker_color=colors))
    fig3.update_layout(height=380, margin=dict(l=20, r=20, t=10, b=20), xaxis_title="표준화 계수")
    st.plotly_chart(fig3, width="stretch")


# ── 4. 품목 전환 시그널 ──────────────────────────────────────
st.divider()
st.header("4. 품목 전환 시그널 (삼겹양지 매도 시 대체 매수 후보)")
st.caption("자기 이력 백분위: 높음=고평가(매도)/낮음=저평가(매수). 평균회귀 관점 · 용도 대체성은 별도 고려.")
sw = _load(DATA_DASHBOARD / "switch_signal.csv")
if sw is None or sw.empty:
    st.info("전환 시그널 없음 — build_switch_signal.py 실행 필요")
else:
    st.caption("거래가 지속되는 활성 품목(Tier1·2)만 대상. 거래 끊긴 품목은 자동 제외됨.")
    buy = sw[sw["signal"].astype(str).str.contains("매수")].sort_values("pct_rank")
    st.markdown("**매수 후보 (저평가 상위)**")
    st.dataframe(buy.head(8), hide_index=True, width="stretch")
    with st.expander("전체 활성 부위 상대가치 표 보기"):
        st.dataframe(sw, hide_index=True, width="stretch")

    # ML 예측 상승랭킹 (집계: data/3_reports/ml/, 집PC·이PC 학습 산출)
    import json
    from pathlib import Path as _P
    ml_dir = _P(str(DATA_DASHBOARD)).parents[0] / "3_reports" / "ml"
    rank = _load(ml_dir / "cut_upside_ranking.csv")
    if rank is not None and not rank.empty:
        st.markdown("**🤖 ML 예측 상승 랭킹 (익월 수익률 예측, pooled XGBoost)**")
        mp = ml_dir / "cut_model_metrics.json"
        if mp.exists():
            try:
                mm = json.loads(mp.read_text(encoding="utf-8"))
                st.caption(f"모델 신뢰도(OOS): 순위 IC {mm.get('rank_ic','-')}, 방향 적중 {mm.get('direction_hit','-')} "
                           f"· {mm.get('note','')}")
            except Exception:
                pass
        st.dataframe(rank.head(8), hide_index=True, width="stretch")
        st.caption("※ 상승예상 + 저평가(낮은 백분위)가 겹치면 강한 매수. 소표본이라 방향성 참고용.")

# ── 5. 거래 활성 품목(Universe) ─────────────────────────────
uni = _load(DATA_DASHBOARD / "meatbox_universe.csv")
if uni is not None and not uni.empty:
    st.divider()
    st.header("5. 거래 활성 품목 (Universe)")
    n1 = int((uni["tier"] == 1).sum()); n2 = int((uni["tier"] == 2).sum()); n0 = int((uni["tier"] == 0).sum())
    cc = st.columns(3)
    cc[0].metric("Tier1 (안정·이력충분)", f"{n1}종")
    cc[1].metric("Tier2 (신규·활성)", f"{n2}종")
    cc[2].metric("제외 (거래끊김)", f"{n0}종")
    st.caption("미트박스 품목 추가/제거에 매 실행 시 자동 대응(동적 선정). 모델·시그널은 Tier1·2(활성)만 사용.")
    with st.expander("품목별 활성도 상세"):
        st.dataframe(uni, hide_index=True, width="stretch")
