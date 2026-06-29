"""
[파일 정의서]
- 파일명: src/reports/generate_market_report.py
- 역할: 산출물 생성 (일반인용 월간 시장 리포트)
- 데이터 소스: dashboard_ready_data, samgyup_forecast, fas_supply_signal,
              switch_signal, cut_upside_ranking, meatbox_universe
- 출력: data/3_reports/market_report_YYYYMM.txt (카톡/문자 복붙용) + market_report_latest.txt
- 목적: 전문용어 없이 쉬운 말로 "이번 달 수입육 시세 흐름 + 다음달 전망 + 주목 품목" 정리.
- 실행: python src/reports/generate_market_report.py
- 주의: 참고용. 소표본·공개데이터 기반이라 단정 금지(면책 문구 포함).
"""
import sys, json
from datetime import datetime
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, DATA_DASHBOARD, DATA_PROCESSED, DATA_REPORTS, ensure_dirs

ML_DIR = Path(str(DATA_REPORTS)) / "ml"


def _load(p):
    p = Path(p)
    if not p.exists():
        return None
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def _active_parts():
    uni = _load(DATA_DASHBOARD / "meatbox_universe.csv")
    if uni is None or uni.empty:
        return None
    return set(uni[uni["tier"] > 0]["part"])


def _movers():
    """이번 달(최근 3주) vs 약 1개월 전 평균 비교 — 활성 품목 오름/내림 Top3."""
    mb = _load(DASHBOARD_READY_CSV)
    if mb is None:
        return [], []
    mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
    mb = mb.dropna(subset=["date", "part", "wholesale_price"])
    mb = mb[mb["wholesale_price"] > 0]
    active = _active_parts()
    if active:
        mb = mb[mb["part"].isin(active)]
    daily = mb.groupby(["part", "date"])["wholesale_price"].mean().reset_index()
    last = daily["date"].max()
    out = []
    for part, g in daily.groupby("part"):
        cur = g[g["date"] >= last - pd.Timedelta(days=21)]["wholesale_price"].mean()
        prev = g[(g["date"] < last - pd.Timedelta(days=21)) &
                 (g["date"] >= last - pd.Timedelta(days=51))]["wholesale_price"].mean()
        if pd.notna(cur) and pd.notna(prev) and prev > 0:
            out.append((part, int(round(cur)), (cur / prev - 1) * 100))
    ups = sorted([x for x in out if x[2] > 0], key=lambda x: -x[2])[:3]
    downs = sorted([x for x in out if x[2] < 0], key=lambda x: x[2])[:3]
    return ups, downs, last


def _samgyup_outlook():
    """삼겹양지 계절성(다음달 과거 평균변화) vs 최근 모멘텀을 비교해 충돌 없는 한 줄 전망 생성."""
    df = _load(DATA_PROCESSED / "samgyup_unified_monthly.csv")
    if df is None or df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    s = df.sort_values("date").set_index("date")["price_won_per_kg"].asfreq("MS").interpolate(limit=2)
    if s.dropna().empty:
        return None
    cur = float(s.dropna().iloc[-1])
    last_m = s.dropna().index[-1]
    nxt_month = (last_m.month % 12) + 1
    ret = s.pct_change(fill_method=None)
    seas = ret[ret.index.month == nxt_month].dropna()
    seas_avg = seas.mean() * 100 if len(seas) else 0.0
    recent = s.dropna()
    mom3 = (recent.iloc[-1] / recent.iloc[-4] - 1) * 100 if len(recent) >= 4 else 0.0

    # 방향 멘트: 계절성·모멘텀 결합
    if seas_avg < -1 and mom3 > 3:
        verdict = f"상반기 강세(최근3개월 {mom3:+.0f}%)였으나, {nxt_month}월은 계절적으로 약한 달(과거 평균 {seas_avg:+.0f}%) → 상승세 둔화·소폭 조정 가능성"
    elif seas_avg > 1 and mom3 > 1:
        verdict = f"상승 모멘텀(최근3개월 {mom3:+.0f}%)과 계절 강세(과거 {nxt_month}월 평균 {seas_avg:+.0f}%)가 겹쳐 추가 상승 가능성"
    elif seas_avg < -1 and mom3 < -1:
        verdict = f"하락 모멘텀과 계절 약세가 겹쳐 약세 지속 가능성 (과거 {nxt_month}월 평균 {seas_avg:+.0f}%)"
    else:
        verdict = f"계절성(과거 {nxt_month}월 평균 {seas_avg:+.0f}%)과 최근 흐름(3개월 {mom3:+.0f}%)이 엇갈려 보합권 예상"
    return cur, nxt_month, verdict


