"""
[파일 정의서]
- 파일명: preprocess_macro.py
- 역할: 가공 (Data Processing)
- 대상: 거시경제 지표 (Macro — 금리·CPI·PPI·옥수수·WTI)
- 데이터 소스: data/0_raw/macro_indicators_raw.csv (FRED + ECOS long format)
- 수집/가공 주기: 일단위
- 주요 기능:
    1. raw(long) 로드 → indicator_id 별로 2019-01-01 ~ 최신일 일별 인덱스 생성
    2. 월별 지표(freq=M)는 일별로 forward-fill (as-of 값, ML lag 용). 금리·물가는 다음 발표 전까지 값이
       유지되는 것이 정상이므로 ffill 에 limit 을 두지 않음 (가격 ffill 과 다른 정책)
       일별 지표(freq=D)는 짧은 결측만 채운다: WTI 는 주말·휴장 대비 4일, 기상(KMA)은 2일까지만 ffill,
       기상은 마지막 관측일 이후로 연장하지 않는다. 채우지 못한 날은 행을 만들지 않는다.
       주별 지표(freq=W, 예: 미국 경유 GASDESW 월요일 관측)는 다음 관측 전까지 7일 한도로 ffill (2026-10 추가).
       호주 생우(MLA)는 거래일(월~목·금)만 저장되므로 일별 기본 한도(4일)로 주말·공휴일을 채운다.
    3. value, ma30, yoy_pct, mom_pct 산출 — 원 주기 기준 (2026-10 정합성 수정)
       - 월별 지표: 월 시계열에서 전월(mom)·전년동월(yoy) 대비를 계산한 뒤 일별로 펼침
         (예전 일별 shift(30)/shift(365) 는 31일에 mom=0, 3월 1일에 2개월 변화가 되는 오류가 있었음)
       - 일별 지표: 달력 기준 1개월/1년 전 값(±7일 이내 직전 관측, asof)과 비교
       - 분모가 0 이면 inf 대신 결측(NaN). 기상(KMA 기온·강수량)은 % 변화가 무의미해 yoy/mom 을 비워 둠
         (예전엔 강수량 yoy inf 582행·mom inf 660행 발생)
    4. 산출물:
       - data/1_processed/macro_indicators_daily.csv  (long + ma30/yoy/mom)
       - data/2_dashboard/macro_dashboard_ready.csv    (wide: date × indicator, 가격 데이터와 merge용)

날짜 정책: raw 의 월별 date 는 YYYY-MM-01 로 통일되어 있으며, 전처리에서 일별로 확장한다.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    MACRO_RAW_CSV,
    MACRO_PROCESSED_CSV,
    MACRO_DASHBOARD_CSV,
    ensure_dirs,
)
from utils.io_safe import atomic_to_csv

HISTORY_START = pd.Timestamp(2019, 1, 1)

# 일별 지표 ffill 한도 (일). 기상은 짧은 결측만, 시장가격(WTI)은 주말·연휴까지.
DAILY_FFILL_LIMIT = {"KMA": 2}
DAILY_FFILL_LIMIT_DEFAULT = 4
# 원 주기별 ffill 한도 (소스별 한도가 없을 때 적용) — 주별 지표는 다음 관측일 직전까지
FREQ_FFILL_LIMIT = {"W": 7}
# 일별 지표 yoy/mom 비교 시 1년/1개월 전 날짜에 관측이 없으면 직전 관측을 쓰되 허용 간격
ASOF_TOLERANCE = pd.Timedelta(days=7)
# 변화율(yoy/mom %)을 산출하지 않는 소스 — 기상(기온·강수량)은 % 변화가 무의미(0 분모·부호 전환)
NO_PCT_SOURCES = {"KMA"}


def load_raw() -> pd.DataFrame | None:
    path = Path(MACRO_RAW_CSV)
    if not path.exists():
        print(f"[안내] raw 파일이 없습니다: {path}")
        print("        먼저 collect_macro_fred.py / collect_macro_ecos.py 를 실행하세요.")
        return None
    df = pd.read_csv(str(path), encoding="utf-8-sig")
    if df.empty:
        print("[안내] raw 가 비어 있습니다.")
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "value"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    return df


def _pct(cur: pd.Series, base: pd.Series) -> pd.Series:
    """(cur / base - 1) * 100, 분모 0 → NaN (inf 방지)."""
    out = (cur / base.where(base != 0) - 1.0) * 100.0
    return out.replace([np.inf, -np.inf], np.nan)


def _asof_prev(obs: pd.Series, idx: pd.DatetimeIndex, offset: pd.DateOffset) -> pd.Series:
    """idx 각 날짜의 (날짜 - offset) 시점 값. 그 날 관측이 없으면 ASOF_TOLERANCE 이내 직전 관측."""
    target = idx - offset
    vals = obs.reindex(target, method="ffill", tolerance=ASOF_TOLERANCE)
    return pd.Series(vals.values, index=idx)


def build_daily(df_raw: pd.DataFrame) -> pd.DataFrame:
    """indicator_id 별 일별 확장 + ma30/yoy/mom 산출 (long format). yoy/mom 은 원 주기 기준."""
    today = pd.Timestamp.today().normalize()
    # 메타(국가·이름·단위·freq·source)는 indicator_id 별 마지막 값 사용
    meta_cols = ["country", "indicator_name", "unit", "freq", "source"]
    meta = (
        df_raw.sort_values("date")
        .groupby("indicator_id")[meta_cols]
        .last()
    )

    out_frames = []
    for indicator_id, g in df_raw.groupby("indicator_id"):
        g = g.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        g = g.set_index("date")
        obs = g["value"]
        freq = str(meta.loc[indicator_id, "freq"]).upper()
        source = str(meta.loc[indicator_id, "source"]).upper()
        start = min(HISTORY_START, g.index.min())

        if freq == "M":
            # 월 시계열(월초 기준)에서 전월·전년동월 대비 → 일별로 펼침 (as-of, limit 없음)
            m = obs.copy()
            m.index = m.index.to_period("M").to_timestamp()
            m = m[~m.index.duplicated(keep="last")]
            m = m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="MS"))
            mom_m = _pct(m, m.shift(1))
            yoy_m = _pct(m, m.shift(12))
            end = max(today, g.index.max())
            daily_idx = pd.date_range(start=start, end=end, freq="D")
            value = m.reindex(daily_idx).ffill()
            mom = mom_m.reindex(daily_idx).ffill()
            yoy = yoy_m.reindex(daily_idx).ffill()
        else:
            # 일별·주별: 짧은 결측만 ffill, 비교는 달력 기준 1개월/1년 전 관측(asof, 7일 이내 직전 관측)
            limit = DAILY_FFILL_LIMIT.get(source, FREQ_FFILL_LIMIT.get(freq, DAILY_FFILL_LIMIT_DEFAULT))
            last_obs = g.index.max()
            end = last_obs if source in DAILY_FFILL_LIMIT else max(last_obs, min(today, last_obs + pd.Timedelta(days=limit)))
            daily_idx = pd.date_range(start=start, end=end, freq="D")
            value = obs.reindex(daily_idx).ffill(limit=limit)
            if source in NO_PCT_SOURCES:
                # 기온(°C, 0 부근 부호 전환)·강수량(0mm 다수)은 변화율이 의미 없어 산출하지 않음
                yoy = pd.Series(np.nan, index=daily_idx)
                mom = pd.Series(np.nan, index=daily_idx)
            else:
                yoy = _pct(value, _asof_prev(obs, daily_idx, pd.DateOffset(years=1)))
                mom = _pct(value, _asof_prev(obs, daily_idx, pd.DateOffset(months=1)))

        frame = pd.DataFrame({
            "date": daily_idx,
            "value": value.values,
            "yoy_pct": yoy.values,
            "mom_pct": mom.values,
        })
        frame["indicator_id"] = indicator_id
        frame["ma30"] = frame["value"].rolling(window=30, min_periods=15).mean()

        # HISTORY_START 이전(있다면)·값이 없는 날(ffill 한도 초과 결측)은 잘라낸다
        frame = frame[(frame["date"] >= HISTORY_START) & frame["value"].notna()]
        out_frames.append(frame)

    if not out_frames:
        return pd.DataFrame()

    daily = pd.concat(out_frames, ignore_index=True)
    # 메타 병합
    daily = daily.merge(meta, on="indicator_id", how="left")

    # 반올림 (소수 4자리)
    for c in ("value", "ma30", "yoy_pct", "mom_pct"):
        daily[c] = daily[c].round(4)

    col_order = [
        "date", "country", "indicator_id", "indicator_name",
        "value", "unit", "freq", "source",
        "ma30", "yoy_pct", "mom_pct",
    ]
    daily = daily[[c for c in col_order if c in daily.columns]]
    daily = daily.sort_values(["indicator_id", "date"]).reset_index(drop=True)
    return daily


def build_dashboard(daily: pd.DataFrame) -> pd.DataFrame:
    """가격 데이터와 date 기준 merge 가능한 wide 포맷.
    컬럼: date, <indicator_id>(value), <indicator_id>_yoy_pct ...
    """
    if daily.empty:
        return pd.DataFrame()

    value_wide = daily.pivot_table(
        index="date", columns="indicator_id", values="value", aggfunc="last"
    )
    yoy_wide = daily.pivot_table(
        index="date", columns="indicator_id", values="yoy_pct", aggfunc="last"
    )
    # yoy 를 산출하지 않는 지표(기상)도 컬럼은 유지 (스키마 호환)
    yoy_wide = yoy_wide.reindex(columns=value_wide.columns)
    yoy_wide.columns = [f"{c}_yoy_pct" for c in yoy_wide.columns]

    wide = value_wide.join(yoy_wide, how="left").reset_index()
    wide = wide.sort_values("date").reset_index(drop=True)
    return wide


def main():
    ensure_dirs()
    df_raw = load_raw()
    if df_raw is None:
        # 산출물 없이 정상 종료 (파이프라인 non-critical)
        return

    daily = build_daily(df_raw)
    if daily.empty:
        print("[안내] 일별 산출 결과가 비어 있습니다.")
        return

    atomic_to_csv(daily, MACRO_PROCESSED_CSV, index=False, encoding="utf-8-sig")
    print(f"[완료] processed 저장: {MACRO_PROCESSED_CSV} "
          f"({len(daily)} rows, indicator {daily['indicator_id'].nunique()}종)")

    wide = build_dashboard(daily)
    atomic_to_csv(wide, MACRO_DASHBOARD_CSV, index=False, encoding="utf-8-sig")
    print(f"[완료] dashboard 저장: {MACRO_DASHBOARD_CSV} "
          f"({len(wide)} rows, {wide.shape[1]-1} cols)")


if __name__ == "__main__":
    main()
