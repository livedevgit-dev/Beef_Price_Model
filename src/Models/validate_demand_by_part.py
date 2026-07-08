"""
[파일 정의서]
- 파일명: src/Models/validate_demand_by_part.py
- 역할: 검증 (부위별 수요-채널 민감도 가설 검증 — 읽기 전용)
- 가설(사용자): 부위마다 수요 채널이 달라 지표 영향이 다르다.
    · 삼겹양지(우삼겹): 마트 제품 아님 → B2B·외식(마라탕·샤브) 중심 → '외식(음식점생산지수)'에 민감,
      '마트 판매'에는 둔감할 것.
    · 갈비·한우: 마트/가정소비·명절 수요 → '마트 판매·소비자물가'에 민감할 것.
- 방법: 타깃 부위별 익월 수익률 vs 각 수요지표(MoM, 발표시차 반영)의 Spearman IC 매트릭스.
- 타깃:
    · 수입 삼겹양지, 수입 LA갈비            (미트박스 B2B 도매)
    · 한우 갈비, 한우 등심, 한우 전체(도체)  (EKAPE 경락가 전국계)
- 출력: 콘솔 IC 매트릭스 + data/3_reports/ml/demand_by_part_ic.csv
- 주의: 월 표본 작음(~40). 부호·상대크기의 '경향' 참고용, 단정 금지.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DATA_REPORTS, DATA_PROCESSED, MACRO_RAW_CSV, DASHBOARD_READY_CSV,
                    HANWOO_DASHBOARD_CSV, KAMIS_PORK_RAW_CSV, ensure_dirs)

MIN_N = 24   # IC 계산 최소 표본

# 수요지표: (indicator_id, 표기명, 발표시차 개월)
DEMAND = [
    ("kr_retail_hypermarket", "대형마트", 2),
    ("kr_retail_dept", "백화점", 2),
    ("kr_retail_cvs", "편의점", 2),
    ("kr_service_food", "외식(음식점)", 2),
    ("kr_cpi_beef_imp", "수입쇠고기CPI", 1),
    ("kr_cpi_beef_dom", "국산쇠고기CPI", 1),
    ("kr_cpi_pork", "돼지고기CPI", 1),
]
PORK_LAG = 0


def _m(s):
    return pd.to_datetime(s, errors="coerce").dt.to_period("M").dt.to_timestamp()


def _monthly_ret(price_by_month: pd.Series) -> pd.Series:
    """월평균가 → 익월 수익률(t→t+1)."""
    idx = pd.period_range(price_by_month.index.min().to_period("M"),
                          price_by_month.index.max().to_period("M"), freq="M").to_timestamp()
    p = price_by_month.reindex(idx)
    return (p.shift(-1) / p - 1).rename("ret_next")


def build_targets() -> dict:
    tg = {}
    # 수입 삼겹양지 — 긴 시계열(통합 월간, 2016~) 사용 (대시보드 원본은 ~19개월로 짧음)
    try:
        sg = pd.read_csv(DATA_PROCESSED / "samgyup_unified_monthly.csv", parse_dates=["date"])
        s = sg.set_index("date")["price_won_per_kg"].sort_index()
        if len(s) >= MIN_N:
            tg["수입_삼겹양지"] = _monthly_ret(s)
    except Exception as e:
        print("  [skip] 삼겹양지:", e)

    # 한우 (EKAPE 경락) — '전체(도체)'는 전국계, 부위(갈비·등심·양지)는 시장 데이터 월평균
    hw = pd.read_csv(HANWOO_DASHBOARD_CSV, low_memory=False)
    hw["mm"] = _m(hw["date"])
    hw["price_won_per_kg"] = pd.to_numeric(hw["price_won_per_kg"], errors="coerce")
    nat_mask = hw["is_national_total"].astype(str).isin(["True", "1", "1.0"]) \
        if "is_national_total" in hw.columns else pd.Series(False, index=hw.index)

    for part, label, use_nat in [("전체(도체)", "한우_전체", True),
                                 ("갈비", "한우_갈비", False),
                                 ("등심", "한우_등심", False),
                                 ("양지", "한우_양지", False)]:
        sub = hw[(hw["part"] == part) & (nat_mask if use_nat else ~nat_mask)]
        s = sub.groupby("mm")["price_won_per_kg"].mean().dropna()
        if len(s) >= MIN_N:
            tg[label] = _monthly_ret(s)
    return tg


def build_demand() -> dict:
    """지표명 → MoM(발표시차 shift 적용) Series."""
    feats = {}
    m = pd.read_csv(MACRO_RAW_CSV)
    for ind, label, lag in DEMAND:
        s = m[m["indicator_id"] == ind].copy()
        if s.empty:
            continue
        s["mm"] = _m(s["date"])
        lvl = s.groupby("mm")["value"].mean()
        feats[label] = lvl.pct_change(fill_method=None).shift(lag)
    # 돼지 삼겹살 도매가 (일→월평균) MoM
    try:
        pk = pd.read_csv(KAMIS_PORK_RAW_CSV)
        pk = pk[(pk["product_cls_name"] == "도매") & (pk["item_name"] == "돼지") &
                (pk["kind_name"].astype(str).str.contains("삼겹", na=False))]
        pk["mm"] = _m(pk["reg_date"])
        lvl = pk.groupby("mm")["price"].mean()
        feats["돼지도매(삼겹)"] = lvl.pct_change(fill_method=None).shift(PORK_LAG)
    except Exception as e:
        print("  [skip] 돼지도매:", e)
    return feats


def ic(a: pd.Series, b: pd.Series):
    df = pd.concat([a, b], axis=1).dropna()
    if len(df) < MIN_N:
        return np.nan, len(df)
    return spearmanr(df.iloc[:, 0], df.iloc[:, 1])[0], len(df)


def main():
    ensure_dirs()
    targets = build_targets()
    demand = build_demand()
    if not targets or not demand:
        print("[오류] 타깃/수요지표 데이터 부족")
        return

    feat_names = list(demand.keys())
    mat = pd.DataFrame(index=feat_names, columns=list(targets.keys()), dtype=float)
    nmat = pd.DataFrame(index=feat_names, columns=list(targets.keys()), dtype=int)
    for tname, ret in targets.items():
        for fname, fser in demand.items():
            v, n = ic(fser, ret)
            mat.loc[fname, tname] = v
            nmat.loc[fname, tname] = n

    print("=" * 72)
    print("  부위별 수요-채널 민감도 — Spearman IC 매트릭스")
    print("  (지표 MoM, 발표시차 반영 → 각 부위 '익월 수익률'과의 상관)")
    print("=" * 72)
    # 표 출력
    colw = max(12, max(len(c) for c in mat.columns) + 1)
    header = "지표\\부위".ljust(16) + "".join(c.rjust(colw) for c in mat.columns)
    print(header)
    print("-" * len(header))
    for f in mat.index:
        row = f.ljust(16)
        for c in mat.columns:
            v = mat.loc[f, c]
            cell = "   -   " if pd.isna(v) else f"{v:+.3f}"
            mark = ""
            if not pd.isna(v):
                mark = "★" if abs(v) >= 0.2 else ("·" if abs(v) >= 0.1 else " ")
            row += (cell + mark).rjust(colw)
        print(row)
    print(f"\n표본 n(부위별): " + ", ".join(f"{c}={int(nmat[c].max())}" for c in nmat.columns))
    print("범례: ★ |IC|≥0.2 주목 · |IC|≥0.1 미약")

    # 가설 점검
    print("\n[가설 점검]")

    def _get(f, t):
        return mat.loc[f, t] if (f in mat.index and t in mat.columns) else np.nan

    # 삼겹양지: 외식 > 마트 ?
    sg_food = _get("외식(음식점)", "수입_삼겹양지")
    sg_mart = _get("대형마트", "수입_삼겹양지")
    if not pd.isna(sg_food) and not pd.isna(sg_mart):
        ok = abs(sg_food) > abs(sg_mart)
        print(f"  · 삼겹양지: 외식 IC {sg_food:+.3f} vs 마트 {sg_mart:+.3f} "
              f"→ {'가설 부합(외식>마트)' if ok else '가설 불충분(외식 우위 아님)'}")
    # 한우 갈비: 마트/국산CPI 가 외식보다 ?
    for t in ["한우_갈비", "한우_등심", "수입_LA갈비"]:
        mart = _get("대형마트", t); dept = _get("백화점", t)
        food = _get("외식(음식점)", t); dcpi = _get("국산쇠고기CPI", t)
        vals = {k: v for k, v in [("대형마트", mart), ("백화점", dept), ("국산쇠고기CPI", dcpi), ("외식", food)] if not pd.isna(v)}
        if vals:
            top = max(vals, key=lambda k: abs(vals[k]))
            print(f"  · {t}: 최강 채널 = {top} (IC {vals[top]:+.3f}) "
                  f"[마트 {mart:+.3f}/백화점 {dept:+.3f}/국산CPI {dcpi:+.3f}/외식 {food:+.3f}]"
                  .replace("nan", " - "))

    out = Path(str(DATA_REPORTS)) / "ml"
    out.mkdir(parents=True, exist_ok=True)
    mat.to_csv(out / "demand_by_part_ic.csv", encoding="utf-8-sig")
    print(f"\n[저장] {out/'demand_by_part_ic.csv'}")
    print("※ 월 표본이 작아 경향 참고용. 부호 안정성은 수개월 뒤 재검증 권장.")


if __name__ == "__main__":
    main()
