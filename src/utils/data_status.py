"""
[파일 정의서]
- 파일명: data_status.py
- 역할: 점검 (전체 데이터 신선도 현황판)
- 주요 기능: 모든 핵심 데이터셋의 '최신 데이터 일자 + 수집 주기 + 지연 + 상태'를 한 표로 출력/저장.
- 출력: data/2_dashboard/data_status.csv (BI·Home 에서 표시)
- 실행: python src/utils/data_status.py  (또는 run_daily_update 종료 시 자동)
- 주기 표기: 일=매 영업일, 월=월 1회(보통 익월 중순 갱신)
"""
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DASHBOARD_READY_CSV, MASTER_IMPORT_VOLUME_CSV, BEEF_STOCK_XLSX,
                    USDA_BEEF_HISTORY_CSV, EXCHANGE_RATE_XLSX, HAN_AUCTION_RAW_CSV,
                    KAMIS_HANWOO_RAW_CSV, KAMIS_PORK_RAW_CSV, MACRO_RAW_CSV, FAS_EXPORT_SALES_CSV,
                    US_CATTLE_ON_FEED_CSV, DATA_DASHBOARD, ensure_dirs)

TODAY = pd.Timestamp(datetime.now().date())


def _maxdate_csv(path, col, fmt=None, monthly_suffix=None):
    p = Path(path)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, usecols=[col], low_memory=False)
    except Exception:
        try:
            df = pd.read_csv(p, low_memory=False)
        except Exception:
            return None
    s = df[col].astype(str)
    if monthly_suffix:
        s = s + monthly_suffix
    d = pd.to_datetime(s, format=fmt, errors="coerce").dropna()
    return d.max() if not d.empty else None


def _maxdate_xlsx(path, col, monthly_suffix=None):
    p = Path(path)
    if not p.exists():
        return None
    try:
        df = pd.read_excel(p, usecols=[col])
    except Exception:
        try:
            df = pd.read_excel(p)
        except Exception:
            return None
    s = df[col].astype(str)
    if monthly_suffix:
        s = s + monthly_suffix
    d = pd.to_datetime(s, errors="coerce").dropna()
    return d.max() if not d.empty else None


def _macro_max(indicator_ids):
    p = Path(MACRO_RAW_CSV)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, usecols=["date", "indicator_id"], low_memory=False)
    except Exception:
        return None
    sub = df[df["indicator_id"].isin(indicator_ids)]
    d = pd.to_datetime(sub["date"], errors="coerce").dropna()
    return d.max() if not d.empty else None


def collect_status() -> pd.DataFrame:
    rows = []

    def add(name, src, freq, latest, ok_lag_days):
        if latest is None:
            rows.append({"데이터": name, "소스": src, "주기": freq, "최신데이터": "-",
                         "지연(일)": None, "상태": "없음"})
            return
        # 월간 지표는 그 '달 전체'를 뜻하므로 지연은 월말(말일) 기준으로 계산
        # (월초 기준으로 재면 실제보다 ~30일 더 늦어 보이는 착시 발생)
        if str(freq).startswith("월"):
            anchor = pd.Timestamp(latest) + pd.offsets.MonthEnd(0)
        else:
            anchor = pd.Timestamp(latest)
        lag = (TODAY - anchor).days
        status = "최신" if lag <= ok_lag_days else "지연"
        # 월간 지표는 "YYYY-MM (월간)" 표기 — '월 1일'로 오해 방지
        if str(freq).startswith("월"):
            shown = pd.Timestamp(latest).strftime("%Y-%m") + " (월)"
        else:
            shown = pd.Timestamp(latest).strftime("%Y-%m-%d")
        rows.append({"데이터": name, "소스": src, "주기": freq,
                     "최신데이터": shown, "지연(일)": lag, "상태": status})

    # 일별 (영업일 기준, 5일 이내면 최신)
    add("미트박스 시세", "미트박스", "일", _maxdate_csv(DASHBOARD_READY_CSV, "date"), 5)
    add("USDA 부위시세", "USDA", "일", _maxdate_csv(USDA_BEEF_HISTORY_CSV, "report_date", fmt="%m/%d/%Y"), 7)
    add("환율(USD/KRW)", "네이버", "일", _maxdate_xlsx(EXCHANGE_RATE_XLSX, "Date"), 5)
    add("한우 경락가(EKAPE)", "EKAPE", "일", _maxdate_csv(HAN_AUCTION_RAW_CSV, "auction_end_ymd", fmt="%Y%m%d"), 7)
    add("한우 도/소매(KAMIS)", "KAMIS", "일", _maxdate_csv(KAMIS_HANWOO_RAW_CSV, "reg_date"), 7)
    add("거시-미국(FRED)", "FRED", "일/월", _macro_max(["us_wti", "us_corn", "us_food_ppi"]), 40)
    add("거시-국내(ECOS)", "ECOS", "월", _macro_max(["kr_base_rate", "kr_cpi_food", "kr_ppi_food"]), 45)
    add("기후(기온·강수)", "KMA", "일", _macro_max(["kr_temp_avg", "kr_precip"]), 7)
    add("미국 수출(FAS)", "FAS", "주", _maxdate_csv(FAS_EXPORT_SALES_CSV, "week_ending"), 21)
    add("사육두수(CattleOnFeed)", "USDA NASS", "월", _maxdate_csv(US_CATTLE_ON_FEED_CSV, "date"), 45)

    # 수요·유통 (소비시장 요인 — 유통채널/외식). 통계청 발표시차 큼(현재 ~4개월) → 임계치 넉넉히
    add("소매·외식(ECOS)", "ECOS", "월",
        _macro_max(["kr_retail_hypermarket", "kr_retail_cvs", "kr_retail_dept", "kr_service_food"]), 120)
    add("품목물가(쇠/돼지 CPI)", "ECOS", "월",
        _macro_max(["kr_cpi_beef_imp", "kr_cpi_beef_dom", "kr_cpi_pork"]), 45)
    # 공급(외식 대량소비·대체재) — 돼지 도매가 (일)
    add("돼지 도매가(KAMIS)", "KAMIS", "일", _maxdate_csv(KAMIS_PORK_RAW_CSV, "reg_date"), 7)

    # 월별 (전월 데이터가 익월 중순 갱신 → 45일 이내면 최신으로 간주)
    add("수입량(KMTA)", "KMTA/식약처", "월", _maxdate_csv(MASTER_IMPORT_VOLUME_CSV, "std_date", monthly_suffix="-01"), 45)
    # 재고는 KMTA 발표가 느려 통상 2개월가량 지연이 정상 → 75일 이내면 최신
    add("재고(KMTA)", "KMTA", "월", _maxdate_xlsx(BEEF_STOCK_XLSX, "기준년월", monthly_suffix="-01"), 75)

    return pd.DataFrame(rows)


def main():
    ensure_dirs()
    df = collect_status()
    df.to_csv(DATA_DASHBOARD / "data_status.csv", index=False, encoding="utf-8-sig")
    print(f"\n{'='*64}")
    print(f"  [데이터 현황판]  기준: {TODAY.strftime('%Y-%m-%d')}")
    print(f"{'='*64}")
    print(df.to_string(index=False))
    delayed = df[df["상태"] == "지연"]
    if not delayed.empty:
        print(f"\n[주의] 지연 {len(delayed)}건: {', '.join(delayed['데이터'])}")
    print("※ 일별=매 영업일 / 월별=월1회(전월치가 보통 익월 중순 갱신)")


if __name__ == "__main__":
    main()
