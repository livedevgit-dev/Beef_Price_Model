"""
[파일 정의서]
- 파일명: build_samgyup_model.py
- 역할: 분석 (삼겹양지 예측 피처 통합 + 예측 + 변수 영향력)
- 대상: 수입육 삼겹양지
- 데이터 소스: samgyup_unified_monthly + USDA Plate원가 + 환율 + 재고/수입(양지)
              + FAS 수출(중국/한국) + Cattle on Feed + macro(raw, 발표값 그대로)
- 출력:
    - data/1_processed/samgyup_model_features.csv  (월별 통합 피처 — train_samgyup_xgb.py 입력)
    - data/2_dashboard/samgyup_forecast.csv        (계절+추세 예측 + 밴드, BI용) 컬럼: date,type,base,low,high
    - data/2_dashboard/samgyup_feature_importance.csv (표준화 릿지 영향력, 해석용) 컬럼: feature,std_coef
- 피처 시점 규칙 (룩어헤드 방지):
    · 피처 행 t 의 값 = 월 t 말에 '실제로 알 수 있는' 값 = 원계열의 (t − AVAIL_LAG) 월 값.
      (예: 2026-10 행의 stock_yj = 2026-08 재고. 10월 말 현재 KMTA 재고 최신이 8월이므로)
    · 발표 전 월을 앞 값으로 채우지(ffill) 않는다. macro 는 일별 ffill 된 processed 대신 raw 를 사용.
    · 시차 근거는 AVAIL_LAG 주석 참고. 실행 시 '관측 시차'(오늘 기준 최신 월)를 출력해 가정과 비교한다.
- 재고 구조 단절: KMTA 재고는 2023-05 에 합계 279천→162천톤으로 단절(조사 표본 변경 추정, 2023-04 는 원본 오류로 결측).
  → stock_yj 는 2023-05 이후 원계열만 사용(그 이전은 NaN). 단절 전후 레벨을 한 회귀에 섞으면 가짜 상관이 생김.
- FAS 주간 수출은 월 '주 평균' (주 합계는 4주/5주 달에 따라 ±25% 왜곡).
- 비고: 영향력은 numpy 릿지(설명용). xgboost 학습은 src/Models/train_samgyup_xgb.py.
"""
import sys, warnings
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DATA_PROCESSED, DATA_DASHBOARD, USDA_PLATE_USD_KG_CSV,
                    MASTER_IMPORT_VOLUME_CSV, EXCHANGE_RATE_XLSX, BEEF_STOCK_XLSX,
                    MACRO_RAW_CSV, FAS_EXPORT_SALES_CSV, US_CATTLE_ON_FEED_CSV,
                    ensure_dirs)
from utils.io_safe import atomic_to_csv

# 피처별 발표시차(개월): 월 t 말 시점에 원계열의 몇 개월 전 값까지 공개돼 있는가
# (2026-10-30 기준 각 원천의 최신 월로 확인 — 실행 시 '관측 시차'로 재확인)
AVAIL_LAG = {
    "usda_plate": 0,      # USDA 일간 리포트(최신 = 전일) → 당월 평균을 월말에 확보
    "fx": 0,              # 환율 일간
    "us_wti": 0,          # FRED 일간 (2~3 영업일 지연)
    "kr_temp_avg": 0,     # 기상청 일간
    "kr_precip": 0,
    "fas_china": 0,       # FAS 주간(목요일 발표, ~1주 지연) → 당월 확보된 주들의 평균
    "fas_korea": 0,
    "cof_inventory": 0,   # Cattle on Feed '당월 1일 재고' — 당월 셋째~넷째 금요일 발표
    "cof_placements": 1,  # 전월 입식두수 — 당월 리포트에 발표
    "import_yj": 1,       # KMTA 수입실적(식약처 잠정 포함) — 익월 중순 게시 (10월 말 최신 = 9월)
    "stock_yj": 2,        # KMTA 재고 — 2개월 지연 게시 (10월 말 최신 = 8월)
    "us_soybean_meal": 1, # FRED/IMF 월간 — 익월 초 발표
    "kr_cpi_food": 1,     # 통계청 CPI — 익월 초 발표
    "kr_ppi_food": 1,     # 한국은행 PPI — 익월 ~20일 발표
    "kr_base_rate": 1,    # ECOS 월간 계열 — 익월 갱신 (10월 말 최신 = 9월)
}
STOCK_REGIME_START = "2023-05-01"   # KMTA 재고 조사 기준 단절 이후만 사용
MACRO_IDS = ["us_soybean_meal", "kr_ppi_food", "kr_cpi_food", "us_wti", "kr_base_rate",
             "kr_temp_avg", "kr_precip"]


