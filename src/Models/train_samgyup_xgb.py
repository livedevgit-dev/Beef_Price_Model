"""
[파일 정의서]
- 파일명: train_samgyup_xgb.py
- 역할: 분석 (삼겹양지 익월 가격 예측 — XGBoost, 시계열 검증)
- 입력: data/1_processed/samgyup_model_features.csv
- 출력: data/3_reports/ml/ 의 samgyup_pred.csv, samgyup_metrics.json, samgyup_importance.csv
- 방법: 타겟 = 익월 가격(samgyup.shift(-1)). 피처 = 당월 드라이버 + AR(lag1,2).
        walk-forward(expanding window) out-of-sample 평가. naive(전월값)·계절 baseline 과 비교.
- 주의: 표본 작음(완전행 ~37) → 과적합 위험. OOS 로만 평가하고 baseline 못 이기면 그대로 보고.
"""
import sys, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED, ensure_dirs
import xgboost as xgb

OUT = Path(__file__).resolve().parents[2] / "data" / "3_reports" / "ml"


def main():
    ensure_dirs(); OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PROCESSED / "samgyup_model_features.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["samgyup_lag1"] = df["samgyup"].shift(1)
    df["samgyup_lag2"] = df["samgyup"].shift(2)
    df["target"] = df["samgyup"].shift(-1)          # 익월 가격
    feats = [c for c in df.columns if c not in ("date", "samgyup", "target")]
    d = df.dropna(subset=feats + ["target", "samgyup"]).reset_index(drop=True)
    n = len(d)
    print(f"표본 {n}개월, 피처 {len(feats)}개")

    min_train = max(18, n // 2)
    rows = []
    for i in range(min_train, n):
        Xtr, ytr = d.loc[:i-1, feats], d.loc[:i-1, "target"]
        m = xgb.XGBRegressor(n_estimators=120, max_depth=2, learning_rate=0.05,
                             subsample=0.8, colsample_bytree=0.8, random_state=42)
        m.fit(Xtr, ytr)
        pred = float(m.predict(d.loc[[i], feats])[0])
        rows.append({"date": d.loc[i, "date"], "actual": d.loc[i, "target"],
                     "pred_xgb": pred, "naive": d.loc[i, "samgyup"]})  # naive=당월값으로 익월 예측
    res = pd.DataFrame(rows).dropna(subset=["actual"])

    def mae(a, b): return float(np.mean(np.abs(a - b)))
    def r2(a, p):
        ss = np.sum((a - a.mean())**2); return float(1 - np.sum((a-p)**2)/ss) if ss else float("nan")
    mae_x, mae_n = mae(res["actual"], res["pred_xgb"]), mae(res["actual"], res["naive"])
    metrics = {"n_oos": len(res), "mae_xgb": round(mae_x), "mae_naive": round(mae_n),
               "r2_xgb_oos": round(r2(res["actual"], res["pred_xgb"]), 3),
               "xgb_beats_naive": bool(mae_x < mae_n),
               "note": "OOS walk-forward. 익월 가격 예측. naive=당월값 그대로."}

    # 전체 학습 후 변수 중요도 + 익월 1개월 예측
    full = df.dropna(subset=feats + ["samgyup"])
    mf = xgb.XGBRegressor(n_estimators=120, max_depth=2, learning_rate=0.05, random_state=42)
    tr = full.dropna(subset=["target"])
    mf.fit(tr[feats], tr["target"])
    imp = pd.DataFrame({"feature": feats, "importance": mf.feature_importances_}).sort_values("importance", ascending=False)
    next_pred = float(mf.predict(full[feats].iloc[[-1]])[0])
    metrics["next_month_pred"] = round(next_pred)
    metrics["next_month_from"] = str(full["date"].iloc[-1].date())

    res.to_csv(OUT / "samgyup_pred.csv", index=False, encoding="utf-8-sig")
    imp.to_csv(OUT / "samgyup_importance.csv", index=False, encoding="utf-8-sig")
    (OUT / "samgyup_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[완료] samgyup_pred.csv / samgyup_metrics.json / samgyup_importance.csv")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("\n[중요도 Top5]\n", imp.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
