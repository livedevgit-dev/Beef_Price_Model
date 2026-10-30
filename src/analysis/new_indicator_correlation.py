"""
[파일 정의서]
- 파일명: new_indicator_correlation.py
- 역할: 분석 (재실행용)
- 주요 기능: 2026-10-30 추가한 원가·물류·소비 지표 ↔ 수입육 도매가(삼겹양지, 미트박스 미국/호주 지수)
  월간 MoM% 상관 (지표 선행 lag 0~4개월, Bonferroni ×5 보정 p). 검토 후 미수집한 후보는 ECOS 에서 즉석 조회.
- 산출물: data/3_reports/analysis/new_indicator_correlation.csv
- 주의: 조합이 많아(지표×lag×타깃×기간) 우연한 |r|≈0.45 가 여럿 나올 수 있음 — 기간 분할·부호 안정성으로 재확인할 것
"""
import os
import sys
import numpy as np
import pandas as pd
import requests
import urllib3
from scipy import stats
from dotenv import load_dotenv

urllib3.disable_warnings()
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROJECT_ROOT  # noqa: E402
from utils.io_safe import atomic_to_csv  # noqa: E402

ROOT = str(PROJECT_ROOT)

load_dotenv(ROOT + r"\.env")
OUT = ROOT + r"\data\3_reports\analysis\new_indicator_correlation.csv"

NEW = {
    "kr_impi_beef_krw": "ECOS 401Y017/10121201AA/W", "kr_impi_beef_lc": "ECOS 401Y017/10121201AA/C",
    "kr_fx_aud": "ECOS 731Y001/0000017", "kr_cpi_diesel": "ECOS 901Y009/G02102",
    "kr_ppi_road_freight": "ECOS 404Y014/501122AA", "kr_ppi_cold_storage": "ECOS 404Y016/50143102AA",
    "kr_ppi_ocean_freight": "ECOS 404Y016/50121201AA", "kr_cpi_dineout": "ECOS 901Y009/K011",
    "kr_cpi_dineout_beef": "ECOS 901Y009/K01110", "kr_retail_food": "ECOS 901Y100/G31/T3",
    "au_beef_price": "FRED PBEEFUSDM", "us_fed_steer": "FRED WPU013101", "us_diesel": "FRED GASDESW",
    "us_ppi_ocean_freight": "FRED PCU483111483111", "au_eyci": "MLA indicator 0", "au_heavy_steer": "MLA indicator 4",
}
# 비교 기준(기존 수집 지표)
BENCH = {"kr_cpi_beef_imp": "ECOS 901Y009/A01202 (기존)", "us_wti": "FRED DCOILWTICO (기존)",
         "us_corn": "FRED PMAIZMTUSDM (기존)"}
# 검토만 하고 수집하지 않은 후보 (ad hoc 조회)
ADHOC = {
    "x_impi_beef_usd": ("401Y017", "10121201AA/D", "수입물가 쇠고기 달러기준"),
    "x_cpi_bulgogi": ("901Y009", "K01109", "CPI 불고기(외식)"),
    "x_cpi_galbitang": ("901Y009", "K01105", "CPI 갈비탕(외식)"),
    "x_cpi_gasoline": ("901Y009", "G02101", "CPI 휘발유"),
    "x_ppi_beef": ("404Y016", "10121201AA", "PPI 쇠고기(국내 생산)"),
}


def monthly_from_raw():
    r = pd.read_csv(ROOT + r"\data\0_raw\macro_indicators_raw.csv", parse_dates=["date"])
    r = r[r.indicator_id.isin(list(NEW) + list(BENCH))]
    r["m"] = r["date"].dt.to_period("M")
    return r.groupby(["indicator_id", "m"])["value"].mean().unstack(0)


def adhoc():
    key = os.getenv("ECOS_API_KEY")
    out = {}
    for iid, (sc, item, _) in ADHOC.items():
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/1000/{sc}/M/201901/202610/{item}"
        rows = requests.get(url, verify=False, timeout=60).json()["StatisticSearch"]["row"]
        s = pd.Series({pd.Period(r["TIME"][:4] + "-" + r["TIME"][4:], "M"): float(r["DATA_VALUE"]) for r in rows})
        out[iid] = s
    usd = pd.read_excel(ROOT + r"\data\0_raw\exchange_rate_data.xlsx")
    usd["m"] = pd.to_datetime(usd["Date"]).dt.to_period("M")
    out["x_fx_usd"] = pd.to_numeric(usd["Close"], errors="coerce").groupby(usd["m"]).mean()
    return pd.DataFrame(out)


