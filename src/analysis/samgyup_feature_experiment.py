"""
[파일 정의서]
- 파일명: samgyup_feature_experiment.py
- 역할: 분석 (재실행용 실험)
- 목적: 2026-10-30 추가 지표(원가·물류·소비·호주축)가 삼겹양지 익월가 예측을 실제로 개선하는지
        walk-forward(expanding) 표본외 검증으로 비교. 운영 예측기는 바꾸지 않는다.
- 비교 대상 (모두 '익월 가격' 예측, 평가는 같은 OOS 달):
    naive        : 당월값 그대로
    xgb_level    : 현재 운영 XGB 와 같은 방식(가격 수준 직접 예측)
    ridge_base   : 익월 변화율(%) 을 기존 피처의 변화율로 예측 (릿지, 강한 축소) → 당월값 × (1+예측)
    ridge_new    : ridge_base + 신규 지표 변화율
    xgb_chg_new  : 변화율 예측 XGB (기존+신규)
    ridge_core   : 핵심 원가(미국 플레이트 원가·환율) + 자기 모멘텀만, ridge_core_diesel: + 국내 경유
- 피처 시차: build_samgyup_model.AVAIL_LAG + 신규 지표 NEW_LAG (월말에 실제로 알 수 있는 값만)
- 산출물: data/3_reports/analysis/samgyup_feature_experiment.csv (모델별 MAE·naive 대비), _pred.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED, DATA_REPORTS, MACRO_RAW_CSV  # noqa: E402
from utils.io_safe import atomic_to_csv  # noqa: E402

OUT_DIR = DATA_REPORTS / "analysis"

# 신규 지표와 발표시차(개월): 월간 통계는 익월 공표(1), 일·주간 시장가격은 당월 확보(0)
NEW_LAG = {
    "kr_cpi_diesel": 1, "kr_cpi_dineout_beef": 1, "kr_cpi_dineout": 1, "kr_impi_beef_lc": 1,
    "kr_impi_beef_krw": 1, "kr_ppi_road_freight": 1, "kr_ppi_cold_storage": 1, "kr_ppi_ocean_freight": 1,
    "kr_retail_food": 2, "au_beef_price": 1, "us_fed_steer": 1, "us_ppi_ocean_freight": 1,
    "kr_fx_aud": 0, "us_diesel": 0, "au_eyci": 0, "au_heavy_steer": 0,
}
BASE_EXCLUDE = {"samgyup"}
MIN_TRAIN = 18
RIDGE_ALPHA = 10.0


def load_frame():
    f = pd.read_csv(DATA_PROCESSED / "samgyup_model_features.csv", parse_dates=["date"]).set_index("date").sort_index()
    f = f[~f.index.duplicated()]
    grid = pd.date_range(f.index.min(), f.index.max(), freq="MS")
    f = f.reindex(grid)
    mac = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    mac["m"] = mac["date"].dt.to_period("M").dt.to_timestamp()
    mac["value"] = pd.to_numeric(mac["value"], errors="coerce")
    new_cols = []
    for ind, lag in NEW_LAG.items():
        s = mac[mac["indicator_id"] == ind].groupby("m")["value"].mean()
        if s.empty:
            continue
        g = s.reindex(pd.date_range(min(s.index.min(), grid.min()), grid.max(), freq="MS"))
        f[ind] = g.shift(lag).reindex(grid)
        new_cols.append(ind)
    return f, new_cols


def pct(s):
    return (s / s.shift(1) - 1) * 100


def walk_forward(d, feats, kind):
    """d: 연속 월 격자(행=월). target_chg = 익월 변화율. 반환: OOS 예측가 Series."""
    from sklearn.linear_model import Ridge
    import xgboost as xgb
    preds = {}
    rows = d.dropna(subset=["target", "samgyup"]).index
    for k, t in enumerate(rows):
        if k < MIN_TRAIN:
            continue
        tr = d.loc[rows[:k]]
        if kind == "xgb_level":
            Xtr, ytr = tr[feats], tr["target"]
            m = xgb.XGBRegressor(n_estimators=120, max_depth=2, learning_rate=0.05,
                                 subsample=0.8, colsample_bytree=0.8, random_state=42)
            m.fit(Xtr, ytr)
            preds[t] = float(m.predict(d.loc[[t], feats])[0])
            continue
        tr = tr.dropna(subset=["target_chg"])
        Xtr, ytr = tr[feats], tr["target_chg"]
        if kind.startswith("ridge"):
            mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
            Xz = ((Xtr - mu) / sd).fillna(0)
            m = Ridge(alpha=RIDGE_ALPHA).fit(Xz, ytr)
            x = ((d.loc[[t], feats] - mu) / sd).fillna(0)
            chg = float(m.predict(x)[0])
        else:
            m = xgb.XGBRegressor(n_estimators=150, max_depth=2, learning_rate=0.05,
                                 subsample=0.8, colsample_bytree=0.8, random_state=42)
            m.fit(Xtr, ytr)
            chg = float(m.predict(d.loc[[t], feats])[0])
        preds[t] = d.loc[t, "samgyup"] * (1 + chg / 100)
    return pd.Series(preds)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    f, new_cols = load_frame()
    base_cols = [c for c in f.columns if c not in BASE_EXCLUDE and c not in new_cols]
    d = f.copy()
    d["target"] = d["samgyup"].shift(-1)
    d["target_chg"] = pct(d["samgyup"]).shift(-1)
    # 변화율 피처 (연속 월끼리만), 가격 자체 모멘텀 포함
    # 0·음수가 있는 계열(기온·강수·중국 수출 등)은 변화율 대신 차분
    chg = pd.DataFrame({f"{c}_chg": (pct(d[c]) if (d[c].dropna() > 0).all() else d[c].diff())
                        for c in base_cols + new_cols}, index=d.index)
    chg["samgyup_chg"] = pct(d["samgyup"])
    chg = chg.replace([np.inf, -np.inf], np.nan)
    d = d.join(chg)
    base_chg = [f"{c}_chg" for c in base_cols] + ["samgyup_chg"]
    new_chg = [f"{c}_chg" for c in new_cols]
    # 레벨 XGB 는 운영과 같이 레벨 피처 + AR
    d["samgyup_lag1"] = d["samgyup"].shift(1)
    d["samgyup_lag2"] = d["samgyup"].shift(2)
    lvl_feats = base_cols + ["samgyup_lag1", "samgyup_lag2"]

    # 공통 OOS 대상: 변화율 타깃·당월 변화율이 모두 있는 달 (가장 엄격한 집합에 맞춤)
    usable = d.dropna(subset=["target", "samgyup", "target_chg", "samgyup_chg"])
    d = d.loc[usable.index.min():]
    models = {
        "xgb_level": walk_forward(d, lvl_feats, "xgb_level"),
        "ridge_base": walk_forward(d, base_chg, "ridge"),
        "ridge_new": walk_forward(d, base_chg + new_chg, "ridge"),
        "xgb_chg_new": walk_forward(d, base_chg + new_chg, "xgb_chg"),
        # 소수 핵심 원가 피처만 (과적합 점검): 미국 원가·환율 [+ 경유]
        "ridge_core": walk_forward(d, ["samgyup_chg", "usda_plate_chg", "fx_chg"], "ridge"),
        "ridge_core_diesel": walk_forward(d, ["samgyup_chg", "usda_plate_chg", "fx_chg", "kr_cpi_diesel_chg"], "ridge"),
    }
    common = None
    for s in models.values():
        common = s.index if common is None else common.intersection(s.index)
    res = pd.DataFrame({k: v.reindex(common) for k, v in models.items()})
    res["naive"] = d.loc[common, "samgyup"]
    res["actual"] = d.loc[common, "target"]
    res = res.dropna(subset=["actual"])

    rows = []
    mae_n = float(np.mean(np.abs(res["actual"] - res["naive"])))
    for k in ["naive"] + list(models):
        err = res["actual"] - res[k]
        rows.append({"model": k, "mae": round(float(np.mean(np.abs(err)))),
                     "vs_naive_pct": round((float(np.mean(np.abs(err))) / mae_n - 1) * 100, 1),
                     "dir_hit_pct": round(float(np.mean(np.sign(res[k] - res["naive"]) ==
                                                         np.sign(res["actual"] - res["naive"]))) * 100, 1)
                     if k != "naive" else None,
                     "n_oos": len(res), "oos_from": f"{res.index.min():%Y-%m}", "oos_to": f"{res.index.max():%Y-%m}"})
    out = pd.DataFrame(rows)
    atomic_to_csv(out, OUT_DIR / "samgyup_feature_experiment.csv", index=False, encoding="utf-8-sig")
    atomic_to_csv(res.round(0).reset_index(names="date"), OUT_DIR / "samgyup_feature_experiment_pred.csv",
                  index=False, encoding="utf-8-sig")
    print(f"신규 지표 {len(new_cols)}개: {new_cols}")
    print(f"기존 피처 {len(base_cols)}개: {base_cols}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
