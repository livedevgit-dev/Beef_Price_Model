"""
[파일 정의서]
- 파일명: train_cut_upside.py
- 역할: 분석 (부위별 향후 상승 가능성 — pooled XGBoost)
- 입력: data/2_dashboard/dashboard_ready_data.csv (활성 universe 부위)
- 출력: data/3_reports/ml/ 의 cut_upside_ranking.csv, cut_model_metrics.json
- 방법: 전 부위 통합(pooled) 학습. 부위×월 단위로 모멘텀·백분위·변동성·계절성 피처 →
        타겟 = 익월 수익률(%). 시계열 OOS(IC·적중률) 평가 후 최신월 랭킹 산출.
- 주의: 미트박스 1.5년 → 표본 적음. 방향성 스크린으로만 해석.
"""
import sys, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, ensure_dirs
from utils.select_universe import classify_universe
import xgboost as xgb

OUT = Path(__file__).resolve().parents[2] / "data" / "3_reports" / "ml"


def build_panel():
    mb = pd.read_csv(DASHBOARD_READY_CSV)
    mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
    mb = mb.dropna(subset=["date", "part", "wholesale_price"])
    mb = mb[mb["wholesale_price"] > 0]
    active = set(classify_universe(mb).query("tier>0")["part"])
    mb = mb[mb["part"].isin(active)]
    # 월별 평균가
    mb["m"] = mb["date"].dt.to_period("M").dt.to_timestamp()
    mo = mb.groupby(["part", "m"])["wholesale_price"].mean().reset_index()
    rows = []
    for part, g in mo.groupby("part"):
        g = g.sort_values("m").reset_index(drop=True)
        g["ret1"] = g["wholesale_price"].pct_change()
        g["mom_1"] = g["ret1"]
        g["mom_3"] = g["wholesale_price"].pct_change(3)
        g["vol_3"] = g["ret1"].rolling(3).std()
        g["pctile"] = g["wholesale_price"].expanding().apply(lambda s: (s < s.iloc[-1]).mean())
        g["month"] = g["m"].dt.month
        g["fwd1"] = g["wholesale_price"].shift(-1) / g["wholesale_price"] - 1  # 익월 수익률(타겟)
        g["part"] = part
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


def main():
    ensure_dirs(); OUT.mkdir(parents=True, exist_ok=True)
    panel = build_panel()
    feats = ["mom_1", "mom_3", "vol_3", "pctile", "month"]
    train = panel.dropna(subset=feats + ["fwd1"]).copy()
    print(f"pooled 표본 {len(train)} (부위×월)")

    # 시계열 OOS: 월 단위 walk-forward
    months = sorted(train["m"].unique())
    start = months[len(months)//2]
    preds = []
    for tm in [m for m in months if m >= start]:
        tr = train[train["m"] < tm]; te = train[train["m"] == tm]
        if len(tr) < 30 or te.empty:
            continue
        m = xgb.XGBRegressor(n_estimators=150, max_depth=3, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, random_state=42)
        m.fit(tr[feats], tr["fwd1"])
        te = te.copy(); te["pred"] = m.predict(te[feats])
        preds.append(te[["m", "part", "pred", "fwd1"]])
    oos = pd.concat(preds, ignore_index=True) if preds else pd.DataFrame()

    metrics = {"pooled_n": int(len(train)), "oos_n": int(len(oos))}
    if not oos.empty:
        ic = oos["pred"].corr(oos["fwd1"], method="spearman")     # 순위 정보계수
        hit = float(((oos["pred"] > 0) == (oos["fwd1"] > 0)).mean())  # 방향 적중률
        metrics.update({"rank_ic": round(float(ic), 3), "direction_hit": round(hit, 3),
                        "note": "IC>0·적중>0.5 면 약한 예측력. 소표본이라 방향성 참고용."})

    # 최신월 랭킹 (전체 학습 → 가장 최근 관측월의 익월 수익률 예측)
    full = panel.dropna(subset=feats).copy()
    last_m = full["m"].max()
    cur = full[full["m"] == last_m].copy()
    tr_all = train  # fwd1 있는 것만
    mf = xgb.XGBRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, random_state=42)
    mf.fit(tr_all[feats], tr_all["fwd1"])
    cur["pred_return_1m_pct"] = (mf.predict(cur[feats]) * 100).round(2)
    rank = cur[["part", "wholesale_price", "pctile", "pred_return_1m_pct"]].copy()
    rank["pctile"] = (rank["pctile"] * 100).round()
    rank = rank.rename(columns={"wholesale_price": "current_price"}).sort_values("pred_return_1m_pct", ascending=False)
    rank["current_price"] = rank["current_price"].round().astype(int)
    rank.insert(0, "rank", range(1, len(rank) + 1))

    rank.to_csv(OUT / "cut_upside_ranking.csv", index=False, encoding="utf-8-sig")
    (OUT / "cut_model_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[완료] cut_upside_ranking.csv / cut_model_metrics.json")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\n[상승 예상 상위 (기준월 {last_m.date()})]")
    print(rank.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
