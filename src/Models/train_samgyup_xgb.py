"""
[파일 정의서]
- 파일명: train_samgyup_xgb.py
- 역할: 분석 (삼겹양지 익월 가격 예측 — XGBoost, 시계열 검증)
- 입력: data/1_processed/samgyup_model_features.csv (build_samgyup_model.py 산출)
- 출력: data/3_reports/ml/ 의 samgyup_pred.csv, samgyup_metrics.json, samgyup_importance.csv
- 방법: 타겟 = 익월 가격(달력 기준 t+1). 피처 = 월 t 말에 공개된 드라이버(발표시차 반영 — 피처 CSV 에서 이미 shift)
        + AR(lag1,2, 달력 기준). walk-forward(expanding window) out-of-sample 평가. naive(당월값) baseline 과 비교.
- 시점 규칙: 피처 CSV 의 행 t 는 원계열 (t − AVAIL_LAG) 값 → 같은 행으로 t+1 을 예측해도 룩어헤드 없음.
        타깃 시계열에 빈 달이 있어 행 단위 shift 는 2개월 뒤를 '익월'로 쓰는 오류가 생김 → 연속 월 격자에서 shift.
- 결측: stock_yj 는 재고 조사 단절(2023-05) 이전이 NaN → XGBoost 결측 분기로 처리(행 삭제 안 함).
        그 외 피처는 결측 행 제외. 최신 행 예측은 실제 최신 월 행을 그대로 사용(결측 피처는 출력).
- 주의: 표본 작음 → 과적합 위험. OOS 로만 평가하고 baseline 못 이기면 그대로 보고.
"""
import sys, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED, ensure_dirs
from utils.io_safe import atomic_to_csv
import xgboost as xgb

OUT = Path(__file__).resolve().parents[2] / "data" / "3_reports" / "ml"
NAN_OK = {"stock_yj"}     # 구조적으로 앞부분이 비어 있는 피처 (XGBoost 결측 분기 사용)


def main():
    ensure_dirs(); OUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(DATA_PROCESSED / "samgyup_model_features.csv", parse_dates=["date"]).set_index("date").sort_index()
    raw = raw[~raw.index.duplicated()]
    # 연속 월 격자 (빈 달은 NaN 행) → shift 가 달력 기준이 됨
    df = raw.reindex(pd.date_range(raw.index.min(), raw.index.max(), freq="MS"))
    df.index.name = "date"
    df["samgyup_lag1"] = df["samgyup"].shift(1)
    df["samgyup_lag2"] = df["samgyup"].shift(2)
    df["target"] = df["samgyup"].shift(-1)          # 익월 가격
    df = df[df["samgyup"].notna()].reset_index()
    feats = [c for c in df.columns if c not in ("date", "samgyup", "target")]
    req = [c for c in feats if c not in NAN_OK]
    d = df.dropna(subset=req + ["target", "samgyup"]).reset_index(drop=True)
    n = len(d)
    print(f"표본 {n}개월 ({d['date'].min():%Y-%m}~{d['date'].max():%Y-%m}), 피처 {len(feats)}개 "
          f"(결측 허용: {sorted(NAN_OK & set(feats))})")

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
               "oos_period": f"{res['date'].min():%Y-%m}~{res['date'].max():%Y-%m}" if len(res) else "-",
               "note": "OOS walk-forward. 익월 가격 예측. 피처는 발표시차 반영(월말 공개값만). naive=당월값 그대로."}

    # 전체 학습 후 변수 중요도 + 익월 1개월 예측
    mf = xgb.XGBRegressor(n_estimators=120, max_depth=2, learning_rate=0.05, random_state=42)
    mf.fit(d[feats], d["target"])
    imp = pd.DataFrame({"feature": feats, "importance": mf.feature_importances_}).sort_values("importance", ascending=False)
    latest = df.iloc[[-1]]                             # 실제 최신 월 (예전 행으로 대체하지 않음)
    miss = [c for c in feats if pd.isna(latest[c].iloc[0])]
    next_pred = float(mf.predict(latest[feats])[0])
    metrics["next_month_pred"] = round(next_pred)
    metrics["next_month_from"] = str(latest["date"].iloc[0].date())
    if miss:
        metrics["next_month_missing_features"] = miss
        print(f"[주의] 최신 행 결측 피처(결측 분기로 예측): {miss}")

    atomic_to_csv(res, OUT / "samgyup_pred.csv", index=False, encoding="utf-8-sig")
    atomic_to_csv(imp, OUT / "samgyup_importance.csv", index=False, encoding="utf-8-sig")
    (OUT / "samgyup_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[완료] samgyup_pred.csv / samgyup_metrics.json / samgyup_importance.csv")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print("\n[중요도 Top5]\n", imp.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