def mom_consecutive(s: pd.Series) -> pd.Series:
    """연속된 달끼리만 MoM% (공백 달 건너뛴 변화는 제외)."""
    s = s.dropna().sort_index()
    full = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="M"))
    return (full / full.shift(1) - 1) * 100


def targets():
    t = {}
    sg = pd.read_csv(ROOT + r"\data\1_processed\samgyup_unified_monthly.csv", parse_dates=["date"])
    sg = sg.set_index(sg["date"].dt.to_period("M"))["price_won_per_kg"]
    t["samgyup"] = mom_consecutive(sg)
    d = pd.read_csv(ROOT + r"\data\2_dashboard\dashboard_ready_data.csv", low_memory=False, parse_dates=["date"])
    d = d[(d["is_filled"].astype(str) == "False") & d["wholesale_price"].notna()]
    d["m"] = d["date"].dt.to_period("M")
    # 품목(부위)별 월평균 → 자기 평균으로 정규화 → 같은 달에 연속 존재하는 부위끼리만 MoM 평균(체인지수)
    for cat, key in [("미국", "us_wholesale_idx"), ("호주", "au_wholesale_idx")]:
        pm = d[d["category"] == cat].groupby(["part", "m"])["wholesale_price"].mean().unstack(0)
        pm = pm / pm.mean()
        full = pm.reindex(pd.period_range(pm.index.min(), pm.index.max(), freq="M"))
        part_mom = (full / full.shift(1) - 1) * 100
        t[key] = part_mom.mean(axis=1, skipna=True).where(part_mom.notna().sum(axis=1) >= 3)
    return pd.DataFrame(t)


def main():
    ind = monthly_from_raw().join(adhoc(), how="outer")
    ind_mom = pd.DataFrame({c: mom_consecutive(ind[c]) for c in ind.columns})
    tg = targets()
    meta = {**{k: (v, "new") for k, v in NEW.items()}, **{k: (v, "benchmark") for k, v in BENCH.items()},
            **{k: (f"ECOS {v[0]}/{v[1]} ({v[2]})", "rejected_candidate") for k, v in ADHOC.items()},
            "x_fx_usd": ("exchange_rate_data.xlsx USD/KRW (기존)", "benchmark")}
    periods = {
        "samgyup": [("2023-01+", pd.Period("2023-01", "M")), ("2019-01+", pd.Period("2019-01", "M"))],
        "us_wholesale_idx": [("2025-01+ (meatbox 전체)", pd.Period("2025-01", "M"))],
        "au_wholesale_idx": [("2025-01+ (meatbox 전체)", pd.Period("2025-01", "M"))],
    }
    rows = []
    for col in ind_mom.columns:
        for tgt, plist in periods.items():
            for pname, pstart in plist:
                for lag in range(5):
                    x = ind_mom[col].shift(lag)  # 지표가 lag 개월 선행
                    df = pd.concat([x, tg[tgt]], axis=1, keys=["x", "y"]).dropna()
                    df = df[df.index >= pstart]
                    n = len(df)
                    if n < 6 or df["x"].std() == 0:
                        r, p = np.nan, np.nan
                    else:
                        r, p = stats.pearsonr(df["x"], df["y"])
                    rows.append({"indicator_id": col, "source_code": meta[col][0], "group": meta[col][1],
                                 "target": tgt, "period": pname, "lag_months": lag, "corr": r, "p_value": p, "n": n})
    res = pd.DataFrame(rows)
    # 지표·타깃·기간별 |corr| 최대 lag 표시 + 5개 lag 중 골랐으므로 Bonferroni(×5) 보정 p
    res["abs"] = res["corr"].abs()
    best_idx = res.dropna(subset=["corr"]).groupby(["indicator_id", "target", "period"])["abs"].idxmax()
    res["is_best_lag"] = False
    res.loc[best_idx, "is_best_lag"] = True
    res["p_bonf_lag5"] = np.minimum(1.0, res["p_value"] * 5)
    res = res.drop(columns="abs")
    for c in ("corr", "p_value", "p_bonf_lag5"):
        res[c] = res[c].round(4)
    atomic_to_csv(res, OUT, index=False, encoding="utf-8-sig")
    best = res[res.is_best_lag].copy()
    best["absr"] = best["corr"].abs()
    pd.set_option("display.width", 250)
    for (tgt, per), g in best.groupby(["target", "period"]):
        print(f"\n=== {tgt} / {per}")
        print(g.sort_values("absr", ascending=False)[["indicator_id", "group", "lag_months", "corr", "n", "p_value", "p_bonf_lag5"]].to_string(index=False))
    print("\nsaved", OUT, len(res))
    # 타깃 기초정보
    print(tg.describe().round(2).to_string())


if __name__ == "__main__":
    main()