def build_report() -> str:
    L = []
    ups, downs, last = _movers()
    ym = last.strftime("%Y년 %m월") if last is not None else datetime.now().strftime("%Y년 %m월")

    L.append(f"🥩 수입육 시세 리포트 ({ym} 기준)")
    L.append("=" * 28)

    # 1) 삼겹양지 전망 (계절성·모멘텀 결합 — 충돌 제거)
    ol = _samgyup_outlook()
    if ol:
        cur, nxt_month, verdict = ol
        L.append(f"\n■ 삼겹양지(미국산) 현재 약 {cur:,.0f}원/kg")
        L.append(f"  {nxt_month}월 전망: {verdict}")
        L.append("  · 공급(수입량) 급증 시 하락 폭 확대 주의")

    # 2) 공급 신호
    fas = _load(DATA_DASHBOARD / "fas_supply_signal.csv")
    if fas is not None and "alert_level" in fas.columns and fas["alert_level"].notna().any():
        lv = int(fas.dropna(subset=["alert_level"]).iloc[-1]["alert_level"])
        msg = {0: "🟢 공급 안정적 — 가격 급변 위험 낮음",
               1: "🟡 주의 — 미국→중국 수출이 줄어 한국으로 물량이 몰릴 가능성",
               2: "🔴 경보 — 물량 과잉으로 수입육 가격 하락 압력"}.get(lv, "-")
        L.append(f"\n■ 공급 신호: {msg}")

    # 3) 이번 달 오른/내린 품목
    if ups:
        L.append("\n■ 이번 달 오른 품목 (전월 대비)")
        for p, price, pct in ups:
            L.append(f"  ▲ {p}: {price:,}원/kg ({pct:+.0f}%)")
    if downs:
        L.append("\n■ 이번 달 내린 품목")
        for p, price, pct in downs:
            L.append(f"  ▼ {p}: {price:,}원/kg ({pct:+.0f}%)")

    # 4) 주목 품목 (ML 상승예상 + 저평가)
    rank = _load(ML_DIR / "cut_upside_ranking.csv")
    if rank is not None and not rank.empty:
        # 삼겹양지는 위 전망에서 이미 다뤘으므로 제외(중복·충돌 방지)
        rank = rank[~rank["part"].astype(str).str.contains("삼겹양지", na=False)]
        top = rank.sort_values("pred_return_1m_pct", ascending=False).head(3)
        L.append("\n■ 다음달 상승 가능성 높은 다른 품목 (참고)")
        for _, r in top.iterrows():
            L.append(f"  · {r['part']} (예상 {r['pred_return_1m_pct']:+.1f}%)")

    sw = _load(DATA_DASHBOARD / "switch_signal.csv")
    if sw is not None and not sw.empty and "pct_rank" in sw.columns:
        cheap = sw.sort_values("pct_rank").head(3)
        L.append("\n■ 상대적으로 저렴한 품목 (장바구니 참고)")
        for _, r in cheap.iterrows():
            L.append(f"  · {r['part']} (최근가 {int(r['current_price']):,}원/kg)")

    L.append("\n" + "-" * 28)
    L.append("※ 공개 데이터 기반 참고 정보입니다. 실제 거래·구매 결과를 보장하지 않습니다.")
    return "\n".join(L)


def main():
    ensure_dirs()
    DATA_REPORTS.mkdir(parents=True, exist_ok=True)
    text = build_report()
    ym = datetime.now().strftime("%Y%m")
    (DATA_REPORTS / f"market_report_{ym}.txt").write_text(text, encoding="utf-8")
    (DATA_REPORTS / "market_report_latest.txt").write_text(text, encoding="utf-8")
    print(f"[완료] 리포트 저장: data/3_reports/market_report_{ym}.txt (+ latest)")
    print("\n" + text)


if __name__ == "__main__":
    main()
