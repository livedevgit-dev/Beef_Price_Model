"""
[파일 정의서]
- 파일명: preprocess_macro.py
- 역할: 가공 (Data Processing)
- 대상: 거시경제 지표 (Macro — 금리·CPI·PPI·옥수수·WTI)
- 데이터 소스: data/0_raw/macro_indicators_raw.csv (FRED + ECOS long format)
- 수집/가공 주기: 일단위
- 주요 기능:
    1. raw(long) 로드 → indicator_id 별로 2019-01-01 ~ 최신일 일별 인덱스 생성
    2. 월별 지표는 일별로 forward-fill (ML lag 용). 금리·물가는 다음 발표 전까지 값이
       유지되는 것이 정상이므로 ffill 에 limit 을 두지 않음 (가격 ffill 과 다른 정책)
    3. value, ma30, yoy_pct(전년동일 대비), mom_pct(약 30일 전 대비) 산출 (계산 가능한 것만)
    4. 산출물:
       - data/1_processed/macro_indicators_daily.csv  (long + ma30/yoy/mom)
       - data/2_dashboard/macro_dashboard_ready.csv    (wide: date × indicator, 가격 데이터와 merge용)

날짜 정책: raw 의 월별 date 는 YYYY-MM-01 로 통일되어 있으며, 전처리에서 일별로 확장한다.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    MACRO_RAW_CSV,
    MACRO_PROCESSED_CSV,
    MACRO_DASHBOARD_CSV,
    ensure_dirs,
)

HISTORY_START = pd.Timestamp(2019, 1, 1)


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


def build_daily(df_raw: pd.DataFrame) -> pd.DataFrame:
    """indicator_id 별 일별 ffill + ma30/yoy/mom 산출 (long format)."""
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

        start = min(HISTORY_START, g.index.min())
        end = max(today, g.index.max())
        daily_idx = pd.date_range(start=start, end=end, freq="D")

        # 일별 인덱스로 확장 후 ffill (금리·물가는 다음 발표 전까지 유지 → limit 없음)
        s = g["value"].reindex(daily_idx).ffill()

        frame = pd.DataFrame({"date": daily_idx, "value": s.values})
        frame["indicator_id"] = indicator_id
        # 보조지표
        frame["ma30"] = frame["value"].rolling(window=30, min_periods=15).mean()
        frame["yoy_pct"] = (frame["value"] / frame["value"].shift(365) - 1.0) * 100.0
        frame["mom_pct"] = (frame["value"] / frame["value"].shift(30) - 1.0) * 100.0

        # HISTORY_START 이전(있다면)은 잘라낸다
        frame = frame[frame["date"] >= HISTORY_START]
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

    daily.to_csv(str(MACRO_PROCESSED_CSV), index=False, encoding="utf-8-sig")
    print(f"[완료] processed 저장: {MACRO_PROCESSED_CSV} "
          f"({len(daily)} rows, indicator {daily['indicator_id'].nunique()}종)")

    wide = build_dashboard(daily)
    wide.to_csv(str(MACRO_DASHBOARD_CSV), index=False, encoding="utf-8-sig")
    print(f"[완료] dashboard 저장: {MACRO_DASHBOARD_CSV} "
          f"({len(wide)} rows, {wide.shape[1]-1} cols)")


if __name__ == "__main__":
    main()
