"""
[파일 정의서]
- 파일명: preprocess_hanwoo.py
- 역할: 가공 (Data Processing)
- 대상: 한우
- 데이터 소스:
    - data/0_raw/han_auction_raw.csv   (EKAPE 경락가격 + 도축장별 두수, long format)
    - data/0_raw/kamis_hanwoo_raw.csv  (KAMIS 한우 부위별 소매가, long format)
- 출력:
    - data/1_processed/han_auction_daily.csv  (EKAPE 경매일×등급×시장 정규화 + 합산구간 period_days)
    - data/2_dashboard/hanwoo_dashboard_ready.csv  (대시보드 통합 long format)
- 주요 기능:
    1. EKAPE long → 경매일(auction_end_ymd)×등급×시장 표준화 (단위: 원/kg — EKAPE는 도체 1kg 가격)
       - period_days = 합산 구간 일수. 2026년~ 은 1(일별), 2019~2025는 30일 합산 행(date=구간 종료일)
       - 등급 표준화: 평균→전체, D→등외 (1++~3 + D = 평균 확인), A/B/C(육량등급)·등외제외·결함제외는 원문 유지
       - 권역/전국 플래그는 market_code 로 대소문자 무관 재계산 (CCenterAmt→'Center' 누락 교정)
    2. KAMIS long → 부위·등급 파싱 + 단위 환산(100g → kg). 소매(01)만 사용 —
       KAMIS 축산물 '도매(02)' 응답은 소매와 동일한 중복이라 kamis_wholesale 은 더 이상 만들지 않는다.
       is_outlier: 부위·등급별 ±7일 중앙값 대비 ±50% 넘게 튄 단일일 값 표시(삭제하지 않음)
    3. 두 소스를 통합 long format으로 결합, 일별 행(period_days==1)에 한해 시간 기준 7D/30D 이동평균 산출
       (행 개수 기준 rolling 은 30일 합산 행에서 7개월 평균이 되던 문제 교정. 합산 행의 ma7/ma30 은 공란)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    HAN_AUCTION_DAILY_CSV,
    HAN_AUCTION_RAW_CSV,
    HANWOO_DASHBOARD_CSV,
    KAMIS_HANWOO_RAW_CSV,
    ensure_dirs,
)
from utils.io_safe import atomic_to_csv

# --------------------------------------------------------------------------
# 공통
# --------------------------------------------------------------------------
GRADE_CANONICAL_ORDER = ["1++", "1+", "1", "2", "3", "등외", "전체"]

# EKAPE 시장 코드(소문자) → 한글명 / 권역·전국 구분 (crawl_han_auction_api.py 와 동일 기준)
EKAPE_REGIONAL_CODES = {"city", "east", "west", "center"}
EKAPE_NATIONAL_CODES = {"tot"}
EKAPE_REGION_NAMES = {
    "city": "수도권(권역)", "east": "영남권(권역)", "west": "호남권(권역)",
    "center": "중부권(권역)", "tot": "전국(전체)",
}

KAMIS_OUTLIER_WINDOW = "15D"      # 중심 ±7일
KAMIS_OUTLIER_THRESHOLD = 0.5     # 중앙값 대비 ±50%


def _to_canonical_grade(text: str) -> str:
    s = str(text or "").strip()
    if not s or s.lower() == "nan":
        return "전체"
    # EKAPE 응답의 gradeNm: "1++", "1+", "1", "2", "3", "D", "평균", A/B/C, "등외제외", "결함제외"
    if s in {"1++", "1+", "1", "2", "3", "등외"}:
        return s
    if s == "D":                       # 1++~3 + D = 평균 → D 가 사실상 등외
        return "등외"
    if s in {"QW", "전체", "ALL", "평균"}:
        return "전체"
    return s


# --------------------------------------------------------------------------
# EKAPE 전처리
# --------------------------------------------------------------------------
def process_ekape() -> pd.DataFrame:
    """han_auction_raw.csv → 경매일×등급×시장 long format. 단위는 원/kg."""
    path = Path(HAN_AUCTION_RAW_CSV)
    if not path.exists():
        print(f"[건너뜀] EKAPE 원본 없음: {path}")
        return pd.DataFrame()

    raw = pd.read_csv(path, dtype={"auction_start_ymd": str, "auction_end_ymd": str,
                                   "market_code": str, "grade_nm": str}, low_memory=False)
    if raw.empty:
        return pd.DataFrame()

    # 대표 일자 = 경매(합산 구간) 종료일. 시작일과의 차이로 합산 일수를 명시
    raw["date"] = pd.to_datetime(raw["auction_end_ymd"], format="%Y%m%d", errors="coerce")
    raw["start_date"] = pd.to_datetime(raw["auction_start_ymd"], format="%Y%m%d", errors="coerce")
    raw = raw.dropna(subset=["date"])
    raw["start_date"] = raw["start_date"].fillna(raw["date"])
    period_days = (raw["date"] - raw["start_date"]).dt.days + 1

    raw["grade"] = raw["grade_nm"].apply(_to_canonical_grade)
    raw["sex"] = raw["sex_nm"].fillna("전체").replace("", "전체")

    code_lc = raw["market_code"].fillna("").astype(str).str.strip().str.lower()
    market_name = code_lc.map(EKAPE_REGION_NAMES).fillna(raw["market_name"])

    df = pd.DataFrame({
        "date": raw["date"],
        "auction_start_date": raw["start_date"],
        "period_days": period_days,
        "source": "ekape_auction",
        "grade": raw["grade"],
        "sex": raw["sex"],
        "market_code": raw["market_code"],
        "market_name": market_name,
        "is_national_total": code_lc.isin(EKAPE_NATIONAL_CODES),
        "is_regional_total": code_lc.isin(EKAPE_REGIONAL_CODES),
        "price_won_per_kg": pd.to_numeric(raw["price_won_per_kg"], errors="coerce"),
        "head_count": pd.to_numeric(raw["head_count"], errors="coerce"),
    })

    # 가격·두수 둘 다 결측이면 제거
    df = df[df["price_won_per_kg"].notna() | df["head_count"].notna()]

    atomic_to_csv(df, HAN_AUCTION_DAILY_CSV, index=False, encoding="utf-8-sig")
    print(
        f"[EKAPE] 정규화 완료: {len(df):,} rows (일별 {int((df['period_days'] == 1).sum()):,} / "
        f"기간합산 {int((df['period_days'] > 1).sum()):,}) → {HAN_AUCTION_DAILY_CSV}"
    )
    return df


# --------------------------------------------------------------------------
# KAMIS 전처리
# --------------------------------------------------------------------------
def _parse_kamis_unit_to_kg_factor(unit: str) -> float | None:
    """KAMIS 단위 문자열을 원/kg 환산 계수로 변환.

    예) '100g' → 10 (가격 × 10 = 원/kg)
        '1kg'  → 1
        '600g' → 1000/600
        '500g' → 2
        '1마리' / '1두'  → None (kg 환산 불가)
    """
    s = str(unit or "").strip().lower().replace(" ", "")
    if not s:
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)(kg|g)$", s)
    if not m:
        return None
    qty = float(m.group(1))
    if m.group(2) == "kg":
        kg = qty
    else:
        kg = qty / 1000.0
    if kg <= 0:
        return None
    return 1.0 / kg


def process_kamis() -> pd.DataFrame:
    """kamis_hanwoo_raw.csv → 일자×부위×등급 소매가 long format. 단위 원/kg."""
    path = Path(KAMIS_HANWOO_RAW_CSV)
    if not path.exists():
        print(f"[건너뜀] KAMIS 원본 없음(키 미설정 가능): {path}")
        return pd.DataFrame()

    raw = pd.read_csv(path, dtype={"product_cls_code": str}, low_memory=False)
    if raw.empty:
        return pd.DataFrame()

    # 소매(01)만 사용. 02(도매)는 KAMIS 가 소매와 동일 응답을 준 중복분 → 제외 (collect_kamis_hanwoo.py 정의서 참고)
    _cls = raw["product_cls_code"].astype(str).str.strip().str.zfill(2)
    n_dup = int((_cls == "02").sum())
    if n_dup:
        print(f"[KAMIS] 도매(02) 중복 행 {n_dup:,}건 제외 (소매와 동일 응답)")
    raw = raw[_cls == "01"].copy()

    raw["date"] = pd.to_datetime(raw["reg_date"], errors="coerce")
    raw = raw.dropna(subset=["date"])

    # KAMIS 실제 응답: 부위는 kind_name(안심/등심/설도/양지), 등급은 별도 rank 필드("1++등급")
    raw["part"] = raw["kind_name"].astype(str).str.strip().replace("", "기타")
    if "rank" in raw.columns:
        raw["grade"] = (
            raw["rank"].astype(str)
            .str.replace("등급", "", regex=False)
            .str.strip()
            .apply(_to_canonical_grade)
        )
    else:
        # 구버전 raw(=rank 미수집)는 등급 정보 없음 → 전체로 처리
        raw["grade"] = "전체"

    raw["unit_factor"] = raw["unit"].apply(_parse_kamis_unit_to_kg_factor)
    raw["price_won_per_kg"] = pd.to_numeric(raw["price"], errors="coerce") * raw["unit_factor"]

    df = pd.DataFrame({
        "date": raw["date"],
        "period_days": 1,
        "source": "kamis_retail",
        "grade": raw["grade"],
        "sex": "전체",
        "part": raw["part"],
        "market_code": "",
        "market_name": raw["market_name"].fillna("").astype(str),
        "country_name": raw["country_name"].fillna("").astype(str),
        "is_national_total": False,
        "is_regional_total": False,
        "price_won_per_kg": raw["price_won_per_kg"],
        "head_count": pd.NA,
    })
    # 단위 변환 실패(예: '1마리') 또는 가격 결측 제외
    df = df[df["price_won_per_kg"].notna()]
    print(f"[KAMIS] 정규화 완료: {len(df):,} rows (소매)")
    return df


# --------------------------------------------------------------------------
# 통합 + 이동평균
# --------------------------------------------------------------------------
def _time_rolling(df: pd.DataFrame, grp_cols: list[str], window: str, min_periods: int,
                  stat: str = "mean", center: bool = False) -> pd.Series:
    """그룹별 날짜 기준(예: '7D') rolling. df 는 그룹·date 순 정렬 상태여야 한다."""
    out = pd.Series(float("nan"), index=df.index)
    for _, g in df.groupby(grp_cols, dropna=False, sort=False):
        s = g.set_index("date")["price_won_per_kg"].astype(float)
        r = s.rolling(window, min_periods=min_periods, center=center)
        out.loc[g.index] = (r.median() if stat == "median" else r.mean()).to_numpy()
    return out


def build_dashboard_ready(
    ekape_df: pd.DataFrame, kamis_df: pd.DataFrame
) -> pd.DataFrame:
    """두 소스를 통합 long format으로 결합 + 7/30일(시간 기준) 이동평균."""
    common_cols = [
        "date", "period_days", "source", "grade", "sex", "market_code", "market_name",
        "is_national_total", "is_regional_total",
        "price_won_per_kg", "head_count",
    ]

    ekape_part = ekape_df.copy() if not ekape_df.empty else pd.DataFrame(columns=common_cols)
    if not ekape_part.empty:
        ekape_part["part"] = "전체(도체)"  # EKAPE는 부위 미구분
        ekape_part["country_name"] = ""

    kamis_part = kamis_df.copy() if not kamis_df.empty else pd.DataFrame()

    union_cols = common_cols + ["part", "country_name"]
    for c in union_cols:
        if c not in ekape_part.columns:
            ekape_part[c] = pd.NA
        if not kamis_part.empty and c not in kamis_part.columns:
            kamis_part[c] = pd.NA

    if ekape_part.empty and kamis_part.empty:
        return pd.DataFrame(columns=union_cols + ["ma7", "ma30", "is_outlier"])

    combined = pd.concat(
        [ekape_part[union_cols], kamis_part[union_cols] if not kamis_part.empty else None],
        ignore_index=True,
    )
    combined["date"] = pd.to_datetime(combined["date"])
    combined["period_days"] = pd.to_numeric(combined["period_days"], errors="coerce").fillna(1).astype(int)
    combined = combined.sort_values(
        by=["source", "part", "grade", "market_name", "sex", "date"]
    ).reset_index(drop=True)

    # 이동평균: (source, part, grade, market_name, sex) 그룹 단위, 날짜 기준 창.
    # 기간합산 행(period_days>1)은 창 계산에서 제외 → 해당 행의 ma7/ma30 은 NaN
    grp_cols = ["source", "part", "grade", "market_name", "sex"]
    daily = combined[combined["period_days"] == 1]
    combined["ma7"] = _time_rolling(daily, grp_cols, "7D", min_periods=3)
    combined["ma30"] = _time_rolling(daily, grp_cols, "30D", min_periods=10)

    # KAMIS 단일일 급등락 표시 (데이터는 보존, 차트·분석에서 선택적으로 제외)
    combined["is_outlier"] = False
    kam = combined[combined["source"] == "kamis_retail"]
    if not kam.empty:
        med = _time_rolling(kam, grp_cols, KAMIS_OUTLIER_WINDOW, min_periods=5,
                            stat="median", center=True)
        dev = (kam["price_won_per_kg"] / med.loc[kam.index] - 1).abs()
        combined.loc[kam.index, "is_outlier"] = (dev > KAMIS_OUTLIER_THRESHOLD).fillna(False).to_numpy()
        print(f"[KAMIS] 이상치 표시(is_outlier): {int(combined['is_outlier'].sum()):,}건")

    return combined


def main() -> None:
    ensure_dirs()
    ekape_df = process_ekape()
    kamis_df = process_kamis()
    final_df = build_dashboard_ready(ekape_df, kamis_df)

    if final_df.empty:
        print("[안내] 통합 결과가 비어 있어 대시보드 파일을 생성하지 않았습니다.")
        return

    atomic_to_csv(final_df, HANWOO_DASHBOARD_CSV, index=False, encoding="utf-8-sig")
    print(
        f"[완료] 대시보드 통합 데이터 저장: {len(final_df):,} rows → "
        f"{HANWOO_DASHBOARD_CSV}"
    )


if __name__ == "__main__":
    main()
