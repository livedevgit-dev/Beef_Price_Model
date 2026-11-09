"""
[파일 정의서]
- 파일명: panel_cost_model.py
- 역할: 분석 (재실행용 실험)
- 질문: 삼겹양지 한 품목(월 22개)이 아니라 미트박스 전 품목(부위×원산지)을 한 모델로 묶어 학습하면
        표본 확대로 '다음 기간 변화'를 naive 보다 잘 맞힐 수 있는가?
- 설계:
    · 단위: 미트박스 (원산지, 부위) 지수. 브랜드별 기간 평균을 로그로 바꾼 뒤 연속 기간에
      같은 브랜드끼리 비교한 로그 변화의 평균(체인) → 브랜드 구성 변화 영향 제거. 실관측(is_filled=False)만 사용.
    · 빈도: 월(M)·주(W). 예측 대상 = 다음 기간 로그 변화 (h=1), 추가로 월 h=3(3개월 누적 변화).
    · 피처(모두 t 시점에 알 수 있는 값):
        own_1, own_3        : 자기 최근 1·3기간 로그 변화 (모멘텀/되돌림)
        cost_1, cost_3      : 매핑된 USDA 부위 원가(USD/kg, Choice, 코드 없으면 프라이멀)×환율 의 최근 1·3기간 로그 변화
        cost_1_lag1..3      : 원가 변화의 1~3기간 지연 (전가 시차)
        gap                 : log(미트박스 지수 / 원화 원가 지수) 를 품목별 과거 평균으로 뺀 값 (마진 괴리, 오차수정항)
        fx_1                : 환율(미국: USD, 호주: AUD) 1기간 로그 변화
        is_au               : 호주산 더미 (USDA 원가는 proxy)
    · 모델: 풀링 릿지(표준화, 고정 alpha), 풀링 XGB(얕은 트리) — walk-forward(기간 t 이전 전 품목 행으로 학습 → t 행 예측).
    · 평가: 전체 패널 MAE 와 품목별 MAE 의 naive(변화 0) 대비, 방향 적중률, 삼겹양지(미국) 단독 결과.
      비교군: 품목별 단독 릿지(같은 피처, 자기 이력만) → 풀링의 표본 확대 효과 분리.
- 산출물: data/3_reports/analysis/panel_cost_model.csv (모델×빈도×h 요약), panel_cost_model_by_item.csv
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DASHBOARD_READY_CSV, DATA_REPORTS, EXCHANGE_RATE_XLSX, MACRO_RAW_CSV,  # noqa: E402
                    USDA_BEEF_HISTORY_CSV, USDA_PRIMAL_HISTORY_CSV)
from utils.io_safe import atomic_to_csv  # noqa: E402
from utils.part_mapping import CANONICAL_PARTS, meatbox_to_canonical  # noqa: E402

OUT = DATA_REPORTS / "analysis"
MIN_TRAIN = {"M": 8, "W": 20}        # 패널은 기간당 행이 ~35개라 초기 학습 기간을 짧게 둘 수 있음
MIN_BRANDS = 2                       # 체인 변화 계산에 필요한 최소 브랜드 쌍
LB_PER_KG = 2.20462
FREQ_RULE = {"M": "MS", "W": "W-MON"}
_CODE_RE = re.compile(r"\(([0-9A-Z]+)\s+\d\)")
FEATS = ["own_1", "own_3", "cost_1", "cost_3", "cost_1_lag1", "cost_1_lag2", "cost_1_lag3", "gap", "fx_1", "is_au"]
COST_FEATS = ["cost_1", "cost_3", "cost_1_lag1", "cost_1_lag2", "cost_1_lag3", "gap", "fx_1", "is_au"]
OWN_FEATS = ["own_1", "own_3"]


def _period(s, f):
    return s.dt.to_period(f).dt.start_time


def chain_change(df, key, date_col, val_col, f):
    """키(브랜드)별 기간 평균 → 연속 기간 같은 키의 로그 변화 평균(체인)."""
    d = df.copy()
    d["p"] = _period(d[date_col], f)
    pv = d.groupby([key, "p"])[val_col].mean().unstack(key)
    pv = pv.reindex(pd.date_range(pv.index.min(), pv.index.max(), freq=FREQ_RULE[f]))
    lg = np.log(pv)
    dif = lg - lg.shift(1)
    return dif.mean(axis=1).where(dif.notna().sum(axis=1) >= MIN_BRANDS)


def usda_cut_cost(f):
    """USDA 코드별 Choice USD/kg 기간 평균 + 프라이멀 USD/kg (열 = 코드 또는 프라이멀명)."""
    u = pd.read_csv(USDA_BEEF_HISTORY_CSV, low_memory=False,
                    usecols=["report_date", "item_description", "weighted_average", "grade"])
    u = u[u["grade"] == "Choice"].copy()
    u["code"] = u["item_description"].str.extract(_CODE_RE)[0]
    u["d"] = pd.to_datetime(u["report_date"], format="%m/%d/%Y", errors="coerce")
    u["usd_kg"] = pd.to_numeric(u["weighted_average"], errors="coerce") / 100 * LB_PER_KG
    u = u.dropna(subset=["code", "d", "usd_kg"])
    u["p"] = _period(u["d"], f)
    cuts = u.groupby(["code", "p"])["usd_kg"].mean().unstack("code")
    pr = pd.read_csv(USDA_PRIMAL_HISTORY_CSV, low_memory=False, usecols=["report_date", "primal_desc", "choice_600_900"])
    pr["d"] = pd.to_datetime(pr["report_date"], format="%m/%d/%Y", errors="coerce")
    pr["usd_kg"] = pd.to_numeric(pr["choice_600_900"], errors="coerce") / 100 * LB_PER_KG
    pr["p"] = _period(pr["d"], f)
    prim = pr.dropna(subset=["d", "usd_kg"]).groupby(["primal_desc", "p"])["usd_kg"].mean().unstack("primal_desc")
    return pd.concat([cuts, prim], axis=1)


def fx_series(f):
    ex = pd.read_excel(EXCHANGE_RATE_XLSX)
    usd = pd.Series(pd.to_numeric(ex["Close"], errors="coerce").values, index=pd.to_datetime(ex["Date"])).dropna()
    mac = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    aud = mac[mac["indicator_id"] == "kr_fx_aud"].set_index("date")["value"].astype(float).sort_index()
    out = {}
    for nm, s in (("USD", usd), ("AUD", aud)):
        out[nm] = s.groupby(_period(s.index.to_series(), f)).mean()
    return out


def cost_key_for(part):
    cid = meatbox_to_canonical(part)
    spec = next((p for p in CANONICAL_PARTS if p.canonical_id == cid), None)
    if spec is None:
        return None, None
    return (list(spec.usda_codes) or None), spec.usda_primal


def build_panel(f):
    d = pd.read_csv(DASHBOARD_READY_CSV, parse_dates=["date"], low_memory=False)
    d = d[~d["is_filled"].astype(str).str.lower().eq("true") & d["wholesale_price"].notna()]
    d = d[d["category"].isin(["미국", "호주"])]
    usda = usda_cut_cost(f)
    fx = fx_series(f)
    rows = []
    for (cat, part), g in d.groupby(["category", "part"]):
        if g["date"].nunique() < (12 if f == "M" else 40):
            continue
        codes, primal = cost_key_for(part)
        if codes is None and primal is None:
            continue
        cols = [c for c in (codes or []) if c in usda.columns] or ([primal] if primal in usda.columns else [])
        if not cols:
            continue
        y_chg = chain_change(g, "brand", "date", "wholesale_price", f)
        cost_usd = usda[cols].mean(axis=1)
        fxs = fx["AUD" if cat == "호주" else "USD"]
        idx = pd.date_range(min(y_chg.index.min(), cost_usd.index.min()), y_chg.index.max(), freq=FREQ_RULE[f])
        cost_krw = (cost_usd.reindex(idx) * fx["USD"].reindex(idx)).ffill(limit=1)   # 원가 결제는 USD
        lc = np.log(cost_krw)
        ly = y_chg.reindex(idx).cumsum()
        gap_raw = ly - lc
        df = pd.DataFrame(index=idx)
        df["y_chg"] = y_chg.reindex(idx)
        df["own_1"] = df["y_chg"]
        df["own_3"] = df["y_chg"].rolling(3).sum()
        df["cost_1"] = lc - lc.shift(1)
        df["cost_3"] = lc - lc.shift(3)
        for k in (1, 2, 3):
            df[f"cost_1_lag{k}"] = df["cost_1"].shift(k)
        df["gap"] = gap_raw - gap_raw.expanding().mean()
        lfx = np.log(fxs.reindex(idx))
        df["fx_1"] = lfx - lfx.shift(1)
        df["is_au"] = int(cat == "호주")
        df["target_h1"] = df["y_chg"].shift(-1)
        if f == "M":
            df["target_h3"] = df["y_chg"].shift(-1) + df["y_chg"].shift(-2) + df["y_chg"].shift(-3)
        df["item"] = f"{cat}·{part}"
        df["cost_src"] = "+".join(cols)
        rows.append(df.reset_index().rename(columns={"index": "date"}))
    return pd.concat(rows, ignore_index=True)


def ridge_fit_predict(Xtr, ytr, Xte, alpha):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    Ztr, Zte = (Xtr - mu) / sd, (Xte - mu) / sd
    A = Ztr.T @ Ztr + alpha * np.eye(Ztr.shape[1])
    b = np.linalg.solve(A, Ztr.T @ (ytr - ytr.mean()))
    return Zte @ b + ytr.mean()


def walk(panel, target, f, model, feats=FEATS, pooled=True, alpha=30.0):
    """기간 순 walk-forward. pooled=False 면 품목별 자기 이력만으로 학습."""
    p = panel.dropna(subset=feats + [target]).sort_values("date")
    periods = sorted(p["date"].unique())
    h = 3 if target.endswith("h3") else 1
    preds = []
    xgb = None
    if model == "xgb":
        import xgboost as xgb_mod
        xgb = xgb_mod
    for i in range(MIN_TRAIN[f], len(periods)):
        t = periods[i]
        te = p[p["date"] == t]
        # 학습 행: 타깃이 t 시점에 확정된 행만 (h 기간 앞 타깃 → 누수 방지)
        cutoff = periods[i - h]
        tr_all = p[p["date"] <= cutoff]
        for item, te_i in te.groupby("item"):
            tr = tr_all if pooled else tr_all[tr_all["item"] == item]
            if len(tr) < (6 if not pooled else 30):
                continue
            Xtr, ytr, Xte = tr[feats].values, tr[target].values, te_i[feats].values
            if model == "ridge":
                yhat = ridge_fit_predict(Xtr, ytr, Xte, alpha)
            else:
                m = xgb.XGBRegressor(n_estimators=200, max_depth=2, learning_rate=0.03, subsample=0.8,
                                     colsample_bytree=0.8, min_child_weight=10, reg_lambda=5.0, verbosity=0)
                m.fit(Xtr, ytr)
                yhat = m.predict(Xte)
            preds.append(pd.DataFrame({"date": t, "item": item, "y": te_i[target].values, "yhat": yhat}))
    if not preds:
        return None
    out = pd.concat(preds, ignore_index=True)
    out["e_m"] = (out["y"] - out["yhat"]).abs()
    out["e_n"] = out["y"].abs()
    out["dir_ok"] = np.sign(out["y"]) == np.sign(out["yhat"])
    return out


def summarize(out, name, f, target):
    if out is None:
        return None, None
    tot = {"model": name, "freq": f, "target": target, "n_oos": len(out), "n_items": out["item"].nunique(),
           "mae_model": round(out["e_m"].mean(), 4), "mae_naive": round(out["e_n"].mean(), 4),
           "vs_naive_pct": round((out["e_m"].mean() / out["e_n"].mean() - 1) * 100, 1),
           "dir_acc": round(out["dir_ok"].mean() * 100, 1)}
    sg = out[out["item"] == "미국·삼겹양지"]
    if len(sg):
        tot["samgyup_vs_naive_pct"] = round((sg["e_m"].mean() / sg["e_n"].mean() - 1) * 100, 1)
        tot["samgyup_n"] = len(sg)
    by = out.groupby("item").agg(n=("y", "size"), mae_model=("e_m", "mean"), mae_naive=("e_n", "mean"), dir_acc=("dir_ok", "mean"))
    by["vs_naive_pct"] = (by["mae_model"] / by["mae_naive"] - 1) * 100
    by = by.assign(model=name, freq=f, target=target).reset_index()
    return tot, by


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summ, items = [], []
    for f in ("M", "W"):
        panel = build_panel(f)
        n_items = panel["item"].nunique()
        print(f"[{f}] 패널 품목 {n_items}개, 행 {panel['y_chg'].notna().sum()}개 "
              f"(기간 {panel['date'].min():%Y-%m-%d}~{panel['date'].max():%Y-%m-%d})")
        targets = ["target_h1"] + (["target_h3"] if f == "M" else [])
        for tg in targets:
            runs = {
                "pooled_ridge": walk(panel, tg, f, "ridge", pooled=True),
                "pooled_ridge_cost_only": walk(panel, tg, f, "ridge", feats=COST_FEATS, pooled=True),
                "pooled_ridge_own_only": walk(panel, tg, f, "ridge", feats=OWN_FEATS, pooled=True),
                "pooled_xgb": walk(panel, tg, f, "xgb", pooled=True),
                "item_ridge": walk(panel, tg, f, "ridge", pooled=False, alpha=5.0),
            }
            for nm, out in runs.items():
                tot, by = summarize(out, nm, f, tg)
                if tot:
                    summ.append(tot)
                    items.append(by)
    S = pd.DataFrame(summ)
    I = pd.concat(items, ignore_index=True)
    atomic_to_csv(S, OUT / "panel_cost_model.csv", index=False, encoding="utf-8-sig")
    atomic_to_csv(I, OUT / "panel_cost_model_by_item.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    print(S.to_string(index=False))
    best = I[(I["model"] == "pooled_ridge") & (I["freq"] == "M") & (I["target"] == "target_h1")].sort_values("vs_naive_pct")
    print("\n[월 h1 pooled_ridge 품목별 naive 대비 %]")
    print(best[["item", "n", "vs_naive_pct", "dir_acc"]].to_string(index=False))


if __name__ == "__main__":
    main()
