"""
[파일 정의서]
- 파일명: preprocess_fas_signal.py
- 역할: 가공 (덤핑/다이버전 조기경보 신호 생성)
- 대상: 미국 소고기 수출 (중국 vs 한국)
- 데이터 소스: data/0_raw/fas_export_sales_raw.csv (collect_fas_export_sales.py)
- 출력: data/2_dashboard/fas_supply_signal.csv (월별)
- 주요 기능:
    1. 주간 수출(weeklyExports)을 국가별·월별 집계 (중국 / 한국)
    2. 다이버전 경보 산출:
       - 중국행이 추세 대비 급감(=미국산이 중국에 못 들어감) + 한국행이 평소보다 높음
         → 한국 공급과잉 → 삼겹양지 등 수입육 가격 하방 위험 "경보"
    3. 경보 레벨: 정상 / 주의(중국 급감) / 경보(중국 급감 + 한국 과잉)

산출 컬럼: date, china_exp, korea_exp, china_vs_med(중국/12개월중앙값),
           korea_vs_med, alert_level(0정상/1주의/2경보), note
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import FAS_EXPORT_SALES_CSV, FAS_SIGNAL_CSV, ensure_dirs

# 경보 임계치
CHINA_DROP_RATIO = 0.5    # 중국행이 12개월 중앙값의 50% 미만이면 "급감"
KOREA_HIGH_RATIO = 1.10   # 한국행이 12개월 중앙값의 110% 초과면 "과잉"


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

    # 12개월 롤링 중앙값 대비 비율
    piv["china_med"] = piv["china_exp"].rolling(12, min_periods=6).median()
    piv["korea_med"] = piv["korea_exp"].rolling(12, min_periods=6).median()
    piv["china_vs_med"] = piv["china_exp"] / piv["china_med"]
    piv["korea_vs_med"] = piv["korea_exp"] / piv["korea_med"]

    def level(row):
        china_drop = pd.notna(row["china_vs_med"]) and row["china_vs_med"] < CHINA_DROP_RATIO
        korea_high = pd.notna(row["korea_vs_med"]) and row["korea_vs_med"] > KOREA_HIGH_RATIO
        if china_drop and korea_high:
            return 2, "경보: 중국행 급감 + 한국행 과잉 → 공급과잉·가격 하방 위험"
        if china_drop:
            return 1, "주의: 중국행 급감 (한국 전가 가능성 모니터링)"
        return 0, "정상"

    lv = piv.apply(level, axis=1, result_type="expand")
    piv["alert_level"] = lv[0]
    piv["note"] = lv[1]

    out = piv.reset_index()[["date", "china_exp", "korea_exp",
                             "china_vs_med", "korea_vs_med", "alert_level", "note"]]
    out = out.round({"china_vs_med": 2, "korea_vs_med": 2})
    out.to_csv(str(FAS_SIGNAL_CSV), index=False, encoding="utf-8-sig")
    print(f"[완료] FAS 공급경보 저장: {FAS_SIGNAL_CSV} ({len(out)}개월)")

    # 최근 경보 상태 출력
    recent = out.dropna(subset=["china_vs_med"]).tail(6)
    if not recent.empty:
        print("\n[최근 6개월 경보]")
        for _, r in recent.iterrows():
            tag = {0: "정상", 1: "주의", 2: "경보"}[int(r["alert_level"])]
            print(f"  {r['date'].strftime('%Y-%m')}: [{tag}] 중국 {r['china_vs_med']}x / 한국 {r['korea_vs_med']}x")


if __name__ == "__main__":
    main()
