"""
[파일 정의서]
- 파일명: src/utils/preprocess_kr_customs_beef.py
- 역할: 데이터 가공 (전처리)
- 대상: 관세청 국가별×HSK10 쇠고기 수입실적 원본 (data/0_raw/kr_customs_beef_import.csv, collect_kr_customs_beef.py 산출)
- 주요 기능:
    1. data/1_processed/kr_customs_beef_monthly.csv — 국가 × 부위군(group) 월별 수입 중량·금액·단가·전년동월비
       group: frozen_rib(0202201000) / frozen_bone_in_other(020220 중 갈비 외) / frozen_boneless(020230)
              chilled_rib(0201201000) / chilled_other(020120 중 갈비 외) / chilled_boneless(020130)
              frozen_all(0202*) / chilled_all(0201*) / all
       country 는 ISO2 + 전 국가 합계 'ALL'.  yoy_kg_pct = 전년 동월 대비 중량 증감률(%)
    2. data/1_processed/au_safeguard_usage.csv — 호주산(0201+0202 전 세번) 연내 누적 수입량 vs 한·호 FTA 농산물
       특별긴급관세(ASG) 발동 물량: date, year, month_kg, cum_kg, quota_kg, usage_pct, projected_trigger_month
       projected_trigger_month = 해당 월까지의 월평균 속도로 선형 외삽했을 때 발동 물량에 도달하는 월(연내 도달 못하면 빈값)
- 주의:
    * 관세청 통계는 '통관(수입신고 수리)' 기준. 세이프가드 소진율 집계(관세청 FTA 포털)도 통관 기준이지만 잠정치·정정 시차가 있어
      월별 합계가 공표 소진율과 수 % 차이 날 수 있다.
    * 수집 대상 HS6 는 020120/020130/020220/020230 — ASG 대상에 포함된 도체(020110/020210)는 수입량이 미미하여 제외됨.
    * 세번 분리 이력: 2008-12 까지 뼈있는 것은 0201200000/0202200000 단일 세번 → *_bone_in_other/chilled_other 에 귀속되고
      *_rib 은 0 이다. 갈비(…201000) 분리 시계열은 2009-01 부터만 유효하다 (frozen_all/chilled_all/all 은 전 기간 연속).
    * 관세청 월별 통계는 2026년 기준으로 ASG 공표 소진율보다 약 1~1.5개월 늦게 누적치가 도달한다
      (2026-07-21 발동 공표 vs 월별 통계 7월말 누적 86%, 9월에 100% 초과) — 선행 판단엔 관세청 FTA포털 주간 소진율 병행 필요.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED, DATA_RAW, ensure_dirs
from utils.io_safe import atomic_to_csv

# config.py 에 경로 상수가 정의되면 우선 사용
try:
    from config import KR_CUSTOMS_BEEF_CSV as RAW_FILE
except ImportError:
    RAW_FILE = DATA_RAW / "kr_customs_beef_import.csv"
try:
    from config import KR_CUSTOMS_BEEF_MONTHLY_CSV as MONTHLY_FILE
except ImportError:
    MONTHLY_FILE = DATA_PROCESSED / "kr_customs_beef_monthly.csv"
try:
    from config import AU_SAFEGUARD_USAGE_CSV as SAFEGUARD_FILE
except ImportError:
    SAFEGUARD_FILE = DATA_PROCESSED / "au_safeguard_usage.csv"

# --------------------------------------------------------------------------
# 한·호 FTA 쇠고기 ASG 발동 물량 (톤 → kg 로 변환해 사용)
# --------------------------------------------------------------------------
# ※ 값 검증 상태 (2026-11-23 조사):
#   - 2026: 196,050 t  [확인] MLA·Beef Central·관세청 FTA포털 보도 일치 (2026-07-21 100% 소진·발동)
#   - 2025: 192,206 t  [확인-명목] MLA 2024-12 "2025 trigger volume 192,206 t swt, minus 2024 excess tonnage"
#           → 2024년 초과 통관분을 차감한 실제 적용치는 약 190,340 t 으로 보고됨 [미확인] → 아래 QUOTA_EFFECTIVE_T 로 덮어씀
#   - 2022: 181,120 t  [확인] MLA 2021-12 보도 / 2019: 170,673 t [확인] MLA 2019-10 보도
#   - 그 외 연도: KAFTA 부속서 3-A 의 '매년 2% 복리 증가' 규칙으로 2019 값에서 전·후방 계산한 명목치 [미확인-산출값]
#     (2014 발효 첫해 ≈ 154,584 t 로 역산됨. 2007~2009 호주산 수입 평균 + 10% 가 기준이라는 보도와 대체로 부합)
#   - 2029년 ASG 종료 예정. 연도별 '초과분 차감' 등 실효 적용치는 관세청 FTA 포털 공고로 확인해야 함.
QUOTA_ANCHOR_YEAR, QUOTA_ANCHOR_T = 2019, 170_673.0
QUOTA_GROWTH = 1.02
QUOTA_FIRST_YEAR, QUOTA_LAST_YEAR = 2014, 2028
QUOTA_VERIFIED_T: dict[int, float] = {2019: 170_673, 2022: 181_120, 2026: 196_050}   # 공표치 확인
QUOTA_EFFECTIVE_T: dict[int, float] = {2025: 190_340}   # 초과분 차감 추정 적용치 [미확인]


def _quota_t(year: int) -> float:
    if year in QUOTA_EFFECTIVE_T:
        return QUOTA_EFFECTIVE_T[year]
    if year in QUOTA_VERIFIED_T:
        return QUOTA_VERIFIED_T[year]
    if year < QUOTA_FIRST_YEAR or year > QUOTA_LAST_YEAR:
        return float("nan")
    return round(QUOTA_ANCHOR_T * QUOTA_GROWTH ** (year - QUOTA_ANCHOR_YEAR))


def _quota_status(year: int) -> str:
    if year in QUOTA_EFFECTIVE_T:
        return "effective_unverified"
    if year in QUOTA_VERIFIED_T:
        return "verified"
    if QUOTA_FIRST_YEAR <= year <= QUOTA_LAST_YEAR:
        return "derived_2pct"
    return "none"


# 부위군 매핑 (HS 접두어 기반 — 과거 세번 변경에도 견고)
def _group_of(hs10: str) -> str:
    if not isinstance(hs10, str) or len(hs10) < 6:
        return "unknown"
    chilled = hs10.startswith("0201")
    prefix6 = hs10[:6]
    if prefix6 in ("020120", "020220"):
        if hs10 in ("0201201000", "0202201000"):
            return "chilled_rib" if chilled else "frozen_rib"
        return "chilled_other" if chilled else "frozen_bone_in_other"
    if prefix6 in ("020130", "020230"):
        return "chilled_boneless" if chilled else "frozen_boneless"
    return "unknown"


def _load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_FILE, dtype={"hs10": str, "country": str}, low_memory=False)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["imp_kg"] = pd.to_numeric(df["imp_kg"], errors="coerce").fillna(0)
    df["imp_usd"] = pd.to_numeric(df["imp_usd"], errors="coerce").fillna(0)
    return df


def build_monthly(df: pd.DataFrame) -> pd.DataFrame:
    base = df[["date", "country", "hs10", "imp_kg", "imp_usd"]].copy()
    base["group"] = base["hs10"].map(_group_of)
    base = base[base["group"] != "unknown"]

    # 세부 group + 상위 집계(frozen_all / chilled_all / all) 를 행으로 추가
    parts = [base]
    agg_frozen = base[base["hs10"].str.startswith("0202")].assign(group="frozen_all")
    agg_chilled = base[base["hs10"].str.startswith("0201")].assign(group="chilled_all")
    parts += [agg_frozen, agg_chilled, base.assign(group="all")]
    stacked = pd.concat(parts, ignore_index=True)

    # 전 국가 합계 'ALL'
    stacked = pd.concat([stacked, stacked.assign(country="ALL")], ignore_index=True)

    monthly = (stacked.groupby(["date", "country", "group"], as_index=False)[["imp_kg", "imp_usd"]].sum())
    kg = monthly["imp_kg"].where(monthly["imp_kg"] > 0)
    monthly["unit_value_usd_kg"] = (monthly["imp_usd"] / kg).round(4)

    # 전년 동월비 (같은 country·group 의 12개월 전 값)
    prev = monthly[["date", "country", "group", "imp_kg"]].copy()
    prev["date"] = prev["date"] + pd.DateOffset(years=1)
    prev = prev.rename(columns={"imp_kg": "_kg_prev"})
    monthly = monthly.merge(prev, on=["date", "country", "group"], how="left")
    prev_kg = monthly["_kg_prev"].where(monthly["_kg_prev"] > 0)
    monthly["yoy_kg_pct"] = ((monthly["imp_kg"] / prev_kg - 1) * 100).round(2)
    monthly = monthly.drop(columns=["_kg_prev"])

    monthly["date"] = monthly["date"].dt.strftime("%Y-%m-%d")
    monthly["imp_kg"] = monthly["imp_kg"].round(0).astype("int64")
    monthly["imp_usd"] = monthly["imp_usd"].round(0).astype("int64")
    return monthly.sort_values(["date", "country", "group"]).reset_index(drop=True)


def build_au_safeguard(df: pd.DataFrame) -> pd.DataFrame:
    au = df[df["country"] == "AU"].groupby("date", as_index=False)["imp_kg"].sum().sort_values("date")
    if au.empty:
        return pd.DataFrame(columns=["date", "year", "month_kg", "cum_kg", "quota_kg", "usage_pct",
                                     "projected_trigger_month", "quota_status"])
    au = au.rename(columns={"imp_kg": "month_kg"})
    au["year"] = au["date"].dt.year
    au["month"] = au["date"].dt.month
    au["cum_kg"] = au.groupby("year")["month_kg"].cumsum()
    au["quota_kg"] = au["year"].map(lambda y: _quota_t(y) * 1000)
    au["quota_status"] = au["year"].map(_quota_status)
    au["usage_pct"] = (au["cum_kg"] / au["quota_kg"] * 100).round(2)

    # 선형 외삽: 해당 월까지 월평균 속도로 연내 발동 물량 도달 월 추정
    def _proj(row) -> str:
        if not np.isfinite(row["quota_kg"]) or row["cum_kg"] <= 0:
            return ""
        pace = row["cum_kg"] / row["month"]
        months_needed = row["quota_kg"] / pace
        m = math.ceil(months_needed - 1e-9)
        if m > 12:
            return ""
        return f"{int(row['year'])}-{max(m, 1):02d}"
    au["projected_trigger_month"] = au.apply(_proj, axis=1)

    au["date"] = au["date"].dt.strftime("%Y-%m-%d")
    out = au[["date", "year", "month_kg", "cum_kg", "quota_kg", "usage_pct", "projected_trigger_month", "quota_status"]]
    out["month_kg"] = out["month_kg"].round(0).astype("int64")
    out["cum_kg"] = out["cum_kg"].round(0).astype("int64")
    return out.reset_index(drop=True)


def preprocess_kr_customs_beef() -> int:
    print("=" * 60)
    print("[시작] 관세청 쇠고기 수입실적 전처리 (국가×부위군 월별 / 호주산 ASG 소진율)")
    print("=" * 60)
    ensure_dirs()
    if not Path(RAW_FILE).exists():
        print(f"[건너뜀] 원본 파일이 없습니다: {RAW_FILE} — 수집(collect_kr_customs_beef.py)부터 진행하세요.")
        return 0
    try:
        df = _load_raw()
    except Exception as e:
        print(f"[에러] 원본 파일을 읽을 수 없습니다 ({type(e).__name__}: {e})")
        return 1
    if df.empty:
        print("[에러] 원본에 유효한 행이 없습니다.")
        return 1

    monthly = build_monthly(df)
    atomic_to_csv(monthly, MONTHLY_FILE, index=False, encoding="utf-8-sig")
    print(f"[완료] 월별 국가×부위군: {len(monthly)}행 ({monthly['date'].min()} ~ {monthly['date'].max()}) → {MONTHLY_FILE}")

    sg = build_au_safeguard(df)
    atomic_to_csv(sg, SAFEGUARD_FILE, index=False, encoding="utf-8-sig")
    if not sg.empty:
        last = sg.iloc[-1]
        print(f"[완료] 호주산 ASG 소진율: {len(sg)}행 — 최근 {last['date']} 누적 {last['cum_kg']/1e6:,.1f}kt "
              f"/ 물량 {last['quota_kg']/1e6:,.1f}kt = {last['usage_pct']}% "
              f"(도달 예상월 {last['projected_trigger_month'] or '연내 미도달'}, 물량 근거 {last['quota_status']}) → {SAFEGUARD_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(preprocess_kr_customs_beef())
