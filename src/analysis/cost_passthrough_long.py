"""
[파일 정의서]
- 파일명: cost_passthrough_long.py
- 역할: 분석 (재실행용 실험)
- 질문: 2019년 이후 7년이 아니라 20~30년 월간 이력으로 '수입 원가 → 국내 수입육 가격' 전가 구조(크기·시차)를
        안정적으로 추정할 수 있는가? 긴 이력으로 학습하면 최근 구간 표본외 예측이 나아지는가?
- 데이터 (전부 월간, 2026-11-09 백필로 확장):
    USDA Primal Plate(Choice USD/kg)  2005~  usda_primal_history → 미국 삼겹양지 원가
    USD/KRW 월평균                    2005~  exchange_rate_data.xlsx
    수입물가지수 쇠고기 원화/계약통화  1990~  ECOS 401Y017 (통관 단가 성격 — 원가가 국경을 넘는 시점)
    소비자물가 수입 쇠고기             1995~  ECOS 901Y009/A01202 (최종 소비자 가격)
    미트박스 미국산 도매지수           2025~  (최근 2년 — 장기 지표와의 정합 확인용)
- 분석:
    A. 교차상관: 원가 변화(USD, 원화)가 수입물가·CPI 변화를 몇 개월 선행하는가
    B. 분포시차 회귀: ΔCPI_t = a + Σ_k b_k Δcost_{t-k} (k=0..6) → 누적 전가율·R² (전체/2005~/2019~ 구간 비교)
    C. walk-forward 예측(ΔCPI 수입 쇠고기, h=1·3): naive(0) / AR / 원가 피처 / 전체, 학습 시작 2005 vs 2019 비교
       (피처는 월말 t 에 실제로 알 수 있는 값: USDA·환율 lag0, 수입물가·CPI lag1)
- 산출물: data/3_reports/analysis/cost_passthrough_long.csv (예측 요약), _xcorr.csv, _dlag.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DASHBOARD_READY_CSV, DATA_REPORTS, EXCHANGE_RATE_XLSX, MACRO_RAW_CSV,  # noqa: E402
                    USDA_PRIMAL_HISTORY_CSV)
from utils.io_safe import atomic_to_csv  # noqa: E402

OUT = DATA_REPORTS / "analysis"
LB_PER_KG = 2.20462
OOS_START = "2012-01-01"       # 예측 평가 시작 (2005 학습 시작 기준 7년 학습 후)
RECENT_OOS = "2022-01-01"      # 학습 시작 2005 vs 2019 비교용 공통 평가 구간


def _mstart(s):
    return pd.to_datetime(s, errors="coerce").dt.to_period("M").dt.to_timestamp()


def load():
    mac = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    mac["value"] = pd.to_numeric(mac["value"], errors="coerce")

    def ind(i):
        s = mac[mac["indicator_id"] == i].groupby(mac["date"].dt.to_period("M").dt.to_timestamp())["value"].mean()
        return s.sort_index()
    pr = pd.read_csv(USDA_PRIMAL_HISTORY_CSV, low_memory=False, usecols=["report_date", "primal_desc", "choice_600_900"])
    pr["m"] = _mstart(pr["report_date"])
    pr["v"] = pd.to_numeric(pr["choice_600_900"], errors="coerce") / 100 * LB_PER_KG
    plate = pr[pr["primal_desc"] == "Primal Plate"].groupby("m")["v"].mean()
    cutout = pr.groupby("m")["v"].mean()
    ex = pd.read_excel(EXCHANGE_RATE_XLSX)
    fx = pd.to_numeric(ex["Close"], errors="coerce").groupby(_mstart(ex["Date"])).mean()
    mb = pd.read_csv(DASHBOARD_READY_CSV, parse_dates=["date"], low_memory=False)
    mb = mb[(mb["category"] == "미국") & ~mb["is_filled"].astype(str).str.lower().eq("true") & mb["wholesale_price"].notna()]
    mb["m"] = mb["date"].dt.to_period("M").dt.to_timestamp()
    pv = mb.groupby(["part", "brand", "m"])["wholesale_price"].mean().unstack("m")
    lg = np.log(pv)
    mb_chg = (lg - lg.shift(1, axis=1)).mean(axis=0)
    df = pd.DataFrame({
        "cpi_imp": ind("kr_cpi_beef_imp"), "cpi_dom": ind("kr_cpi_beef_dom"), "cpi_total": ind("kr_cpi_total"),
        "impi_krw": ind("kr_impi_beef_krw"), "impi_lc": ind("kr_impi_beef_lc"),
        "plate_usd": plate, "cutout_usd": cutout, "fx": fx,
    })
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="MS"))
    df["plate_krw"] = df["plate_usd"] * df["fx"]
    df["cpi_imp_real"] = df["cpi_imp"] / df["cpi_total"]
    L = np.log(df)
    D = (L - L.shift(1)).add_prefix("d_")
    D["d_meatbox_us"] = mb_chg.reindex(D.index)
    return df, D


def xcorr(D):
    rows = []
    pairs = [("d_plate_usd", "d_impi_lc"), ("d_plate_krw", "d_impi_krw"), ("d_impi_krw", "d_cpi_imp"),
             ("d_plate_krw", "d_cpi_imp"), ("d_fx", "d_cpi_imp"), ("d_fx", "d_impi_krw"),
             ("d_plate_krw", "d_meatbox_us"), ("d_impi_krw", "d_meatbox_us"), ("d_meatbox_us", "d_cpi_imp"),
             ("d_cpi_imp", "d_cpi_imp")]
    for x, y in pairs:
        for k in range(0, 7):
            s = pd.concat([D[x].shift(k), D[y]], axis=1).dropna()
            if len(s) < 20:
                continue
            rows.append({"x_leads_by": k, "x": x, "y": y, "n": len(s), "corr": round(s.iloc[:, 0].corr(s.iloc[:, 1]), 3)})
    return pd.DataFrame(rows)


def dlag(D, cost, target, start, K=6):
    cols = [D[cost].shift(k).rename(f"b{k}") for k in range(K + 1)]
    X = pd.concat(cols, axis=1)
    s = pd.concat([D[target].rename("y"), X], axis=1).dropna()
    s = s[s.index >= start]
    if len(s) < 30:
        return None
    A = np.column_stack([np.ones(len(s)), s.iloc[:, 1:].values])
    b, *_ = np.linalg.lstsq(A, s["y"].values, rcond=None)
    resid = s["y"].values - A @ b
    r2 = 1 - resid.var() / s["y"].var()
    cum = np.cumsum(b[1:])
    return {"cost": cost, "target": target, "from": start, "n": len(s), "r2": round(r2, 3),
            "b0": round(b[1], 3), "cum_3m": round(cum[2], 3), "cum_6m": round(cum[-1], 3)}


def ridge_pred(Xtr, ytr, Xte, alpha=10.0):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
    b = np.linalg.solve(Ztr.T @ Ztr + alpha * np.eye(Ztr.shape[1]), Ztr.T @ (ytr - ytr.mean()))
    return Zte @ b + ytr.mean()


def feature_frame(D):
    """월말 t 에 알 수 있는 값으로 피처 구성. 타깃: ΔCPI(t+1), 3개월 누적 ΔCPI(t+1..t+3)."""
    F = pd.DataFrame(index=D.index)
    F["own_1"] = D["d_cpi_imp"].shift(1)                 # CPI 는 익월 초 발표 → t 말 기준 t-1 까지
    F["own_3"] = D["d_cpi_imp"].shift(1).rolling(3).sum()
    F["impi_1"] = D["d_impi_krw"].shift(1)               # 수입물가 익월 중순 발표
    F["impi_3"] = D["d_impi_krw"].shift(1).rolling(3).sum()
    F["plate_1"] = D["d_plate_krw"]                      # USDA·환율은 당월 확보
    F["plate_3"] = D["d_plate_krw"].rolling(3).sum()
    F["plate_6"] = D["d_plate_krw"].rolling(6).sum()
    F["fx_1"] = D["d_fx"]
    F["fx_3"] = D["d_fx"].rolling(3).sum()
    F["t_h1"] = D["d_cpi_imp"].shift(-1)
    F["t_h3"] = D["d_cpi_imp"].shift(-1) + D["d_cpi_imp"].shift(-2) + D["d_cpi_imp"].shift(-3)
    return F


SETS = {
    "ar": ["own_1", "own_3"],
    "cost": ["impi_1", "impi_3", "plate_1", "plate_3", "plate_6", "fx_1", "fx_3"],
    "full": ["own_1", "own_3", "impi_1", "impi_3", "plate_1", "plate_3", "plate_6", "fx_1", "fx_3"],
}


def walk(F, feats, target, train_from, oos_from, alpha=10.0):
    h = 3 if target == "t_h3" else 1
    s = F[feats + [target]].dropna()
    s = s[s.index >= train_from]
    dates = s.index[s.index >= oos_from]
    e_m, e_n, ok = [], [], []
    for t in dates:
        tr = s[s.index <= t - pd.DateOffset(months=h)]
        if len(tr) < 36:
            continue
        yhat = ridge_pred(tr[feats].values, tr[target].values, s.loc[[t], feats].values, alpha)[0]
        y = s.loc[t, target]
        e_m.append(abs(y - yhat)); e_n.append(abs(y)); ok.append(np.sign(y) == np.sign(yhat))
    if not e_m:
        return None
    return {"feats": "+".join(feats) if len(feats) < 3 else [k for k, v in SETS.items() if v == feats][0],
            "target": target, "train_from": train_from, "oos_from": oos_from, "n_oos": len(e_m),
            "mae": round(np.mean(e_m), 4), "mae_naive": round(np.mean(e_n), 4),
            "vs_naive_pct": round((np.mean(e_m) / np.mean(e_n) - 1) * 100, 1), "dir_acc": round(np.mean(ok) * 100, 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)
    df, D = load()
    print("[범위]", {c: (df[c].first_valid_index().strftime("%Y-%m"), int(df[c].notna().sum())) for c in df.columns if df[c].notna().any()})

    X = xcorr(D)
    atomic_to_csv(X, OUT / "cost_passthrough_long_xcorr.csv", index=False, encoding="utf-8-sig")
    print("\n[A] 교차상관 (x 가 k개월 선행):")
    print(X.pivot_table(index=["x", "y", "n"], columns="x_leads_by", values="corr").to_string())

    rows = []
    for cost, tgt in (("d_impi_krw", "d_cpi_imp"), ("d_plate_krw", "d_cpi_imp"), ("d_plate_krw", "d_impi_krw"),
                      ("d_plate_usd", "d_impi_lc"), ("d_fx", "d_cpi_imp")):
        for start in ("1995-01-01", "2005-01-01", "2019-01-01"):
            r = dlag(D, cost, tgt, start)
            if r:
                rows.append(r)
    DL = pd.DataFrame(rows)
    atomic_to_csv(DL, OUT / "cost_passthrough_long_dlag.csv", index=False, encoding="utf-8-sig")
    print("\n[B] 분포시차 회귀 (누적 전가율 = Σb_k):")
    print(DL.to_string(index=False))

    F = feature_frame(D)
    res = []
    for tgt in ("t_h1", "t_h3"):
        for nm, feats in SETS.items():
            res.append(walk(F, feats, tgt, "2005-01-01", OOS_START))
            res.append(walk(F, feats, tgt, "2005-01-01", RECENT_OOS))
            res.append(walk(F, feats, tgt, "2019-01-01", RECENT_OOS))
    R = pd.DataFrame([r for r in res if r])
    atomic_to_csv(R, OUT / "cost_passthrough_long.csv", index=False, encoding="utf-8-sig")
    print("\n[C] walk-forward ΔCPI(수입 쇠고기) 예측, naive(변화 0) 대비:")
    print(R.to_string(index=False))


if __name__ == "__main__":
    main()
