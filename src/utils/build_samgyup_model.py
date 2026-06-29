"""
[파일 정의서]
- 파일명: build_samgyup_model.py
- 역할: 분석 (삼겹양지 예측 피처 통합 + 예측 + 변수 영향력)
- 대상: 수입육 삼겹양지
- 데이터 소스: samgyup_unified_monthly + USDA Plate원가 + 환율 + 재고/수입(양지)
              + FAS 수출(중국/한국) + Cattle on Feed + macro
- 출력:
    - data/1_processed/samgyup_model_features.csv  (월별 통합 피처 — 집 PC xgboost 학습용)
    - data/2_dashboard/samgyup_forecast.csv        (계절+추세 예측 + 밴드, BI용)
    - data/2_dashboard/samgyup_feature_importance.csv (표준화 릿지 영향력, 해석용)
- 비고: 이 PC는 numpy2.x로 xgboost/sklearn 미동작 → 영향력은 numpy 릿지로 산출.
        무거운 ML(xgboost)은 집 PC에서 features CSV로 수행.
"""
import sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DATA_PROCESSED, DATA_DASHBOARD, USDA_PLATE_USD_KG_CSV,
                    MASTER_IMPORT_VOLUME_CSV, EXCHANGE_RATE_XLSX, BEEF_STOCK_XLSX,
                    MACRO_PROCESSED_CSV, FAS_EXPORT_SALES_CSV, US_CATTLE_ON_FEED_CSV,
                    ensure_dirs)

def _m(s): return pd.to_datetime(s, errors="coerce").dt.to_period("M").dt.to_timestamp()

def build_features() -> pd.DataFrame:
    tgt = pd.read_csv(DATA_PROCESSED/"samgyup_unified_monthly.csv", parse_dates=["date"]).set_index("date")["price_won_per_kg"].rename("samgyup")
    feat = pd.DataFrame(tgt)

    # USDA Short Plate 원가
    try:
        u = pd.read_csv(USDA_PLATE_USD_KG_CSV); u["m"]=_m(u["report_date"])
        pl = u[u["primal_desc"].astype(str).str.contains("Plate",case=False,na=False)]
        feat["usda_plate"] = (pl if not pl.empty else u).groupby("m")["choice_usd_per_kg"].mean()
    except Exception as e: print("  [skip] usda_plate:", e)
    # 환율
    try:
        ex = pd.read_excel(EXCHANGE_RATE_XLSX); ex["m"]=_m(ex["Date"])
        feat["fx"] = ex.groupby("m")["Close"].mean()
    except Exception as e: print("  [skip] fx:", e)
    # 수입/재고 양지
    try:
        imp = pd.read_csv(MASTER_IMPORT_VOLUME_CSV); imp["m"]=_m(imp["std_date"].astype(str)+"-01")
        feat["import_yj"] = imp.groupby("m")["부위별_양지_합계"].sum()
    except Exception as e: print("  [skip] import_yj:", e)
    try:
        stk = pd.read_excel(BEEF_STOCK_XLSX); stk["m"]=_m(stk["기준년월"].astype(str)+"-01")
        sj = stk[stk["부위별 부위별"].astype(str).str.contains("양지",na=False)]
        feat["stock_yj"] = sj.groupby("m")["조사재고량 조사재고량"].sum()
    except Exception as e: print("  [skip] stock_yj:", e)
    # FAS 중국/한국 수출
    try:
        f = pd.read_csv(FAS_EXPORT_SALES_CSV); f["m"]=_m(f["week_ending"]); f["v"]=pd.to_numeric(f["weekly_exports"],errors="coerce")
        pv = f.pivot_table(index="m", columns="country_name", values="v", aggfunc="sum")
        if "중국" in pv: feat["fas_china"]=pv["중국"]
        if "한국" in pv: feat["fas_korea"]=pv["한국"]
    except Exception as e: print("  [skip] fas:", e)
    # Cattle on Feed
    try:
        c = pd.read_csv(US_CATTLE_ON_FEED_CSV); c["m"]=_m(c["date"]); c["v"]=pd.to_numeric(c["value"],errors="coerce")
        for sd, col in [("INVENTORY","cof_inventory"),("PLACEMENTS","cof_placements")]:
            sub = c[c["short_desc"].str.contains(sd,na=False)]
            if not sub.empty: feat[col]=sub.groupby("m")["v"].mean()
    except Exception as e: print("  [skip] cof:", e)
    # macro 핵심
    try:
        mac = pd.read_csv(MACRO_PROCESSED_CSV, parse_dates=["date"]); mac["m"]=mac["date"].dt.to_period("M").dt.to_timestamp()
        for ind in ["us_soybean_meal","kr_ppi_food","kr_cpi_food","us_wti","kr_base_rate",
                    "kr_temp_avg","kr_precip"]:
            sub = mac[mac["indicator_id"]==ind].groupby("m")["value"].mean()
            if len(sub): feat[ind]=sub
    except Exception as e: print("  [skip] macro:", e)

    feat = feat.sort_index()
    feat = feat[feat.index >= "2019-01-01"]
    return feat

