# [파일 정의서]
# - 파일명: build_samgyup_series.py
# - 역할: 가공 (삼겹양지 가격 통합 시계열 생성)
# - 데이터 소스:
#     - data/2_dashboard/dashboard_ready_data.csv (미트박스 '삼겹양지', 2025~ 조밀)
#     - data/0_raw/삼겹양지 유통가격 추이 1.xlsx (도매상 실거래, 2016~ 희소)
# - 출력: data/1_processed/samgyup_unified_monthly.csv
#     컬럼: date(월초), price_won_per_kg, source(meatbox/dealer), n_obs
# - 정책: 2025년~ 미트박스 정본, 그 이전은 도매상으로 백필. 겹침 구간 검증결과
#         두 소스 레벨 차이 ~2.4%·상관 0.86 으로 직접 연결(보정 없음).
# - 의존성: pandas, numpy 만 사용 (sklearn/xgboost 불필요)

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, DATA_RAW, DATA_PROCESSED, ensure_dirs

DEALER_XLSX = DATA_RAW / "삼겹양지 유통가격 추이 1.xlsx"
OUT_CSV = DATA_PROCESSED / "samgyup_unified_monthly.csv"


def _meatbox_monthly() -> pd.DataFrame:
    if not DASHBOARD_READY_CSV.exists():
        return pd.DataFrame()
    mb = pd.read_csv(DASHBOARD_READY_CSV)
    mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
    s = mb[mb["part"] == "삼겹양지"].dropna(subset=["wholesale_price", "date"]).copy()
    if s.empty:
        return pd.DataFrame()
    s["month"] = s["date"].dt.to_period("M").dt.to_timestamp()
    g = s.groupby("month").agg(price_won_per_kg=("wholesale_price", "mean"),
                               n_obs=("wholesale_price", "size")).reset_index()
    g["source"] = "meatbox"
    return g.rename(columns={"month": "date"})


def _dealer_monthly() -> pd.DataFrame:
    if not DEALER_XLSX.exists():
        return pd.DataFrame()
    raw = pd.read_excel(DEALER_XLSX, sheet_name="삼겹양지", header=None)
    raw.columns = ["date_raw", "gubun", "price"] + [f"c{i}" for i in range(3, raw.shape[1])]
    raw["date"] = pd.to_datetime(raw["date_raw"], errors="coerce")
    raw["price_num"] = pd.to_numeric(raw["price"], errors="coerce")
    d = raw.dropna(subset=["date", "price_num"]).drop_duplicates(subset=["date", "price_num"])
    # 같은 날 여러 건 → 일평균 후 월집계
    d_daily = d.groupby(d["date"].dt.normalize())["price_num"].mean().reset_index()
    d_daily["month"] = d_daily["date"].dt.to_period("M").dt.to_timestamp()
    g = d_daily.groupby("month").agg(price_won_per_kg=("price_num", "mean"),
                                     n_obs=("price_num", "size")).reset_index()
    g["source"] = "dealer"
    return g.rename(columns={"month": "date"})


def main():
    ensure_dirs()
    mb = _meatbox_monthly()
    dl = _dealer_monthly()
    print(f"[미트박스] {len(mb)}개월  [도매상] {len(dl)}개월")

    # 월별 통합: 미트박스 있으면 정본, 없으면 도매상
    frames = []
    mb_months = set(mb["date"]) if not mb.empty else set()
    if not mb.empty:
        frames.append(mb)
    if not dl.empty:
        dl_only = dl[~dl["date"].isin(mb_months)]
        frames.append(dl_only)

    if not frames:
        print("[안내] 통합할 데이터가 없습니다.")
        return

    out = pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True)
    out = out[["date", "price_won_per_kg", "source", "n_obs"]]
    out["price_won_per_kg"] = out["price_won_per_kg"].round(0)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    print(f"[완료] {len(out)}개월 → {OUT_CSV}")
    print(f"  기간: {out['date'].min().date()} ~ {out['date'].max().date()}")
    print(f"  소스 구성: {out['source'].value_counts().to_dict()}")
    print(f"  최근 6개월:\n{out.tail(6).to_string(index=False)}")


if __name__ == "__main__":
    main()