def _m(s): return pd.to_datetime(s, errors="coerce").dt.to_period("M").dt.to_timestamp()


def load_raw() -> dict:
    """원계열(월, 발표 기준월 인덱스, 시차 적용 전) 딕셔너리"""
    raw = {}
    # USDA Short Plate 원가
    try:
        u = pd.read_csv(USDA_PLATE_USD_KG_CSV); u["m"] = _m(u["report_date"])
        pl = u[u["primal_desc"].astype(str).str.contains("Plate", case=False, na=False)]
        raw["usda_plate"] = (pl if not pl.empty else u).groupby("m")["choice_usd_per_kg"].mean()
    except Exception as e: print("  [skip] usda_plate:", e)
    # 환율
    try:
        ex = pd.read_excel(EXCHANGE_RATE_XLSX); ex["m"] = _m(ex["Date"])
        raw["fx"] = pd.to_numeric(ex["Close"], errors="coerce").groupby(ex["m"]).mean()
    except Exception as e: print("  [skip] fx:", e)
    # 수입 양지 (미국+호주 냉동). 결측(NaN)은 합계에서 0 으로 숨기지 않음
    try:
        imp = pd.read_csv(MASTER_IMPORT_VOLUME_CSV); imp["m"] = _m(imp["std_date"].astype(str) + "-01")
        raw["import_yj"] = imp.groupby("m")["부위별_양지_합계"].sum(min_count=1)
    except Exception as e: print("  [skip] import_yj:", e)
    # 재고 양지 — 단절 이후만, 결측 처리된 월(2023-04)은 NaN 유지
    try:
        stk = pd.read_excel(BEEF_STOCK_XLSX); stk["m"] = _m(stk["기준년월"].astype(str) + "-01")
        sj = stk[stk["부위별 부위별"].astype(str).str.contains("양지", na=False)]
        s = pd.to_numeric(sj["조사재고량 조사재고량"], errors="coerce").groupby(sj["m"]).sum(min_count=1)
        raw["stock_yj"] = s[s.index >= STOCK_REGIME_START]
    except Exception as e: print("  [skip] stock_yj:", e)
    # FAS 중국/한국 수출 — 월 주평균
    try:
        f = pd.read_csv(FAS_EXPORT_SALES_CSV); f["m"] = _m(f["week_ending"])
        f["v"] = pd.to_numeric(f["weekly_exports"], errors="coerce")
        pv = f.pivot_table(index="m", columns="country_name", values="v", aggfunc="mean")
        if "중국" in pv: raw["fas_china"] = pv["중국"]
        if "한국" in pv: raw["fas_korea"] = pv["한국"]
    except Exception as e: print("  [skip] fas:", e)
    # Cattle on Feed
    try:
        c = pd.read_csv(US_CATTLE_ON_FEED_CSV); c["m"] = _m(c["date"]); c["v"] = pd.to_numeric(c["value"], errors="coerce")
        for sd, col in [("INVENTORY", "cof_inventory"), ("PLACEMENTS", "cof_placements")]:
            sub = c[c["short_desc"].str.contains(sd, na=False)]
            if not sub.empty: raw[col] = sub.groupby("m")["v"].mean()
    except Exception as e: print("  [skip] cof:", e)
    # macro — raw(발표값). processed 는 일별 ffill 이라 미발표 월이 직전 값으로 채워져 있음
    try:
        mac = pd.read_csv(MACRO_RAW_CSV); mac["m"] = _m(mac["date"])
        mac["value"] = pd.to_numeric(mac["value"], errors="coerce")
        for ind in MACRO_IDS:
            sub = mac[mac["indicator_id"] == ind].groupby("m")["value"].mean()
            if len(sub): raw[ind] = sub
    except Exception as e: print("  [skip] macro:", e)
    return {k: v.dropna().sort_index() for k, v in raw.items() if v is not None}


