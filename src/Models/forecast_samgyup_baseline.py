# [파일 정의서]
# - 파일명: forecast_samgyup_baseline.py
# - 역할: 분석 (삼겹양지 단기·중기 가격 예측 — 베이스라인)
# - 데이터 소스: data/1_processed/samgyup_unified_monthly.csv
# - 출력: data/2_dashboard/samgyup_forecast.csv (월별 예측 + 신뢰구간)
# - 방법: numpy lstsq 회귀 (추세 + 연주기 계절성 2개 하모닉). sklearn/xgboost 불필요.
#         데이터가 월별·희소라 무거운 ML 대신 투명한 회귀를 baseline 으로 사용.
# - 한계: 과거 단일 도매상 소스·희소·레짐변화로 불확실성 큼. 점추정과 함께 ±구간 제시.

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED, DATA_DASHBOARD, ensure_dirs

SERIES_CSV = DATA_PROCESSED / "samgyup_unified_monthly.csv"
OUT_CSV = DATA_DASHBOARD / "samgyup_forecast.csv"
FIT_START = pd.Timestamp(2022, 1, 1)   # 현재 레짐(사료비 급등 이후) 중심으로 적합


def _design(dates: pd.Series, t0: pd.Timestamp) -> np.ndarray:
    t = ((dates.dt.year - t0.year) * 12 + (dates.dt.month - t0.month)).to_numpy(float)
    m = dates.dt.month.to_numpy(float)
    return np.column_stack([
        np.ones_like(t), t,
        np.sin(2 * np.pi * m / 12), np.cos(2 * np.pi * m / 12),
        np.sin(4 * np.pi * m / 12), np.cos(4 * np.pi * m / 12),
    ])


def main():
    ensure_dirs()
    if not SERIES_CSV.exists():
        print(f"[에러] 통합 시계열이 없습니다: {SERIES_CSV}\n  먼저 build_samgyup_series.py 를 실행하세요.")
        return

    df = pd.read_csv(SERIES_CSV, parse_dates=["date"]).sort_values("date")
    df = df.dropna(subset=["price_won_per_kg"])
    fit = df[df["date"] >= FIT_START].copy()
    if len(fit) < 12:
        print(f"[안내] 적합 구간 데이터가 {len(fit)}개월로 부족합니다. 전체 구간으로 대체합니다.")
        fit = df.copy()

    t0 = fit["date"].min()
    X = _design(fit["date"], t0)
    y = fit["price_won_per_kg"].to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    sigma = float(np.sqrt((resid ** 2).sum() / dof))

    last_actual = df.iloc[-1]
    print("=" * 60)
    print("  삼겹양지 가격 예측 (베이스라인: 추세+계절성 회귀)")
    print("=" * 60)
    print(f"적합 구간: {t0.date()} ~ {fit['date'].max().date()} ({len(fit)}개월)")
    print(f"최근 실측: {last_actual['date'].date()} = {last_actual['price_won_per_kg']:,.0f}원/kg "
          f"(source={last_actual['source']})")
    print(f"적합 잔차 표준편차(σ): {sigma:,.0f}원  → 신뢰구간 ±1.96σ\n")

    # 예측 대상: 2026-07 ~ 2026-12
    future = pd.date_range("2026-07-01", "2026-12-01", freq="MS")
    Xf = _design(pd.Series(future), t0)
    pred = Xf @ beta
    lo, hi = pred - 1.96 * sigma, pred + 1.96 * sigma

    out = pd.DataFrame({
        "date": future,
        "forecast_won_per_kg": pred.round(0),
        "lower_95": lo.round(0),
        "upper_95": hi.round(0),
    })

    print("[월별 예측] (원/kg)")
    disp = out.copy()
    disp["date"] = disp["date"].dt.strftime("%Y-%m")
    print(disp.to_string(index=False))

    jul = out.iloc[0]
    h2_avg = pred.mean()
    print(f"\n▶ 7월 단기 예측: {jul['forecast_won_per_kg']:,.0f}원/kg "
          f"(95% 구간 {jul['lower_95']:,.0f} ~ {jul['upper_95']:,.0f})")
    print(f"▶ 2026 하반기(7~12월) 평균 예측: {h2_avg:,.0f}원/kg")

    # 계절-나이브 교차검증(참고): 작년 동월 × 최근 레벨비
    df_idx = df.set_index("date")["price_won_per_kg"]
    recent3 = df_idx.tail(3).mean()
    ly_same3 = df_idx.reindex(df_idx.tail(3).index - pd.DateOffset(years=1)).mean()
    ratio = recent3 / ly_same3 if ly_same3 and not np.isnan(ly_same3) else np.nan
    if not np.isnan(ratio):
        naive = []
        for d in future:
            ly = df_idx.get(d - pd.DateOffset(years=1), np.nan)
            naive.append(ly * ratio if not np.isnan(ly) else np.nan)
        print(f"\n[교차검증] 계절-나이브(작년동월×최근레벨비 {ratio:.2f}): "
              f"7월 {naive[0]:,.0f} / 하반기평균 {np.nanmean(naive):,.0f}원/kg" if not np.isnan(naive[0])
              else "\n[교차검증] 작년 동월 데이터 부족으로 생략")

    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[저장] {OUT_CSV}")
    print("\n※ 주의: 과거가 단일 도매상·희소 소스라 불확실성이 큽니다. 점추정보다 구간으로 해석하세요.")


if __name__ == "__main__":
    main()