def ridge_importance(feat: pd.DataFrame) -> pd.DataFrame:
    df = feat.dropna(subset=["samgyup"]).copy()
    cols = [c for c in df.columns if c != "samgyup"]
    # 결측 많은 열 제외, 행 dropna
    use = [c for c in cols if df[c].notna().sum() >= 24]
    d = df[["samgyup"]+use].dropna()
    if len(d) < 15:
        return pd.DataFrame()
    X = d[use].values; y = d["samgyup"].values
    Xz = (X - X.mean(0))/X.std(0); yz=(y-y.mean())/y.std()
    lam = 1.0
    beta = np.linalg.solve(Xz.T@Xz + lam*np.eye(Xz.shape[1]), Xz.T@yz)
    pred = Xz@beta; r2 = 1-((yz-pred)**2).sum()/((yz-yz.mean())**2).sum()
    out = pd.DataFrame({"feature":use,"std_coef":beta.round(3)}).assign(abs_=lambda x:x["std_coef"].abs()).sort_values("abs_",ascending=False).drop(columns="abs_")
    out.attrs["r2"]=r2; out.attrs["n"]=len(d)
    return out

def forecast(feat: pd.DataFrame, horizon_end="2026-12") -> pd.DataFrame:
    s = feat["samgyup"].dropna()
    s = s[~s.index.duplicated()].asfreq("MS")
    s = s.interpolate(limit=2)
    # 계절지수: 12개월 중심이동평균 대비 비율의 월평균
    ma = s.rolling(12, center=True, min_periods=6).mean()
    ratio = (s/ma).dropna()
    seas = ratio.groupby(ratio.index.month).mean()
    seas = seas/seas.mean()
    # 레벨: 최근 3개월 평균
    level = s.dropna().iloc[-3:].mean()
    last = s.dropna().index.max()
    resid_std = (s/ma).std()*level if not np.isnan((s/ma).std()) else level*0.08
    fut = pd.date_range(last+pd.offsets.MonthBegin(1), pd.Timestamp(horizon_end), freq="MS")
    rows=[]
    for d in fut:
        base = level*seas.get(d.month,1.0)
        rows.append({"date":d.strftime("%Y-%m-%d"),"type":"forecast",
                     "base":round(base), "low":round(base-1.3*resid_std), "high":round(base+1.3*resid_std)})
    hist = [{"date":d.strftime("%Y-%m-%d"),"type":"actual","base":round(v),"low":None,"high":None}
            for d,v in s.dropna().items()]
    return pd.DataFrame(hist+rows)

def main():
    ensure_dirs()
    feat = build_features()
    feat.to_csv(DATA_PROCESSED/"samgyup_model_features.csv", encoding="utf-8-sig")
    print(f"[완료] 피처 테이블: samgyup_model_features.csv ({feat.shape[0]}개월 × {feat.shape[1]}열)")
    print("  포함 피처:", [c for c in feat.columns if c!='samgyup'])

    imp = ridge_importance(feat)
    if not imp.empty:
        imp.to_csv(DATA_DASHBOARD/"samgyup_feature_importance.csv", index=False, encoding="utf-8-sig")
        print(f"[완료] 영향력(릿지, R²={imp.attrs['r2']:.2f}, n={imp.attrs['n']}): samgyup_feature_importance.csv")
        print(imp.head(6).to_string(index=False))

    fc = forecast(feat)
    fc.to_csv(DATA_DASHBOARD/"samgyup_forecast.csv", index=False, encoding="utf-8-sig")
    f_only = fc[fc["type"]=="forecast"]
    print(f"[완료] 예측(계절+추세): samgyup_forecast.csv")
    print(f_only.to_string(index=False))

if __name__ == "__main__":
    main()
