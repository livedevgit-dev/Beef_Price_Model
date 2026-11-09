"""
[파일 정의서]
- 파일명: proxy_target_test.py
- 역할: 분석 (재실행용)
- 질문: 데이터가 많은 한우 경락가(2019~ 일별)를 예측해서 수입육 가격 예측에 쓸 수 있는가?
        → 전제: '한우 가격 변화를 알면 수입육 가격 변화가 설명된다'를 직접 시험한다.
- 방법 (walk-forward, 확장 창, 변화율(로그) 회귀 y_t = a + b·x_t, 평가는 naive(변화 0) 대비 MAE):
    oracle  : x = 같은 기간 한우(또는 후보) 변화 — 미래를 완벽히 맞혔다고 가정한 상한
    lag1    : x = 직전 기간 변화 — 지금 실제로 알 수 있는 값
  후보 x: 한우 경락(전국 전체 등급, 두수 가중), 수입 쇠고기 수입물가지수(원화), 원화 환산 미국 원가(플레이트×환율)
  타깃 y: 미트박스 미국·호주 도매지수(2025~), KAMIS 수입 소매지수(2022~), 수입 쇠고기 CPI(2019~), 삼겹양지(월)
  ※ 지수는 품목·브랜드별 자기 평균으로 정규화 후 평균(구성 변화 제거)
- 산출물: data/3_reports/analysis/proxy_target_test.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DASHBOARD_READY_CSV, DATA_PROCESSED, DATA_REPORTS, EXCHANGE_RATE_XLSX,  # noqa: E402
                    HANWOO_DASHBOARD_CSV, MACRO_RAW_CSV, USDA_PLATE_USD_KG_CSV)
from utils.io_safe import atomic_to_csv  # noqa: E402

OUT = DATA_REPORTS / "analysis"
MIN_TRAIN = {"M": 12, "W": 26}


def norm_index(df, key_cols, date_col, val_col, freq):
    """키(품목·브랜드)별 기간 평균 → 자기 평균으로 정규화 → 기간별 평균 지수."""
    d = df.copy()
    d["p"] = d[date_col].dt.to_period(freq).dt.start_time
    pv = d.groupby(key_cols + ["p"])[val_col].mean().unstack(key_cols)
    pv = pv / pv.mean()
    full = pv.reindex(pd.date_range(pv.index.min(), pv.index.max(), freq="MS" if freq == "M" else "W-MON"))
    # 연속 기간에 같은 키끼리 비교한 로그 변화의 평균(체인) → 구성 변화 영향 제거
    chg = np.log(full / full.shift(1)).mean(axis=1, skipna=True).where(np.log(full / full.shift(1)).notna().sum(axis=1) >= 3)
    return chg


def load():
    S = {}
    # 한우 경락 (전국, 전체 등급, 두수 가중)
    h = pd.read_csv(HANWOO_DASHBOARD_CSV, low_memory=False, parse_dates=["date"])
    n = h[(h["source"] == "ekape_auction") & (h["is_national_total"].astype(str) == "True") & (h["grade"] == "전체")]
    w = pd.to_numeric(n["head_count"], errors="coerce").fillna(0)
    amt = (n["price_won_per_kg"] * w).groupby(n["date"]).sum()
    heads = w.groupby(n["date"]).sum()
    daily = (amt / heads.where(heads > 0)).dropna()
    for f, rule in (("M", "MS"), ("W", "W-MON")):
        a = (daily * heads.reindex(daily.index)).resample(rule, label="left", closed="left").sum()
        b = heads.reindex(daily.index).resample(rule, label="left", closed="left").sum()
        lvl = a / b.where(b > 0)
        S[("x_hanwoo", f)] = np.log(lvl / lvl.shift(1))
    # KAMIS 수입 소매 지수
    k = h[h["source"] == "kamis_retail_import"].dropna(subset=["price_won_per_kg"])
    if "is_outlier" in k.columns:
        k = k[~k["is_outlier"].astype(str).str.lower().eq("true")]
    for f in ("M", "W"):
        S[("y_kamis_import_retail", f)] = norm_index(k, ["part", "origin"], "date", "price_won_per_kg", f)
    # 미트박스 도매지수 (실관측만)
    d = pd.read_csv(DASHBOARD_READY_CSV, parse_dates=["date"])
    d = d[~d["is_filled"].astype(str).str.lower().eq("true") & d["wholesale_price"].notna()]
    for cat, nm in (("미국", "y_meatbox_us"), ("호주", "y_meatbox_au")):
        for f in ("M", "W"):
            S[(nm, f)] = norm_index(d[d["category"] == cat], ["part", "brand"], "date", "wholesale_price", f)
    # 삼겹양지 월
    sg = pd.read_csv(DATA_PROCESSED / "samgyup_unified_monthly.csv", parse_dates=["date"]).set_index("date")["price_won_per_kg"]
    sg = sg.reindex(pd.date_range(sg.index.min(), sg.index.max(), freq="MS"))
    S[("y_samgyup", "M")] = np.log(sg / sg.shift(1))
    # 월간 거시: 수입 쇠고기 CPI(타깃), 수입물가지수(후보)
    mac = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    for ind, nm in (("kr_cpi_beef_imp", "y_cpi_beef_imp"), ("kr_impi_beef_krw", "x_impi_beef_krw")):
        s = mac[mac["indicator_id"] == ind].set_index("date")["value"].sort_index()
        s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS"))
        S[(nm, "M")] = np.log(s / s.shift(1))
    # 원화 환산 미국 원가
    u = pd.read_csv(USDA_PLATE_USD_KG_CSV, parse_dates=["report_date"])
    plate = u[u["primal_desc"].str.contains("Plate", case=False, na=False)].groupby("report_date")["choice_usd_per_kg"].mean()
    ex = pd.read_excel(EXCHANGE_RATE_XLSX)
    fx = pd.Series(pd.to_numeric(ex["Close"], errors="coerce").values, index=pd.to_datetime(ex["Date"])).dropna()
    cost = (plate * fx.reindex(plate.index, method="ffill")).dropna()
    for f, rule in (("M", "MS"), ("W", "W-MON")):
        lvl = cost.resample(rule, label="left", closed="left").mean()
        S[("x_krw_cost", f)] = np.log(lvl / lvl.shift(1))
    return S


def walk(y, x, min_train):
    df = pd.concat([y, x], axis=1, keys=["y", "x"]).dropna()
    errs_m, errs_n = [], []
    for k in range(min_train, len(df)):
        tr = df.iloc[:k]
        b = np.polyfit(tr["x"], tr["y"], 1) if tr["x"].std() > 0 else (0.0, tr["y"].mean())
        pred = b[0] * df["x"].iloc[k] + b[1]
        errs_m.append(abs(df["y"].iloc[k] - pred))
        errs_n.append(abs(df["y"].iloc[k]))
    if not errs_m:
        return None
    r = float(df["y"].corr(df["x"]))
    return {"n_total": len(df), "n_oos": len(errs_m), "corr": round(r, 3),
            "vs_naive_pct": round((np.mean(errs_m) / np.mean(errs_n) - 1) * 100, 1)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    S = load()
    rows = []
    for (yn, f), y in S.items():
        if not yn.startswith("y_"):
            continue
        for (xn, fx_), x in S.items():
            if not xn.startswith("x_") or fx_ != f:
                continue
            for mode, xs in (("oracle", x), ("lag1", x.shift(1))):
                res = walk(y, xs, MIN_TRAIN[f])
                if res:
                    rows.append({"target": yn, "freq": f, "candidate": xn, "mode": mode, **res})
    out = pd.DataFrame(rows).sort_values(["target", "freq", "mode", "vs_naive_pct"])
    atomic_to_csv(out, OUT / "proxy_target_test.csv", index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 200)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
