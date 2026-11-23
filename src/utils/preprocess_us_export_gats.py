"""
[파일 정의서]
- 파일명: preprocess_us_export_gats.py
- 역할: 가공 (월별 그룹 집계)
- 대상: 미국 → 한국 소고기 월간 수출 (HS10, 미국 통관 기준)
- 데이터 소스: data/0_raw/us_export_korea_gats.csv (collect_us_export_gats.py)
- 출력: data/1_processed/us_export_korea_monthly.csv (월 × 그룹, long format)
- 주요 기능:
    1. HS10 행을 월별 그룹으로 합산: 물량(kg)·금액(USD) 합계, 단가 = 금액합 / 물량합 (물량 가중 평균)
    2. 그룹 정의 — hs10 코드에서 직접 판정(저장된 chilled/bone_in 컬럼에 의존하지 않음; 변형 코드 0201306090 등 자동 포함):
         all_beef        : 0201* + 0202* 전체
         frozen_boneless : 0202 30* (0202306000 + 0202303550 …)   ← 삼겹양지(목초 냉동 정육) 축의 직접 원가
         frozen_bone_in  : 0202 10*/20* (0202206000 + 0202203550 … + 1990년대 지육 0202100010/0090)
         chilled_boneless: 0201 30* (0201306000/6090 + 0201303550 …)
         chilled_bone_in : 0201 10*/20* (0201206000 + 0201203550 … + 1990년대 지육 0201100010/0090)
    3. yoy_qty_pct: 같은 그룹의 전년 동월 물량 대비 증감률(%) — 전년 동월이 없거나 0 이면 결측
    4. 소고기 수출이 0건인 월(2004-01~2006-08 BSE 수입금지)은 원본에 행이 없으므로 산출에서도 빠진다(0 으로 채우지 않음)

산출 컬럼: date(YYYY-MM-01), group, qty_kg, value_usd, unit_value_usd_kg, yoy_qty_pct

사용법: python src/utils/preprocess_us_export_gats.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from config import DATA_PROCESSED, DATA_RAW, ensure_dirs  # noqa: E402
from utils.io_safe import atomic_to_csv  # noqa: E402

# config.py 에 상수가 추가되기 전에도 동작하도록 fallback
RAW_PATH = Path(getattr(config, "US_EXPORT_GATS_CSV", DATA_RAW / "us_export_korea_gats.csv"))
OUT_PATH = Path(getattr(config, "US_EXPORT_KOREA_MONTHLY_CSV", DATA_PROCESSED / "us_export_korea_monthly.csv"))

GROUP_ORDER = ["all_beef", "frozen_boneless", "frozen_bone_in", "chilled_boneless", "chilled_bone_in"]
OUTPUT_COLUMNS = ["date", "group", "qty_kg", "value_usd", "unit_value_usd_kg", "yoy_qty_pct"]


def _aggregate(df: pd.DataFrame, group: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "group", "qty_kg", "value_usd"])
    g = df.groupby("date", as_index=False).agg(qty_kg=("qty_kg", "sum"), value_usd=("value_usd", "sum"))
    g.insert(1, "group", group)
    return g


def preprocess_us_export_gats() -> int:
    ensure_dirs()
    if not RAW_PATH.exists():
        print(f"[건너뜀] 원본 파일이 없습니다: {RAW_PATH} (collect_us_export_gats.py 먼저 실행)")
        return 0
    try:
        raw = pd.read_csv(RAW_PATH, dtype={"hs10": str}, low_memory=False)
    except Exception as e:
        print(f"[중단] 원본 파일을 읽을 수 없습니다 ({type(e).__name__}): {RAW_PATH}")
        return 1
    if raw.empty:
        print("[안내] 원본 파일에 데이터가 없습니다.")
        return 0

    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    raw = raw.dropna(subset=["date"])
    raw["qty_kg"] = pd.to_numeric(raw["qty_kg"], errors="coerce").fillna(0.0)
    raw["value_usd"] = pd.to_numeric(raw["value_usd"], errors="coerce").fillna(0.0)
    hs = raw["hs10"].astype(str).str.zfill(10)
    raw = raw[hs.str.startswith(("0201", "0202"))].copy()
    hs = hs.loc[raw.index]
    chilled = hs.str.startswith("0201")
    bone_in = hs.str[4:6].isin(["10", "20"])   # 지육·골부 = True, 정육(30) = False

    parts = [
        _aggregate(raw, "all_beef"),
        _aggregate(raw[~chilled & ~bone_in], "frozen_boneless"),
        _aggregate(raw[~chilled & bone_in], "frozen_bone_in"),
        _aggregate(raw[chilled & ~bone_in], "chilled_boneless"),
        _aggregate(raw[chilled & bone_in], "chilled_bone_in"),
    ]
    out = pd.concat(parts, ignore_index=True)

    # 물량 가중 단가 (물량 0 이면 결측)
    out["unit_value_usd_kg"] = np.where(out["qty_kg"] > 0, out["value_usd"] / out["qty_kg"], np.nan)
    out["unit_value_usd_kg"] = out["unit_value_usd_kg"].round(4)

    # 전년 동월 물량 대비 증감률 (달력 기준 매칭 — 결측 월이 있어도 shift 착시 없음)
    prev = out[["date", "group", "qty_kg"]].copy()
    prev["date"] = prev["date"] + pd.DateOffset(years=1)
    prev = prev.rename(columns={"qty_kg": "_qty_prev"})
    out = out.merge(prev, on=["date", "group"], how="left")
    out["yoy_qty_pct"] = np.where(
        out["_qty_prev"] > 0, (out["qty_kg"] / out["_qty_prev"] - 1.0) * 100.0, np.nan
    )
    out["yoy_qty_pct"] = out["yoy_qty_pct"].round(2)
    out = out.drop(columns=["_qty_prev"])

    out["group"] = pd.Categorical(out["group"], categories=GROUP_ORDER, ordered=True)
    out = out.sort_values(["date", "group"]).reset_index(drop=True)
    out["group"] = out["group"].astype(str)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out[OUTPUT_COLUMNS]

    atomic_to_csv(out, OUT_PATH, index=False, encoding="utf-8-sig")
    n_months = out["date"].nunique()
    print(f"[완료] 월별 그룹 집계 {len(out)}행 ({n_months}개월, {out['date'].min()} ~ {out['date'].max()}) → {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(preprocess_us_export_gats())
