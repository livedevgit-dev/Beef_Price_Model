"""
[파일 정의서]
- 파일명: preprocess_hanwoo.py
- 역할: 가공 (Data Processing)
- 대상: 한우
- 데이터 소스:
    - data/0_raw/han_auction_raw.csv   (EKAPE 경락가격 + 도축장별 두수, long format)
    - data/0_raw/kamis_hanwoo_raw.csv  (KAMIS 한우 도/소매가, long format)
- 출력:
    - data/1_processed/han_auction_daily.csv  (EKAPE 일자×등급×시장 정규화)
    - data/2_dashboard/hanwoo_dashboard_ready.csv  (대시보드 통합 long format)
- 주요 기능:
    1. EKAPE long → 일자×등급×시장 표준화 (단위: 원/kg로 가정 — EKAPE는 도체 1kg 가격)
    2. KAMIS long → 부위·등급 텍스트 파싱(안심(1++등급) → 부위:안심, 등급:1++) + 단위 환산(100g → kg)
    3. 두 소스를 통합 long format으로 결합, 일자별 7/30일 이동평균 산출
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

# --------------------------------------------------------------------------
# 공통
# --------------------------------------------------------------------------
GRADE_CANONICAL_ORDER = ["1++", "1+", "1", "2", "3", "등외", "전체"]


def _to_canonical_grade(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return "전체"
    # EKAPE 응답의 gradeNm: "1++", "1+", "1", "2", "3", "등외", "QW"(전체)
    if s in {"1++", "1+", "1", "2", "3", "등외"}:
        return s
    if s in {"QW", "전체", "ALL", ""}:
        return "전체"
    return s


# --------------------------------------------------------------------------
# EKAPE 전처리
# --------------------------------------------------------------------------
def process_ekape() -> pd.DataFrame:
    """han_auction_raw.csv → 일자×등급×시장 long format. 단위는 원/kg."""
    path = Path(HAN_AUCTION_RAW_CSV)
    if not path.exists():
        print(f"[건너뜀] EKAPE 원본 없음: {path}")
        return pd.DataFrame()

    raw = pd.read_csv(path, low_memory=False)
    if raw.empty:
        return pd.DataFrame()

    # 경매 종료일을 대표 일자로 사용 (시작=종료가 보통이지만 chunk 호출 시 안전)
    raw["date"] = pd.to_datetime(
        raw["auction_end_ymd"].astype(str), format="%Y%m%d", errors="coerce"
    )
    raw = raw.dropna(subset=["date"])

    raw["grade"] = raw["grade_nm"].apply(_to_canonical_grade)
    raw["sex"] = raw["sex_nm"].fillna("전체").replace("", "전체")

    df = pd.DataFrame({
        "date": raw["date"],
        "source": "ekape_auction",
        "grade": raw["grade"],
        "sex": raw["sex"],
        "market_code": raw.get("market_code", ""),
        "market_name": raw.get("market_name", ""),
        "is_national_total": raw.get("is_national_total", False),
        "is_regional_total": raw.get("is_regional_total", False),
        "price_won_per_kg": pd.to_numeric(raw["price_won_per_kg"], errors="coerce"),
        "head_count": pd.to_numeric(raw["head_count"], errors="coerce"),
    })

    # 가격·두수 둘 다 결측이면 제거
    df = df[df["price_won_per_kg"].notna() | df["head_count"].notna()]

    HAN_AUCTION_DAILY_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(str(HAN_AUCTION_DAILY_CSV), index=False, encoding="utf-8-sig")
    print(f"[EKAPE] 정규화 완료: {len(df):,} rows → {HAN_AUCTION_DAILY_CSV}")
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
    """kamis_hanwoo_raw.csv → 일자×부위×등급×구분(도/소매) long format. 단위 원/kg."""
    path = Path(KAMIS_HANWOO_RAW_CSV)
    if not path.exists():
        print(f"[건너뜀] KAMIS 원본 없음(키 미설정 가능): {path}")
        return pd.DataFrame()

    raw = pd.read_csv(path, low_memory=False)
    if raw.empty:
        return pd.DataFrame()

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

    # product_cls_code 가 CSV에서 int(1/2)로 읽힐 수 있어 zfill(2)로 정규화 후 매핑
    _cls = raw["product_cls_code"].astype(str).str.strip().str.zfill(2)
    df = pd.DataFrame({
        "date": raw["date"],
        "source": _cls.map(
            {"02": "kamis_wholesale", "01": "kamis_retail"}
        ).fillna("kamis_unknown"),
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
    print(f"[KAMIS] 정규화 완료: {len(df):,} rows")
    return df


# --------------------------------------------------------------------------
# 통합 + 이동평균
# --------------------------------------------------------------------------
def build_dashboard_ready(
    ekape_df: pd.DataFrame, kamis_df: pd.DataFrame
) -> pd.DataFrame:
    """두 소스를 통합 long format으로 결합 + 7/30일 이동평균."""
    common_cols = [
        "date", "source", "grade", "sex", "market_code", "market_name",
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
        return pd.DataFrame(columns=union_cols + ["ma7", "ma30"])

    combined = pd.concat(
        [ekape_part[union_cols], kamis_part[union_cols] if not kamis_part.empty else None],
        ignore_index=True,
    )
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.sort_values(
        by=["source", "part", "grade", "market_name", "sex", "date"]
    )

    # 이동평균: (source, part, grade, market_name, sex) 그룹 단위
    grp_cols = ["source", "part", "grade", "market_name", "sex"]
    grouped = combined.groupby(grp_cols, dropna=False)
    combined["ma7"] = grouped["price_won_per_kg"].transform(
        lambda x: x.rolling(window=7, min_periods=3).mean()
    )
    combined["ma30"] = grouped["price_won_per_kg"].transform(
        lambda x: x.rolling(window=30, min_periods=10).mean()
    )

    return combined


def main() -> None:
    ensure_dirs()
    ekape_df = process_ekape()
    kamis_df = process_kamis()
    final_df = build_dashboard_ready(ekape_df, kamis_df)

    if final_df.empty:
        print("[안내] 통합 결과가 비어 있어 대시보드 파일을 생성하지 않았습니다.")
        return

    HANWOO_DASHBOARD_CSV.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(str(HANWOO_DASHBOARD_CSV), index=False, encoding="utf-8-sig")
    print(
        f"[완료] 대시보드 통합 데이터 저장: {len(final_df):,} rows → "
        f"{HANWOO_DASHBOARD_CSV}"
    )


if __name__ == "__main__":
    main()
