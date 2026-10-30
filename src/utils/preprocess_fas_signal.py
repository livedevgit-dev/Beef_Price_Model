"""
[파일 정의서]
- 파일명: preprocess_fas_signal.py
- 역할: 가공 (덤핑/다이버전 조기경보 신호 생성)
- 대상: 미국 소고기 수출 (중국 vs 한국)
- 데이터 소스: data/0_raw/fas_export_sales_raw.csv (collect_fas_export_sales.py)
- 출력: data/2_dashboard/fas_supply_signal.csv (월별)
- 주요 기능:
    1. 주간 수출(weeklyExports)을 국가별·월별 집계 (중국 / 한국)
       - 월합계(china_exp/korea_exp)는 차트 호환용으로 유지하되, 판단은 "월내 주평균"으로 한다.
         (주간 데이터를 월로 합치면 목요일이 4번인 달과 5번인 달이 최대 25% 차이 나는 달력 착시 발생)
    2. 고정 장기 기준선(baseline) 대비 비율
       - 중국: 2021~2024 완결월 주평균의 중앙값 (2020년 미·중 1단계 합의로 시장 개방 이후 정상 수준)
       - 한국: 2019~2024 같은 달(1~12월) 주평균의 중앙값 (계절성 반영)
       - 기준선에는 하한(floor)을 둬 0 나누기·과대 배율을 막는다.
       ※ 과거 12개월 롤링 중앙값 방식은 중국행이 0 근처로 장기화되면 기준선 자체가 0 으로 내려가
         "569배·정상" 같은 오판이 났음 → 고정 기준선으로 변경 (2026-10 정합성 수정)
    3. 다이버전 경보 산출:
       - 중국행 주평균이 기준선의 50% 미만(=미국산이 중국에 못 들어감) + 한국행이 같은 달 기준선의 110% 초과
         → 한국 공급과잉 → 삼겹양지 등 수입육 가격 하방 위험 "경보"
    4. 경보 레벨: 정상 / 주의(중국 저조) / 경보(중국 저조 + 한국 과잉)
       (중국 기준선 기간 이전 월 = 시장 개방 이전은 중국 저조 판단을 하지 않음)
    5. 미완결 월(집계된 주 수 < 해당 월 목요일 수, 예: 진행 중인 이번 달)은 is_partial=True 로 표시하고
       경보 판단에서 제외한다 (alert_level·*_vs_med = 결측, note = '집계중').

산출 컬럼: date, china_exp, korea_exp(월합계, MT),
           china_vs_med(중국 주평균/고정 기준선), korea_vs_med(한국 주평균/같은 달 기준선),
           alert_level(0정상/1주의/2경보, 미완결 월은 결측), note,
           weeks(집계 주 수), expected_weeks(해당 월 목요일 수), is_partial,
           china_wk_avg, korea_wk_avg(주평균), china_base, korea_base(기준선)
※ 컬럼명 china_vs_med/korea_vs_med 는 하위 호환(Home·07 페이지·리포트·HTML 대시보드)을 위해 유지.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import FAS_EXPORT_SALES_CSV, FAS_SIGNAL_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# 경보 임계치
CHINA_DROP_RATIO = 0.5    # 중국행 주평균이 기준선의 50% 미만이면 "저조"
KOREA_HIGH_RATIO = 1.10   # 한국행 주평균이 같은 달 기준선의 110% 초과면 "과잉"

# 고정 기준선 기간 (완결월만 사용)
CHINA_BASE_YEARS = (2021, 2024)
KOREA_BASE_YEARS = (2019, 2024)
# 기준선 하한 (MT/주) — 기준 기간 데이터가 비정상적으로 작을 때 배율 폭주 방지
CHINA_BASE_FLOOR = 500.0
KOREA_BASE_FLOOR = 1000.0


def _thursdays_in_month(month_start: pd.Timestamp) -> int:
    """FAS 주간 보고 기준일(week ending = 목요일)이 그 달에 몇 번 있는지."""
    days = pd.date_range(month_start, month_start + pd.offsets.MonthEnd(0), freq="D")
    return int((days.dayofweek == 3).sum())


def main() -> None:
    ensure_dirs()
    path = Path(FAS_EXPORT_SALES_CSV)
    if not path.exists():
        print(f"[안내] FAS raw 없음: {path} — collect_fas_export_sales.py 먼저 실행")
        return

    d = pd.read_csv(path, low_memory=False)
    if d.empty:
        print("[안내] FAS raw 가 비어 있습니다.")
        return

    d["week"] = pd.to_datetime(d["week_ending"], errors="coerce")
    d["weekly_exports"] = pd.to_numeric(d["weekly_exports"], errors="coerce")
    d = d.dropna(subset=["week"])
    d["date"] = d["week"].dt.to_period("M").dt.to_timestamp()

    piv = d.pivot_table(index="date", columns="country_name",
                        values="weekly_exports", aggfunc="sum")
    piv = piv.rename(columns={"중국": "china_exp", "한국": "korea_exp"})
    for c in ("china_exp", "korea_exp"):
        if c not in piv.columns:
            piv[c] = np.nan
    piv = piv.sort_index()

    # 월내 집계 주 수 / 기대 주 수(목요일 수) → 미완결 월 판정
    piv["weeks"] = d.groupby("date")["week"].nunique().reindex(piv.index)
    piv["expected_weeks"] = [_thursdays_in_month(m) for m in piv.index]
    piv["is_partial"] = piv["weeks"] < piv["expected_weeks"]

    # 주평균 (달력 착시 제거)
    piv["china_wk_avg"] = piv["china_exp"] / piv["weeks"]
    piv["korea_wk_avg"] = piv["korea_exp"] / piv["weeks"]

    # 고정 기준선 (완결월만)
    full = piv[~piv["is_partial"]]
    yrs = full.index.year
    china_hist = full.loc[(yrs >= CHINA_BASE_YEARS[0]) & (yrs <= CHINA_BASE_YEARS[1]), "china_wk_avg"]
    china_base = max(float(china_hist.median()) if china_hist.notna().any() else 0.0, CHINA_BASE_FLOOR)
    korea_hist = full.loc[(yrs >= KOREA_BASE_YEARS[0]) & (yrs <= KOREA_BASE_YEARS[1]), "korea_wk_avg"]
    korea_by_month = korea_hist.groupby(korea_hist.index.month).median()
    korea_all = float(korea_hist.median()) if korea_hist.notna().any() else 0.0
    piv["china_base"] = china_base
    piv["korea_base"] = [max(float(korea_by_month.get(m.month, korea_all)), KOREA_BASE_FLOOR)
                         for m in piv.index]

    piv["china_vs_med"] = piv["china_wk_avg"] / piv["china_base"]
    piv["korea_vs_med"] = piv["korea_wk_avg"] / piv["korea_base"]
    # 미완결 월은 비율을 비워 둔다 (읽는 쪽이 dropna 로 '마지막 완결월' 경보를 쓰도록)
    piv.loc[piv["is_partial"], ["china_vs_med", "korea_vs_med"]] = np.nan

    def level(row):
        if row["is_partial"]:
            return np.nan, f"집계중 ({int(row['weeks'])}/{int(row['expected_weeks'])}주) — 경보 판단 제외"
        if row.name.year < CHINA_BASE_YEARS[0]:
            # 중국 시장 개방(2020) 이전: 중국행이 원래 작았으므로 '저조' 판단 대상이 아님
            return 0, "정상 (중국 시장 개방 이전 — 중국 기준 판단 제외)"
        china_drop = pd.notna(row["china_vs_med"]) and row["china_vs_med"] < CHINA_DROP_RATIO
        korea_high = pd.notna(row["korea_vs_med"]) and row["korea_vs_med"] > KOREA_HIGH_RATIO
        if china_drop and korea_high:
            return 2, "경보: 중국행 저조 + 한국행 과잉 → 공급과잉·가격 하방 위험"
        if china_drop:
            return 1, "주의: 중국행 저조 (평시 대비 50% 미만, 한국 전가 가능성 모니터링)"
        return 0, "정상"

    lv = piv.apply(level, axis=1, result_type="expand")
    piv["alert_level"] = lv[0].astype("Float64")
    piv["note"] = lv[1]

    out = piv.reset_index()[["date", "china_exp", "korea_exp",
                             "china_vs_med", "korea_vs_med", "alert_level", "note",
                             "weeks", "expected_weeks", "is_partial",
                             "china_wk_avg", "korea_wk_avg", "china_base", "korea_base"]]
    out["alert_level"] = out["alert_level"].astype("Int64")
    out = out.round({"china_vs_med": 2, "korea_vs_med": 2, "china_wk_avg": 1, "korea_wk_avg": 1,
                     "china_base": 1, "korea_base": 1})
    atomic_to_csv(out, FAS_SIGNAL_CSV, index=False, encoding="utf-8-sig")
    print(f"[완료] FAS 공급경보 저장: {FAS_SIGNAL_CSV} ({len(out)}개월)")
    print(f"   └ 기준선: 중국 {china_base:,.0f} MT/주 ({CHINA_BASE_YEARS[0]}~{CHINA_BASE_YEARS[1]}), "
          f"한국 같은 달 중앙값 {KOREA_BASE_YEARS[0]}~{KOREA_BASE_YEARS[1]}")

    # 최근 경보 상태 출력
    recent = out.tail(7)
    if not recent.empty:
        print("\n[최근 경보]")
        for _, r in recent.iterrows():
            if pd.isna(r["alert_level"]):
                print(f"  {r['date'].strftime('%Y-%m')}: {r['note']}")
                continue
            tag = {0: "정상", 1: "주의", 2: "경보"}[int(r["alert_level"])]
            print(f"  {r['date'].strftime('%Y-%m')}: [{tag}] 중국 {r['china_vs_med']}x / 한국 {r['korea_vs_med']}x")


if __name__ == "__main__":
    main()