def report_lags(raw: dict):
    """오늘 기준 원천별 최신 월 → 관측 시차 vs 가정(AVAIL_LAG) 비교 출력"""
    cur = pd.Timestamp(datetime.now().date()).to_period("M")
    print("  [발표시차] 피처: 가정 lag / 관측(오늘 기준 최신 월)")
    for k, s in raw.items():
        obs = (cur - s.index.max().to_period("M")).n
        lag = AVAIL_LAG.get(k, 1)
        flag = "" if obs <= lag else "  ← 가정보다 늦음: 최신 행은 NaN"
        print(f"    {k:16s} lag {lag} / 관측 {obs} (최신 {s.index.max():%Y-%m}){flag}")


def build_features() -> pd.DataFrame:
    tgt = pd.read_csv(DATA_PROCESSED/"samgyup_unified_monthly.csv", parse_dates=["date"]).set_index("date")["price_won_per_kg"].rename("samgyup")
    tgt = tgt[~tgt.index.duplicated()].sort_index()
    feat = pd.DataFrame(tgt)

    raw = load_raw()
    report_lags(raw)
    # 연속 월 격자에서 시차만큼 뒤로 민 다음 타깃 월에 맞춤 (ffill 없음)
    start = min([tgt.index.min()] + [s.index.min() for s in raw.values()])
    grid = pd.date_range(start, tgt.index.max(), freq="MS")
    for k, s in raw.items():
        feat[k] = s.reindex(grid).shift(AVAIL_LAG.get(k, 1)).reindex(feat.index)

    feat = feat.sort_index()
    feat = feat[feat.index >= "2019-01-01"]
    feat.index.name = "date"
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
    sd = X.std(0); keep = sd > 0                      # 상수열(예: 기준금리 동결 구간) 제외
    use = [u for u, k in zip(use, keep) if k]; X = X[:, keep]
    Xz = (X - X.mean(0))/X.std(0); yz=(y-y.mean())/y.std()
    lam = 1.0
    beta = np.linalg.solve(Xz.T@Xz + lam*np.eye(Xz.shape[1]), Xz.T@yz)
    pred = Xz@beta; r2 = 1-((yz-pred)**2).sum()/((yz-yz.mean())**2).sum()
    out = pd.DataFrame({"feature":use,"std_coef":beta.round(3)}).assign(abs_=lambda x:x["std_coef"].abs()).sort_values("abs_",ascending=False).drop(columns="abs_")
    out.attrs["r2"]=r2; out.attrs["n"]=len(d); out.attrs["period"]=f"{d.index.min():%Y-%m}~{d.index.max():%Y-%m}"
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
    atomic_to_csv(feat, DATA_PROCESSED/"samgyup_model_features.csv", encoding="utf-8-sig")
    print(f"[완료] 피처 테이블: samgyup_model_features.csv ({feat.shape[0]}개월 × {feat.shape[1]}열, 발표시차 반영)")
    print("  포함 피처:", [c for c in feat.columns if c!='samgyup'])
    last = feat.iloc[-1]
    miss = [c for c in feat.columns if c != "samgyup" and pd.isna(last[c])]
    print(f"  최신 행 {feat.index[-1]:%Y-%m}: 결측 피처 {miss or '없음'}")

    imp = ridge_importance(feat)
    if not imp.empty:
        atomic_to_csv(imp, DATA_DASHBOARD/"samgyup_feature_importance.csv", index=False, encoding="utf-8-sig")
        print(f"[완료] 영향력(릿지, R²={imp.attrs['r2']:.2f}, n={imp.attrs['n']}, {imp.attrs['period']}): samgyup_feature_importance.csv")
        print(imp.head(6).to_string(index=False))

    fc = forecast(feat)
    atomic_to_csv(fc, DATA_DASHBOARD/"samgyup_forecast.csv", index=False, encoding="utf-8-sig")
    f_only = fc[fc["type"]=="forecast"]
    print(f"[완료] 예측(계절+추세): samgyup_forecast.csv")
    print(f_only.to_string(index=False))

if __name__ == "__main__":
    main()
