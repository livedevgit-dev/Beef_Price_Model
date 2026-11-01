"""
[파일 정의서]
- 파일명: au_safeguard_event.py
- 역할: 분석 (재실행용)
- 질문: 호주산 쿼터(한·호주 FTA 농산물 세이프가드) 소진·연말 효과로 미국산 삼겹양지 가격이 오르는가?
- 데이터: 미트박스 master_price_data.csv(실제 관측 2025-01~), data/1_processed/samgyup_unified_monthly.csv,
          KMTA 수입량, USDA Primal Plate, 환율
- 방법:
    1. 삼겹양지 미국/호주 브랜드 바스켓(관측일 30% 이상 브랜드, 브랜드별 자기 평균으로 정규화 후 평균)
       → 브랜드 구성 변화 제거
    2. 소진일 전후 -30/+30/+60/+90일 가격 변화, 호주/미국 가격비
    3. 11월→1월 연말 구간 변화, 원화 환산 원가(플레이트 USD/kg × 환율) 대비
- 산출물: data/3_reports/analysis/au_safeguard_event.csv, au_safeguard_yearend.csv
- 한계: 미트박스 실관측은 소진 이벤트 2회(2025, 2026)뿐 — 통계적 검정이 아니라 사례 비교임
- 주의: KMTA 수입량은 검역 기준이라 쿼터(통관 기준) 소진을 추적하지 못한다
        (예: 2026-02-20 쿼터 사용 45.6%≈8.9만t vs KMTA 1~2월 2.7만t, 보세 이월분이 1월에 몰려 통관됨)
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DATA_PROCESSED, DATA_REPORTS, EXCHANGE_RATE_XLSX, MASTER_PRICE_CSV,  # noqa: E402
                    USDA_PLATE_USD_KG_CSV)
from utils.io_safe import atomic_to_csv  # noqa: E402

OUT = DATA_REPORTS / "analysis"
PART = "삼겹양지"

# 연도별 쿼터(공개 보도 기준). 소진일이 없는 해는 미발동 또는 날짜 미확인
SAFEGUARD = [
    {"year": 2020, "quota_t": 174087, "trigger": "2020-11-25", "note": "Beef Central"},
    {"year": 2021, "quota_t": None, "trigger": "2021-11-22", "note": "Beef Central"},
    {"year": 2022, "quota_t": None, "trigger": None, "note": "미발동 (MLA)"},
    {"year": 2023, "quota_t": 184742, "trigger": "2023-12-08", "note": "12-08~11 보도 엇갈림"},
    {"year": 2024, "quota_t": 188437, "trigger": "2024-10-25", "note": "10월 말 (일자는 추정치)"},
    {"year": 2025, "quota_t": 192206, "trigger": "2025-09-12", "note": "세계일보·Beef Central"},
    {"year": 2026, "quota_t": 196050, "trigger": "2026-07-21", "note": "세계일보·서울경제"},
]


def basket(m: pd.DataFrame, country: str) -> pd.Series:
    x = m[(m["part"] == PART) & (m["country"] == country)]
    pv = x.pivot_table(index="date", columns="part_name", values="wholesale_price", aggfunc="mean").sort_index()
    # 관측일 30% 이상 브랜드를 자기 평균으로 정규화 (쿼터 소진 후 호주 브랜드가 빠져도 끊기지 않게)
    keep = pv.columns[pv.notna().mean() >= 0.3]
    norm = pv[keep] / pv[keep].mean()
    return norm.mean(axis=1) * pv[keep].mean().mean()


def listed_brands(m: pd.DataFrame) -> pd.DataFrame:
    """월별 일평균 등록 브랜드 수 — 쿼터 소진 후 호주산 물량 위축의 간접 지표."""
    x = m[m["part"] == PART]
    daily = x.groupby(["country", "date"])["part_name"].nunique().rename("n").reset_index()
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    return daily.pivot_table(index="month", columns="country", values="n", aggfunc="mean").round(1)


def at(s: pd.Series, d: pd.Timestamp):
    v = s[(s.index <= d) & (s.index > d - pd.Timedelta(days=10))]
    return float(v.iloc[-1]) if len(v) else None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(MASTER_PRICE_CSV, parse_dates=["date"])
    m["part"] = m["part_name"].str.split("|").str[0].str.split("-").str[0].str.strip()
    m = m[m["date"] >= "2025-01-22"]
    us, au = basket(m, "미국"), basket(m, "호주")

    u = pd.read_csv(USDA_PLATE_USD_KG_CSV, parse_dates=["report_date"])
    plate = u[u["primal_desc"].str.contains("Plate", case=False, na=False)].groupby("report_date")["choice_usd_per_kg"].mean()
    ex = pd.read_excel(EXCHANGE_RATE_XLSX)
    fx = pd.Series(pd.to_numeric(ex["Close"], errors="coerce").values, index=pd.to_datetime(ex["Date"])).dropna()
    cost = (plate * fx.reindex(plate.index, method="ffill")).dropna()

    rows = []
    for ev in SAFEGUARD:
        if not ev["trigger"]:
            continue
        t = pd.Timestamp(ev["trigger"])
        base_us, base_au, base_c = at(us, t), at(au, t), at(cost, t)
        for off in (-30, 30, 60, 90):
            d = t + pd.Timedelta(days=off)
            if d > us.index.max() and off > 0:
                continue
            vu, va, vc = at(us, d), at(au, d), at(cost, d)
            if base_us is None or vu is None:
                continue
            rows.append({"year": ev["year"], "trigger": ev["trigger"], "offset_days": off,
                         "us_chg_pct": round((vu / base_us - 1) * 100, 1),
                         "au_chg_pct": round((va / base_au - 1) * 100, 1) if va and base_au else None,
                         "krw_cost_chg_pct": round((vc / base_c - 1) * 100, 1) if vc and base_c else None,
                         "au_over_us": round(va / vu, 3) if va else None})
    atomic_to_csv(pd.DataFrame(SAFEGUARD), OUT / "au_safeguard_history.csv", index=False, encoding="utf-8-sig")
    ev_df = pd.DataFrame(rows)
    atomic_to_csv(ev_df, OUT / "au_safeguard_event.csv", index=False, encoding="utf-8-sig")

    ye = []
    for y in (2025,):
        for a, b, label in [(f"{y}-11-15", f"{y}-12-15", "11/15→12/15"), (f"{y}-12-15", f"{y + 1}-01-15", "12/15→1/15"),
                            (f"{y}-11-15", f"{y + 1}-01-31", "11/15→1/31")]:
            a, b = pd.Timestamp(a), pd.Timestamp(b)
            ye.append({"window": f"{y} {label}", "us_chg_pct": round((at(us, b) / at(us, a) - 1) * 100, 1),
                       "au_chg_pct": round((at(au, b) / at(au, a) - 1) * 100, 1),
                       "krw_cost_chg_pct": round((at(cost, b) / at(cost, a) - 1) * 100, 1)})
    ye_df = pd.DataFrame(ye)
    atomic_to_csv(ye_df, OUT / "au_safeguard_yearend.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 200)
    print(ev_df.to_string(index=False))
    print(ye_df.to_string(index=False))
    mon = pd.DataFrame({"미국": us.resample("MS").mean(), "호주": au.resample("MS").mean(),
                        "원화원가": cost.resample("MS").mean()}).loc["2025-07":].round(0)
    mon["호주/미국"] = (mon["호주"] / mon["미국"]).round(3)
    print(mon.to_string())
    raw_au = m[(m["part"] == PART) & (m["country"] == "호주")].groupby("date")["wholesale_price"].mean()
    print("호주 단순평균(월):", raw_au.resample("MS").mean().loc["2026-05":].round(0).to_dict())
    print(listed_brands(m).loc["2025-07":].to_string())


if __name__ == "__main__":
    main()
