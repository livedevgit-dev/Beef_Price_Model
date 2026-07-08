"""
[파일 정의서]
- 파일명: src/Models/validate_demand_features.py
- 역할: 검증 (신규 수요·공급 지표가 삼겹양지 익월 예측에 신호가 있는지 확인 — 읽기 전용)
- 배경: 소비시장 요인(대형마트·외식·품목CPI)과 돼지 도매가를 최근 추가.
        프로덕션 피처로 편입하기 전에 "유효성만" walk-forward로 검증한다.
- 방법:
    1) 타깃: 삼겹양지 월평균가 → 익월 수익률 ret[t] = price[t+1]/price[t]-1
       (의사결정 시점 = 월 t 말. 이 시점에 '알 수 있는' 값만 사용해 누수 방지)
    2) 발표시차(avail_lag) 반영: 일단위 파생(환율·USDA·돼지도매)=0개월,
       월간 발표(CPI·수입·재고)=1개월, 통계청 판매/서비스=2개월 지연으로 shift.
    3) 단변량 IC: Spearman corr(지표 MoM, 익월 수익률)
    4) walk-forward(확장창, 최소학습 36개월) OOS 비교:
       naive(무변동) vs 기존피처 Ridge vs 기존+신규 Ridge
       지표: 수익률 MAE, 방향 적중률, 예측-실측 Spearman
- 출력: 콘솔 + data/3_reports/ml/demand_feature_validation.csv
- 주의: 표본이 작다(월 ~60~80). 결과는 '편입 가치 판단용 참고'이며 단정 금지.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DATA_PROCESSED, DATA_REPORTS, MACRO_RAW_CSV, USDA_PLATE_USD_KG_CSV,
                    MASTER_IMPORT_VOLUME_CSV, EXCHANGE_RATE_XLSX, BEEF_STOCK_XLSX,
                    KAMIS_PORK_RAW_CSV, ensure_dirs)

MIN_TRAIN = 24   # 최소 학습 개월 (월간 표본이 작아 24로 설정)
RIDGE_ALPHA = 1.0
AUG_TOP_K = 3    # 증강 모델에 넣을 신규 피처 수 (단변량 IC 상위) — 과적합·표본손실 방지


def _m(s):
    return pd.to_datetime(s, errors="coerce").dt.to_period("M").dt.to_timestamp()


def _macro_series(m, ind):
    s = m[m["indicator_id"] == ind].copy()
    if s.empty:
        return None
    s["mm"] = _m(s["date"])
    return s.groupby("mm")["value"].mean()


def build_panel():
    # --- 타깃 ---
    tgt = pd.read_csv(DATA_PROCESSED / "samgyup_unified_monthly.csv", parse_dates=["date"])
    tgt = tgt.set_index("date")["price_won_per_kg"].rename("samgyup").sort_index()
    df = pd.DataFrame(index=tgt.index)
    df["samgyup"] = tgt

    raw = {}  # 원계열(레벨)

    # --- 기존(baseline) 피처 ---
    try:
        u = pd.read_csv(USDA_PLATE_USD_KG_CSV); u["mm"] = _m(u["report_date"])
        pl = u[u["primal_desc"].astype(str).str.contains("Plate", case=False, na=False)]
        raw["usda_plate"] = (pl if not pl.empty else u).groupby("mm")["choice_usd_per_kg"].mean()
    except Exception as e:
        print("  [skip] usda_plate:", e)
    try:
        ex = pd.read_excel(EXCHANGE_RATE_XLSX); ex["mm"] = _m(ex["Date"])
        raw["fx"] = ex.groupby("mm")["Close"].mean()
    except Exception as e:
        print("  [skip] fx:", e)
    try:
        imp = pd.read_csv(MASTER_IMPORT_VOLUME_CSV); imp["mm"] = _m(imp["std_date"].astype(str) + "-01")
        raw["import_yj"] = imp.groupby("mm")["부위별_양지_합계"].sum()
    except Exception as e:
        print("  [skip] import_yj:", e)
    try:
        stk = pd.read_excel(BEEF_STOCK_XLSX); stk["mm"] = _m(stk["기준년월"].astype(str) + "-01")
        sj = stk[stk["부위별 부위별"].astype(str).str.contains("양지", na=False)]
        raw["stock_yj"] = sj.groupby("mm")["조사재고량 조사재고량"].sum()
    except Exception as e:
        print("  [skip] stock_yj:", e)

    # --- 신규(candidate) 피처 ---
    m = pd.read_csv(MACRO_RAW_CSV)
    for ind, name in [
        ("kr_retail_hypermarket", "retail_hyper"),
        ("kr_retail_cvs", "retail_cvs"),
        ("kr_retail_dept", "retail_dept"),
        ("kr_service_food", "service_food"),
        ("kr_cpi_beef_imp", "cpi_beef_imp"),
        ("kr_cpi_beef_dom", "cpi_beef_dom"),
        ("kr_cpi_pork", "cpi_pork"),
    ]:
        s = _macro_series(m, ind)
        if s is not None:
            raw[name] = s
    # 돼지 삼겹살 도매가 (일→월평균)
    try:
        pk = pd.read_csv(KAMIS_PORK_RAW_CSV)
        pk = pk[(pk["product_cls_name"] == "도매") & (pk["item_name"] == "돼지") &
                (pk["kind_name"].astype(str).str.contains("삼겹", na=False))]
        pk["mm"] = _m(pk["reg_date"])
        raw["pork_whole"] = pk.groupby("mm")["price"].mean()
    except Exception as e:
        print("  [skip] pork_whole:", e)

    return df, raw


# 피처별 발표시차(개월) — 이 시점에 '알 수 있는' 값만 쓰기 위한 shift
AVAIL_LAG = {
    "usda_plate": 0, "fx": 0, "pork_whole": 0,      # 일단위 → 당월 말 확보
    "import_yj": 1, "stock_yj": 1,                  # 월간 발표(익월)
    "cpi_beef_imp": 1, "cpi_beef_dom": 1, "cpi_pork": 1,
    "retail_hyper": 2, "retail_cvs": 2, "retail_dept": 2, "service_food": 2,  # 통계청 시차 큼
}

BASELINE = ["usda_plate", "fx", "import_yj", "stock_yj"]
CANDIDATE = ["retail_hyper", "retail_cvs", "retail_dept", "service_food",
             "cpi_beef_imp", "cpi_beef_dom", "cpi_pork", "pork_whole"]


def assemble(df, raw):
    """월 격자에 정렬 + MoM 변화율 + 발표시차 shift + 익월수익률 타깃."""
    idx = pd.period_range(df.index.min().to_period("M"),
                          df.index.max().to_period("M"), freq="M").to_timestamp()
    out = pd.DataFrame(index=idx)
    out["samgyup"] = df["samgyup"].reindex(idx)
    # 익월 수익률 (t → t+1)
    out["ret_next"] = out["samgyup"].shift(-1) / out["samgyup"] - 1

    feats = []
    for name, s in raw.items():
        col = s.reindex(idx)
        mom = col.pct_change(fill_method=None)          # MoM 변화율(정상성)
        lag = AVAIL_LAG.get(name, 1)
        out[name] = mom.shift(lag)                       # 발표시차 반영
        feats.append(name)
    return out, feats


def univariate_ic(panel):
    rows = []
    for f in CANDIDATE + BASELINE:
        if f not in panel.columns:
            continue
        sub = panel[[f, "ret_next"]].dropna()
        if len(sub) < 24:
            rows.append((f, np.nan, len(sub)))
            continue
        ic, _ = spearmanr(sub[f], sub["ret_next"])
        rows.append((f, ic, len(sub)))
    return pd.DataFrame(rows, columns=["feature", "spearman_IC", "n"]).sort_values(
        "spearman_IC", key=lambda s: s.abs(), ascending=False)


def walk_forward(panel, feat_cols):
    sub = panel[["ret_next"] + feat_cols].dropna()
    X, y, idx = sub[feat_cols].values, sub["ret_next"].values, sub.index
    n = len(sub)
    preds, actual = [], []
    for i in range(MIN_TRAIN, n):
        Xtr, ytr, Xte = X[:i], y[:i], X[i:i + 1]
        sc = StandardScaler().fit(Xtr)
        model = Ridge(alpha=RIDGE_ALPHA).fit(sc.transform(Xtr), ytr)
        preds.append(float(model.predict(sc.transform(Xte))[0]))
        actual.append(y[i])
    if not preds:
        return None
    preds, actual = np.array(preds), np.array(actual)
    mae = np.mean(np.abs(preds - actual))
    hit = np.mean(np.sign(preds) == np.sign(actual))
    ic = spearmanr(preds, actual)[0] if len(preds) >= 5 else np.nan
    return {"n_oos": len(preds), "MAE": mae, "hit": hit, "IC": ic}


def naive_bench(panel, feat_cols):
    """예측=0(무변동) 벤치 — 동일 표본에서."""
    sub = panel[["ret_next"] + feat_cols].dropna()
    y = sub["ret_next"].values[MIN_TRAIN:]
    if len(y) == 0:
        return None
    mae = np.mean(np.abs(y))            # pred=0
    hit = np.mean(np.sign(0) == np.sign(y))  # 방향 무의미(0)
    return {"n_oos": len(y), "MAE": mae, "hit": hit, "IC": np.nan}


def main():
    ensure_dirs()
    df, raw = build_panel()
    panel, feats = assemble(df, raw)

    have_base = [f for f in BASELINE if f in panel.columns]
    have_cand = [f for f in CANDIDATE if f in panel.columns]

    print("=" * 64)
    print("  신규 수요·공급 지표 — 삼겹양지 익월 예측 유효성 검증")
    print("=" * 64)
    print(f"표본 월수: {panel['ret_next'].notna().sum()}  |  기존피처 {len(have_base)}종, 신규 {len(have_cand)}종")
    print(f"발표시차 반영(shift, 개월): " + ", ".join(f"{k}={AVAIL_LAG[k]}" for k in (have_base+have_cand)))

    # 1) 단변량 IC
    ic = univariate_ic(panel)
    print("\n[1] 단변량 예측력 (Spearman IC — |0.1|↑면 미약, |0.2|↑면 주목)")
    for _, r in ic.iterrows():
        flag = "" if pd.isna(r["spearman_IC"]) else ("  ★" if abs(r["spearman_IC"]) >= 0.2 else ("  ·" if abs(r["spearman_IC"]) >= 0.1 else ""))
        print(f"   {r['feature']:<14} IC={r['spearman_IC']:+.3f}  (n={int(r['n'])}){flag}")

    # 2) walk-forward 비교 — 증강모델엔 신규 IC 상위 K종만
    ic_cand = ic[ic["feature"].isin(have_cand)].dropna(subset=["spearman_IC"])
    top_cand = ic_cand.head(AUG_TOP_K)["feature"].tolist()
    print(f"\n   (증강모델 신규피처 = IC상위 {len(top_cand)}종: {', '.join(top_cand) if top_cand else '-'})")
    base_res = walk_forward(panel, have_base)
    aug_res = walk_forward(panel, have_base + top_cand)
    naive_res = naive_bench(panel, have_base + top_cand)

    print("\n[2] Walk-forward OOS 비교 (MAE 낮을수록·hit 높을수록·IC 높을수록 우수)")
    print(f"   {'모델':<22}{'n':>5}{'MAE(수익률)':>13}{'방향적중':>10}{'예측IC':>9}")
    def _line(name, r):
        if not r:
            print(f"   {name:<22}  (표본 부족)"); return
        icv = "  -" if pd.isna(r["IC"]) else f"{r['IC']:+.3f}"
        print(f"   {name:<22}{r['n_oos']:>5}{r['MAE']*100:>11.2f}%{r['hit']*100:>9.0f}%{icv:>9}")
    _line("naive(무변동)", naive_res)
    _line("기존피처", base_res)
    _line("기존+신규", aug_res)

    # 판정
    print("\n[해석]")
    if base_res and aug_res:
        d_mae = (aug_res["MAE"] - base_res["MAE"]) * 100
        d_hit = (aug_res["hit"] - base_res["hit"]) * 100
        verdict = ("신규 지표가 예측을 개선" if (d_mae < 0 and d_hit >= 0)
                   else "신규 지표의 개선효과 뚜렷하지 않음")
        print(f"   · 기존→기존+신규: MAE {d_mae:+.2f}%p, 방향적중 {d_hit:+.0f}%p → {verdict}")
    if aug_res and naive_res:
        print(f"   · 모델 vs naive: MAE {'우수' if aug_res['MAE']<naive_res['MAE'] else '열위'} "
              f"({aug_res['MAE']*100:.2f}% vs {naive_res['MAE']*100:.2f}%)")
    top = ic.dropna().head(3)["feature"].tolist()
    print(f"   · 단변량 IC 상위: {', '.join(top) if top else '-'}")
    print("   ※ 표본이 작아 참고용. 편입은 IC 안정성·다중공선성까지 보고 결정 권장.")

    # 저장
    out_dir = Path(str(DATA_REPORTS)) / "ml"
    out_dir.mkdir(parents=True, exist_ok=True)
    ic.to_csv(out_dir / "demand_feature_validation.csv", index=False, encoding="utf-8-sig")
    print(f"\n[저장] {out_dir/'demand_feature_validation.csv'}")


if __name__ == "__main__":
    main()
