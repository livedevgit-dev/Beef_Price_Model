"""
[파일 정의서]
- 파일명: data_status.py
- 역할: 점검 (전체 데이터 신선도 현황판)
- 주요 기능: 모든 핵심 데이터셋의 '최신 데이터 일자 + 수집 주기 + 지연 + 상태'를 한 표로 출력/저장.
- 출력: data/2_dashboard/data_status.csv (BI·Home 에서 표시) — 컬럼: 데이터,소스,주기,최신데이터,지연(일),상태
- 실행: python src/utils/data_status.py  (또는 run_daily_update 종료 시 자동)
- 주기 표기: 일=매 영업일, 월=월 1회(보통 익월 중순 갱신)
- 판정 규칙:
    · 여러 지표를 묶은 행은 '가장 오래된' 구성 지표 기준 (일간 WTI 가 월간 옥수수·PPI 지연을 가리지 않게).
      데이터 칸에 기준이 된 지표를 [기준: id] 로 표시. 일간/월간 지표는 행을 분리.
    · 월간 '기간' 지표(월 평균·월간 합계)는 월말 기준으로 지연 계산, '시점' 지표(사육두수 재고 = 매월 1일)는
      그 날짜 기준 (월말 기준으로 재면 지연이 음수가 되던 문제).
    · 수입량은 최신 월의 data_source(KMTA 확정 / 식약처 잠정)를 이름·소스에 표시.
    · 재고는 결측 처리된 월(사이트 원본 오류)을 최신으로 치지 않음.
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
from utils.io_safe import atomic_to_csv

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


def _maxdate_xlsx(path, col, monthly_suffix=None, value_col=None):
    p = Path(path)
    if not p.exists():
        return None
    try:
        df = pd.read_excel(p)
    except Exception:
        return None
    if value_col and value_col in df.columns:
        df = df[pd.to_numeric(df[value_col], errors="coerce").notna()]   # 결측 처리된 월은 최신으로 치지 않음
    s = df[col].astype(str)
    if monthly_suffix:
        s = s + monthly_suffix
    d = pd.to_datetime(s, errors="coerce").dropna()
    return d.max() if not d.empty else None


def _macro_stalest(indicator_ids):
    """구성 지표별 최신일 중 가장 오래된 것 → (date, indicator_id). 아예 없는 지표가 있으면 (None, 그 지표)."""
    p = Path(MACRO_RAW_CSV)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, usecols=["date", "indicator_id"], low_memory=False)
    except Exception:
        return None
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    last = df.dropna(subset=["date"]).groupby("indicator_id")["date"].max()
    missing = [i for i in indicator_ids if i not in last.index]
    if missing:
        return (None, missing[0])
    sub = last.reindex(indicator_ids)
    # 구성 지표 최신일이 서로 다를 때만 기준 지표명 표시
    return (sub.min(), sub.idxmin() if sub.nunique() > 1 else None)


def _cof_stalest():
    """Cattle on Feed 구성 중 가장 지연된 것 → (date, label, point_in_time).
    재고(INVENTORY, 'FIRST OF xxx' = 그 달 1일 시점) / 입식(PLACEMENTS, 그 달 기간 합계)"""
    p = Path(US_CATTLE_ON_FEED_CSV)
    if not p.exists():
        return None
    try:
        c = pd.read_csv(p, usecols=["date", "short_desc"])
    except Exception:
        return None
    c["date"] = pd.to_datetime(c["date"], errors="coerce")
    best = None
    for key, label, point in [("INVENTORY", "inventory", True), ("PLACEMENTS", "placements", False)]:
        d = c[c["short_desc"].astype(str).str.contains(key, na=False)]["date"].max()
        if pd.isna(d):
            return (None, label, point)
        lag = (TODAY - (d if point else d + pd.offsets.MonthEnd(0))).days
        if best is None or lag > best[0]:
            best = (lag, d, label, point)
    return best[1:]


def _import_source_label():
    """최신 월의 data_source → (이름 표기, 소스 표기)"""
    try:
        df = pd.read_csv(MASTER_IMPORT_VOLUME_CSV, usecols=["std_date", "data_source"], dtype=str)
    except Exception:
        return "KMTA/식약처", "KMTA/식약처"
    last = df["std_date"].max()
    srcs = sorted(df.loc[df["std_date"] == last, "data_source"].dropna().unique())
    if srcs == ["KMTA"]:
        return "KMTA 확정", "KMTA"
    if srcs == ["MFDS"]:
        return "식약처 잠정", "식약처"
    return "KMTA+식약처", "KMTA/식약처"


def collect_status() -> pd.DataFrame:
    rows = []

    def add(name, src, freq, latest, ok_lag_days, point_in_time=False):
        if isinstance(latest, tuple):          # (date, 기준 지표) — 묶음 행은 가장 지연된 구성 지표 기준
            latest, member = latest
            if member:
                name = f"{name} [기준: {member}]"
        if latest is None or pd.isna(latest):
            rows.append({"데이터": name, "소스": src, "주기": freq, "최신데이터": "-",
                         "지연(일)": None, "상태": "없음"})
            return
        # 월간 '기간' 지표는 그 '달 전체'를 뜻하므로 지연은 월말(말일) 기준으로 계산
        # (월초 기준으로 재면 실제보다 ~30일 더 늦어 보이는 착시 발생)
        # 월간 '시점' 지표(매월 1일 재고 등)는 그 날짜 자체가 기준
        if str(freq).startswith("월") and not point_in_time:
            anchor = pd.Timestamp(latest) + pd.offsets.MonthEnd(0)
        else:
            anchor = pd.Timestamp(latest)
        lag = (TODAY - anchor).days
        status = "최신" if lag <= ok_lag_days else "지연"
        # 월간 지표는 "YYYY-MM (월간)" 표기 — '월 1일'로 오해 방지
        if str(freq).startswith("월") and not point_in_time:
            shown = pd.Timestamp(latest).strftime("%Y-%m") + " (월)"
        else:
            shown = pd.Timestamp(latest).strftime("%Y-%m-%d")
        rows.append({"데이터": name, "소스": src, "주기": freq,
                     "최신데이터": shown, "지연(일)": lag, "상태": status})

    # 일별 (영업일 기준, 5일 이내면 최신)
    add("미트박스 시세", "미트박스", "일", _maxdate_csv(DASHBOARD_READY_CSV, "date"), 5)
    add("USDA 부위시세", "USDA", "일", _maxdate_csv(USDA_BEEF_HISTORY_CSV, "report_date", fmt="%m/%d/%Y"), 7)
    add("환율(USD/KRW)", "ECOS", "일", _maxdate_xlsx(EXCHANGE_RATE_XLSX, "Date"), 5)
    add("한우 경락가(EKAPE)", "EKAPE", "일", _maxdate_csv(HAN_AUCTION_RAW_CSV, "auction_end_ymd", fmt="%Y%m%d"), 7)
    add("한우 도/소매(KAMIS)", "KAMIS", "일", _maxdate_csv(KAMIS_HANWOO_RAW_CSV, "reg_date"), 7)
    add("거시-미국 유가(FRED)", "FRED", "일", _macro_stalest(["us_wti"]), 7)
    # IMF 국제곡물가(익월 초)·미국 PPI(익월 중순) 발표 → 다음 발표 직전 최대 ~45일
    add("거시-미국 곡물·PPI(FRED)", "FRED", "월",
        _macro_stalest(["us_corn", "us_soybean", "us_soybean_meal", "us_food_ppi"]), 50)
    # CPI 익월 초, PPI 익월 ~20일 발표 → 다음 발표 직전 최대 ~50일
    add("거시-국내(ECOS)", "ECOS", "월", _macro_stalest(["kr_base_rate", "kr_cpi_food", "kr_ppi_food"]), 55)
    add("기후(기온·강수)", "KMA", "일", _macro_stalest(["kr_temp_avg", "kr_precip"]), 7)
    add("미국 수출(FAS)", "FAS", "주", _maxdate_csv(FAS_EXPORT_SALES_CSV, "week_ending"), 21)
    # Cattle on Feed: 매월 셋째~넷째 금요일 발표 (재고=당월 1일 시점, 입식=전월 기간) → 다음 발표 직전 최대 ~53일
    cof = _cof_stalest()
    if cof is None:
        add("사육두수(CattleOnFeed)", "USDA NASS", "월", None, 55)
    else:
        d, label, point = cof
        add("사육두수(CattleOnFeed)", "USDA NASS", "월", (d, label), 55, point_in_time=point)

    # 수요·유통 (소비시장 요인 — 유통채널/외식). 통계청 발표 ~익월 말 → 다음 발표 직전 최대 ~60일
    add("소매·외식(ECOS)", "ECOS", "월",
        _macro_stalest(["kr_retail_hypermarket", "kr_retail_cvs", "kr_retail_dept", "kr_service_food"]), 75)
    add("품목물가(쇠/돼지 CPI)", "ECOS", "월",
        _macro_stalest(["kr_cpi_beef_imp", "kr_cpi_beef_dom", "kr_cpi_pork"]), 45)
    # 원가·물류비·외식 소비 (2026-10 추가)
    add("환율(AUD/KRW)", "ECOS", "일", _macro_stalest(["kr_fx_aud"]), 7)
    add("호주 생우가(EYCI·Heavy Steer)", "MLA", "일", _macro_stalest(["au_eyci", "au_heavy_steer"]), 7)
    add("미국 경유(FRED)", "FRED", "주", _macro_stalest(["us_diesel"]), 14)
    # IMF 소고기 국제가(익월 초)·미국 PPI(익월 중순) → 다음 발표 직전 최대 ~45일
    add("수입원가(호주 소고기·미국 비육우·해상운임)", "FRED", "월",
        _macro_stalest(["au_beef_price", "us_fed_steer", "us_ppi_ocean_freight"]), 50)
    # 수입물가 익월 중순, CPI 익월 초, PPI 익월 ~20일 → 다음 발표 직전 최대 ~50일
    add("수입물가-쇠고기(ECOS)", "ECOS", "월", _macro_stalest(["kr_impi_beef_krw", "kr_impi_beef_lc"]), 50)
    add("물류비(경유·화물·냉동창고·외항)", "ECOS", "월",
        _macro_stalest(["kr_cpi_diesel", "kr_ppi_road_freight", "kr_ppi_cold_storage", "kr_ppi_ocean_freight"]), 55)
    add("외식물가(외식·쇠고기 외식)", "ECOS", "월", _macro_stalest(["kr_cpi_dineout", "kr_cpi_dineout_beef"]), 45)
    add("음식료품 소매판매(ECOS)", "ECOS", "월", _macro_stalest(["kr_retail_food"]), 75)
    # 공급(외식 대량소비·대체재) — 돼지 도매가 (일)
    add("돼지 도매가(KAMIS)", "KAMIS", "일", _maxdate_csv(KAMIS_PORK_RAW_CSV, "reg_date"), 7)

    # 월별 (전월 데이터가 익월 중순 갱신 → 45일 이내면 최신으로 간주)
    imp_label, imp_src = _import_source_label()
    add(f"수입량({imp_label})", imp_src, "월",
        _maxdate_csv(MASTER_IMPORT_VOLUME_CSV, "std_date", monthly_suffix="-01"), 45)
    # 재고는 KMTA 발표가 느려 통상 2개월가량 지연이 정상 → 75일 이내면 최신
    add("재고(KMTA)", "KMTA", "월",
        _maxdate_xlsx(BEEF_STOCK_XLSX, "기준년월", monthly_suffix="-01", value_col="조사재고량 조사재고량"), 75)

    return pd.DataFrame(rows)


def main():
    ensure_dirs()
    df = collect_status()
    atomic_to_csv(df, DATA_DASHBOARD / "data_status.csv", index=False, encoding="utf-8-sig")
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
