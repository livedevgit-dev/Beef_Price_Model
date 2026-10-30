"""
[파일 정의서]
- 파일명: src/Models/domestic_vs_import.py
- 역할: 검증·분석 (읽기 전용 — 원천/가공 데이터를 수정하지 않음)
- 가설(트레이더 증언): "국내산(한우) 소고기 가격과 수입 소고기 가격은 상관관계가 매우 높다."
- 데이터 소스:
    - data/1_processed/han_auction_daily.csv        EKAPE 한우 도체 경락가(전국계, 등급 전체/1++/1, 두수 포함)
    - data/2_dashboard/hanwoo_dashboard_ready.csv   KAMIS 한우 부위별 소매가(kamis_retail) + 수입 소고기 소매가(kamis_retail_import)
    - data/2_dashboard/dashboard_ready_data.csv     미트박스 수입 도매가(is_filled==False 실관측만, 2025-01-22~)
    - data/1_processed/samgyup_unified_monthly.csv  삼겹양지 월별(딜러 데이터 접합, 2016-12~ 결측 달 있음)
- 방법:
    1. 계열 구성(월, 주): 경락가는 두수 가중 평균. KAMIS 는 일평균→기간 평균(이상치 제외).
       미트박스 부위 지수 = log(가격) ~ 브랜드 고정효과 + 기간효과 (브랜드 구성 변화 제거) → 기간효과를 부위 지수로,
       수입 지수 = 원산지(미국/호주)별 부위 지수(각 평균 0으로 정규화)의 기간별 평균.
    2. 상관: 수준(level) vs 변화율(로그차분, 월=MoM, 주=WoW)·전년동월비(YoY) · 계절/명절 더미 제거 잔차.
       리드/래그: 월 −3..+3, 주 −4..+4. lag k>0 = 국내 변화가 k기 '먼저'(국내 선행), k<0 = 수입 선행.
    3. Granger 형 단순 F 검정(OLS 직접 계산): 자기 시차만 vs + 상대 시차, 양방향.
    4. 롤링 12개월 상관(월 변화율) — 관계의 안정성.
    5. 유통마진: KAMIS 수입 소매(원/kg) ÷ 미트박스 같은 원산지·부위 도매(원/kg) − 1.
- 출력: data/3_reports/analysis/
    domestic_vs_import_monthly.csv / _weekly.csv (계열), _corr.csv, _granger.csv, _rolling.csv,
    import_retail_margin.csv, domestic_vs_import.md (요약)
- 주의: 미트박스는 2025-01 이후뿐이라 월 표본 ~21. 여러 쌍을 동시에 보므로 단일 p<0.05 는 우연일 수 있다.
"""

from __future__ import annotations

import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (DASHBOARD_READY_CSV, DATA_PROCESSED, DATA_REPORTS, HAN_AUCTION_DAILY_CSV,
                    HANWOO_DASHBOARD_CSV, ensure_dirs)
from utils.io_safe import atomic_to_csv

OUT_DIR = DATA_REPORTS / "analysis"
SAMGYUP_CSV = DATA_PROCESSED / "samgyup_unified_monthly.csv"

MONTH_LAGS = range(-3, 4)
WEEK_LAGS = range(-4, 5)
MIN_N = 12                     # 상관 계산 최소 표본
MEATBOX_START = "2025-01-22"   # 미트박스 실관측 시작(백필 포함)
KAMIS_MIN_DAYS_M = 10          # KAMIS 월평균 인정 최소 관측일
KAMIS_MIN_DAYS_W = 3           # KAMIS 주평균 인정 최소 관측일

# 설·추석 당일 (명절 더미용). 명절 수요는 명절 전 2~3주에 몰린다
SEOLLAL = ["2019-02-05", "2020-01-25", "2021-02-12", "2022-02-01", "2023-01-22",
           "2024-02-10", "2025-01-29", "2026-02-17"]
CHUSEOK = ["2019-09-13", "2020-10-01", "2021-09-21", "2022-09-10", "2023-09-29",
           "2024-09-17", "2025-10-06", "2026-09-25"]
HOLIDAYS = pd.to_datetime(SEOLLAL + CHUSEOK)

# 미트박스 부위 ↔ 한우 부위 매핑 (수입육 시장에서 실제로 대체·비교되는 부위 기준)
#   갈비: 미국 LA갈비(찜·구이 갈비), 갈비살/늑간살, 등갈비/백립 / 호주 갈비살·등갈비
#   양지: 미국 삼겹양지(우삼겹), 차돌박이 / 호주 차돌양지, 삼겹양지
#   등심: 미국·호주 알목심(척아이롤 — 수입 '등심' 대체 구이용)
#   설도: 호주 설도
MEATBOX_MAP: dict[str, list[tuple[str, str]]] = {
    "갈비": [("미국", "LA갈비"), ("미국", "갈비살/늑간살"), ("미국", "등갈비/백립"),
             ("호주", "갈비살/늑간살"), ("호주", "등갈비/백립")],
    "양지": [("미국", "삼겹양지"), ("미국", "차돌박이"), ("호주", "차돌양지"), ("호주", "삼겹양지")],
    "등심": [("미국", "알목심"), ("호주", "알목심")],
    "설도": [("호주", "설도")],
}
# 수입 지수 구성 부위: 커버리지(기간 중 관측 비율)가 이 이상인 부위만
INDEX_MIN_COVERAGE = 0.8

# 유통마진 비교쌍: (KAMIS 수입 소매 part, 원산지) → 미트박스 (category, part)
#   KAMIS '갈비'(수입)는 뼈갈비 소매 → 미국은 LA갈비, 호주는 앞/척갈비가 가장 가까운 도매 품목(근사)
MARGIN_PAIRS = [
    ("수입 갈비살", "미국", "미국", "갈비살/늑간살"),
    ("수입 갈비살", "호주", "호주", "갈비살/늑간살"),
    ("수입 갈비", "미국", "미국", "LA갈비"),
    ("수입 갈비", "호주", "호주", "앞/척갈비"),
]


# --------------------------------------------------------------------------
# 계열 구성
# --------------------------------------------------------------------------
def _period(dates: pd.Series, freq: str) -> pd.Series:
    d = pd.to_datetime(dates)
    if freq == "M":
        return d.dt.to_period("M").dt.to_timestamp()
    return d.dt.to_period("W-SUN").dt.start_time      # 주 = 월~일, 라벨은 월요일


def load_auction(freq: str) -> dict[str, pd.Series]:
    """EKAPE 전국 경락가(원/kg) — 두수 가중. 일별 행만 사용, (잔존) 30일 합산 행은 월 계열에서만 종료월에 배정."""
    df = pd.read_csv(HAN_AUCTION_DAILY_CSV, low_memory=False, parse_dates=["date"])
    df = df[df["is_national_total"].astype(str).str.lower().eq("true")]
    df = df[df["sex"].fillna("전체").eq("전체")]
    if freq == "W":
        df = df[df["period_days"] == 1]
    out = {}
    for g, label in [("전체", "경락_전체"), ("1++", "경락_1++"), ("1", "경락_1")]:
        x = df[(df["grade"] == g) & df["price_won_per_kg"].notna() & (df["head_count"] > 0)].copy()
        x["amt"] = x["price_won_per_kg"] * x["head_count"]
        # 기간합산 행(백필 미완료 구간)은 두수·금액을 합산 구간의 각 날짜에 균등 배분한 뒤 달에 귀속(근사)
        multi = x[x["period_days"] > 1]
        if not multi.empty:
            rep = multi.loc[multi.index.repeat(multi["period_days"])].copy()
            rep["date"] = rep["date"] - pd.to_timedelta(rep.groupby(level=0).cumcount(), unit="D")
            rep[["amt", "head_count"]] = rep[["amt", "head_count"]].div(rep["period_days"], axis=0)
            x = pd.concat([x[x["period_days"] == 1], rep], ignore_index=True)
        x["p"] = _period(x["date"], freq)
        x["h_multi"] = x["head_count"].where(x["period_days"] > 1, 0.0)
        gsum = x.groupby("p")[["amt", "head_count", "h_multi"]].sum()
        out[label] = gsum["amt"] / gsum["head_count"]
        if g == "전체":
            out["경락두수_전체"] = gsum["head_count"]
            # 1 이면 그 달 값이 전부 30일 합산 행의 비례배분(근사) — 일별 백필 완료 후 0
            out["경락_합산배분비율"] = (gsum["h_multi"] / gsum["head_count"]).round(3)
    return out


def _kamis_period_mean(x: pd.DataFrame, freq: str) -> pd.Series:
    """일평균 → 기간 평균. 관측일이 적은 기간(월 10일·주 3일 미만)은 결측
    (2022 상반기 이전 KAMIS 축산 소매는 대부분 0=미조사라 드문 관측만 남아 있다)."""
    daily = x.groupby("date")["price_won_per_kg"].mean()
    g = daily.groupby(_period(daily.index.to_series(), freq).values)
    m, n = g.mean(), g.size()
    return m[n >= (KAMIS_MIN_DAYS_M if freq == "M" else KAMIS_MIN_DAYS_W)]


def load_kamis(freq: str) -> dict[str, pd.Series]:
    """KAMIS 소매(원/kg): 한우 부위(1+ 등급 기본, 갈비는 1 등급도) + 수입 소고기(원산지별)."""
    h = pd.read_csv(HANWOO_DASHBOARD_CSV, low_memory=False, parse_dates=["date"])
    h = h[h["source"].isin(["kamis_retail", "kamis_retail_import"])]
    if "is_outlier" in h.columns:
        h = h[~h["is_outlier"].astype(str).str.lower().eq("true")]
    out = {}
    hw = h[h["source"] == "kamis_retail"]
    for part in ["등심", "갈비", "양지", "설도", "안심"]:
        for grade in ["1+", "1"]:
            x = hw[(hw["part"] == part) & (hw["grade"] == grade)]
            if len(x):
                out[f"한우소매_{part}_{grade}"] = _kamis_period_mean(x, freq)
    imp = h[h["source"] == "kamis_retail_import"]
    if not imp.empty and "origin" in imp.columns:
        for (part, origin), x in imp.groupby(["part", "origin"]):
            out[f"수입소매_{part.replace('수입 ', '')}_{origin}"] = _kamis_period_mean(x, freq)
        # 수입 소매 지수: 4개 계열(갈비·갈비살 × 美·濠)을 '계열' 고정효과 + 기간효과로 결합(계열 결측에 강건)
        cols = [k for k in out if k.startswith("수입소매_")]
        if cols:
            lp = np.log(pd.concat({k: out[k] for k in cols}, axis=1).sort_index())
            out["수입소매지수"] = np.exp(_two_way_fe(lp)) * 100
    return out


def _two_way_fe(lp: pd.DataFrame) -> pd.Series:
    """lp: index=period, columns=brand, 값=log 가격. 브랜드 고정효과 + 기간효과(교대 투영). 기간효과 반환(평균 0)."""
    a = lp.mean(axis=0) * 0.0
    d = pd.Series(0.0, index=lp.index)
    for _ in range(200):
        d_new = lp.sub(a, axis=1).mean(axis=1, skipna=True)
        a = lp.sub(d_new, axis=0).mean(axis=0, skipna=True)
        if np.nanmax(np.abs((d_new - d).to_numpy())) < 1e-9:
            d = d_new
            break
        d = d_new
    return d - d.mean()


def load_meatbox(freq: str) -> tuple[dict[str, pd.Series], dict[str, pd.Series], pd.DataFrame]:
    """미트박스 부위 지수(log 기간효과) + 원산지별 수입 지수 + 부위별 중앙가격(원/kg)."""
    m = pd.read_csv(DASHBOARD_READY_CSV, low_memory=False, parse_dates=["date"])
    m = m[~m["is_filled"].astype(str).str.lower().eq("true")]
    m = m[(m["date"] >= MEATBOX_START) & (m["wholesale_price"] > 0)]
    m["p"] = _period(m["date"], freq)
    n_periods = m["p"].nunique()

    part_idx: dict[str, pd.Series] = {}
    med_price = {}
    for (cat, part), x in m.groupby(["category", "part"]):
        lp = np.log(x.groupby(["p", "brand"])["wholesale_price"].mean()).unstack("brand")
        med_price[f"{cat}|{part}"] = x.groupby("p")["wholesale_price"].median()
        if lp.notna().any(axis=1).sum() < max(MIN_N, INDEX_MIN_COVERAGE * n_periods):
            continue
        part_idx[f"{cat}|{part}"] = _two_way_fe(lp)

    index: dict[str, pd.Series] = {}
    for cat in ["미국", "호주"]:
        cols = [k for k in part_idx if k.startswith(cat + "|")]
        if cols:
            index[f"수입지수_{cat}"] = np.exp(pd.concat([part_idx[k] for k in cols], axis=1).mean(axis=1)) * 100
    if part_idx:
        index["수입지수_전체"] = np.exp(pd.concat(list(part_idx.values()), axis=1).mean(axis=1)) * 100
    for hpart, members in MEATBOX_MAP.items():
        cols = [f"{c}|{p}" for c, p in members if f"{c}|{p}" in part_idx]
        if cols:
            index[f"수입도매_{hpart}군"] = np.exp(pd.concat([part_idx[k] for k in cols], axis=1).mean(axis=1)) * 100
    for k, v in part_idx.items():
        part_idx[k] = np.exp(v) * 100
    return part_idx, index, pd.DataFrame(med_price)


def load_samgyup() -> pd.Series:
    s = pd.read_csv(SAMGYUP_CSV, parse_dates=["date"])
    return s.set_index("date")["price_won_per_kg"].sort_index()


def build_frame(freq: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    series: dict[str, pd.Series] = {}
    series.update(load_auction(freq))
    series.update(load_kamis(freq))
    part_idx, mb_index, med = load_meatbox(freq)
    series.update(mb_index)
    for k, v in part_idx.items():
        series["미트박스_" + k.replace("|", "_")] = v
    if freq == "M":
        series["삼겹양지_월(접합)"] = load_samgyup()
    df = pd.concat(series, axis=1).sort_index()
    full = pd.date_range(df.index.min(), df.index.max(), freq="MS" if freq == "M" else "W-MON")
    df = df.reindex(full)
    df.index.name = "period"
    return df, med.reindex(full), part_idx


# --------------------------------------------------------------------------
# 통계
# --------------------------------------------------------------------------
def _holiday_dummies(idx: pd.DatetimeIndex, freq: str) -> pd.DataFrame:
    """명절 전 수요 더미. 월: '명절 10일 전'이 속한 달. 주: 명절 전 3주~명절 주 / 명절 다음 주."""
    if freq == "M":
        pre = pd.Series(0.0, index=idx)
        for h in HOLIDAYS:
            pre.loc[pre.index == (h - pd.Timedelta(days=10)).to_period("M").to_timestamp()] = 1.0
        return pd.DataFrame({"pre_holiday": pre})
    pre = pd.Series(0.0, index=idx)
    post = pd.Series(0.0, index=idx)
    for h in HOLIDAYS:
        wk = h.to_period("W-SUN").start_time
        pre.loc[(idx >= wk - pd.Timedelta(weeks=3)) & (idx <= wk)] = 1.0
        post.loc[idx == wk + pd.Timedelta(weeks=1)] = 1.0
    return pd.DataFrame({"pre_holiday": pre, "post_holiday": post})


def deseasonalize(chg: pd.Series, freq: str) -> pd.Series:
    """변화율에서 달(월 계열) 더미 + 명절 더미를 회귀로 제거한 잔차. 표본이 작으면 명절 더미만."""
    s = chg.dropna()
    if len(s) < 10:
        return chg * np.nan
    X = _holiday_dummies(s.index, freq)
    if freq == "M" and len(s) >= 36:
        X = pd.concat([X, pd.get_dummies(s.index.month, prefix="m", drop_first=True, dtype=float)
                       .set_index(s.index)], axis=1)
    X = X.loc[:, X.std() > 0]
    X.insert(0, "const", 1.0)
    beta, *_ = np.linalg.lstsq(X.to_numpy(), s.to_numpy(), rcond=None)
    return (s - X.to_numpy() @ beta).reindex(chg.index)


def _corr(a: pd.Series, b: pd.Series) -> tuple[float, int, float]:
    z = pd.concat([a, b], axis=1).dropna()
    n = len(z)
    if n < MIN_N or z.iloc[:, 0].std() == 0 or z.iloc[:, 1].std() == 0:
        return np.nan, n, np.nan
    r, p = stats.pearsonr(z.iloc[:, 0], z.iloc[:, 1])
    return float(r), n, float(p)


def transforms(s: pd.Series, freq: str) -> dict[str, pd.Series]:
    ls = np.log(s)
    out = {"level": s, "chg": ls.diff()}
    if freq == "M":
        out["yoy"] = ls.diff(12)
    out["chg_deseason"] = deseasonalize(out["chg"], freq)
    return out


def granger_f(y: pd.Series, x: pd.Series, L: int) -> tuple[float, float, int]:
    """y_t ~ c + y_{t-1..L} (제약) vs + x_{t-1..L} (비제약). 반환 (F, p, n)."""
    cols = {"y": y}
    for i in range(1, L + 1):
        cols[f"y{i}"] = y.shift(i)
        cols[f"x{i}"] = x.shift(i)
    z = pd.DataFrame(cols).dropna()
    n = len(z)
    k_u = 1 + 2 * L
    if n - k_u < 8:
        return np.nan, np.nan, n
    Y = z["y"].to_numpy()
    Xr = np.column_stack([np.ones(n)] + [z[f"y{i}"] for i in range(1, L + 1)])
    Xu = np.column_stack([Xr] + [z[f"x{i}"] for i in range(1, L + 1)])
    rss = lambda X: float(np.sum((Y - X @ np.linalg.lstsq(X, Y, rcond=None)[0]) ** 2))
    rss_r, rss_u = rss(Xr), rss(Xu)
    F = ((rss_r - rss_u) / L) / (rss_u / (n - k_u))
    return F, float(stats.f.sf(F, L, n - k_u)), n


# 검정 쌍: (국내 계열, 수입 계열, 설명)
MONTHLY_PAIRS = [
    ("경락_전체", "삼겹양지_월(접합)", "장기: 한우 경락 vs 수입 삼겹양지(딜러+미트박스)"),
    ("경락_전체", "수입소매지수", "중기: 한우 경락 vs KAMIS 수입 소매(갈비·갈비살 美/濠)"),
    ("한우소매_갈비_1+", "수입소매지수", "중기: 한우 갈비 소매 vs KAMIS 수입 소매지수"),
    ("한우소매_갈비_1+", "수입소매_갈비_미국", "중기: 한우 갈비 소매 vs 수입 갈비 소매(美)"),
    ("한우소매_갈비_1+", "수입소매_갈비_호주", "중기: 한우 갈비 소매 vs 수입 갈비 소매(濠)"),
    ("한우소매_양지_1+", "삼겹양지_월(접합)", "장기: 한우 양지 소매 vs 수입 삼겹양지"),
    ("경락_전체", "수입지수_전체", "단기: 한우 경락 vs 미트박스 수입 도매지수"),
    ("경락_전체", "수입지수_미국", "단기: 한우 경락 vs 미트박스 美 지수"),
    ("경락_전체", "수입지수_호주", "단기: 한우 경락 vs 미트박스 濠 지수"),
    ("경락_1++", "수입지수_전체", "단기: 경락 1++ vs 수입 도매지수"),
    ("경락_1", "수입지수_전체", "단기: 경락 1등급 vs 수입 도매지수"),
    ("한우소매_갈비_1+", "수입도매_갈비군", "단기: 한우 갈비 소매 vs 수입 갈비군 도매"),
    ("한우소매_양지_1+", "수입도매_양지군", "단기: 한우 양지 소매 vs 수입 양지군 도매"),
    ("한우소매_등심_1+", "수입도매_등심군", "단기: 한우 등심 소매 vs 수입 알목심 도매"),
    ("한우소매_설도_1+", "수입도매_설도군", "단기: 한우 설도 소매 vs 호주 설도 도매"),
]
WEEKLY_PAIRS = [p for p in MONTHLY_PAIRS if p[0] != "" and "삼겹양지_월" not in p[1]]


def analyze(df: pd.DataFrame, freq: str, pairs) -> tuple[pd.DataFrame, pd.DataFrame]:
    lags = MONTH_LAGS if freq == "M" else WEEK_LAGS
    L_g = 2 if freq == "M" else 4
    corr_rows, g_rows = [], []
    for dom, imp, desc in pairs:
        if dom not in df or imp not in df:
            continue
        td, ti = transforms(df[dom], freq), transforms(df[imp], freq)
        for tr in td:
            for k in (lags if tr != "level" else [0]):
                # lag k: corr(국내_t, 수입_{t+k}) → k>0 이면 국내가 먼저 움직임
                r, n, p = _corr(td[tr], ti[tr].shift(-k))
                corr_rows.append({"freq": freq, "domestic": dom, "imported": imp, "desc": desc,
                                  "transform": tr, "lag": k, "r": r, "n": n, "p": p})
        for tr in ["chg", "chg_deseason"]:
            for direction, y, x in [("국내→수입", ti[tr], td[tr]), ("수입→국내", td[tr], ti[tr])]:
                F, p, n = granger_f(y, x, L_g)
                g_rows.append({"freq": freq, "domestic": dom, "imported": imp, "transform": tr,
                               "direction": direction, "lags": L_g, "F": F, "p": p, "n": n})
    return pd.DataFrame(corr_rows), pd.DataFrame(g_rows)


def rolling_corr(df: pd.DataFrame, pairs, window: int = 12) -> pd.DataFrame:
    rows = []
    for dom, imp, _ in pairs:
        if dom not in df or imp not in df:
            continue
        a, b = np.log(df[dom]).diff(), np.log(df[imp]).diff()
        r = a.rolling(window, min_periods=window - 2).corr(b)
        n = pd.concat([a, b], axis=1).notna().all(axis=1).astype(float).rolling(window, min_periods=1).sum()
        for t in r.dropna().index:
            rows.append({"period": t.strftime("%Y-%m"), "domestic": dom, "imported": imp,
                         "window": window, "r": r[t], "n": int(n[t])})
    return pd.DataFrame(rows)


def margins(med_m: pd.DataFrame, kamis_m: dict[str, pd.Series]) -> pd.DataFrame:
    rows = []
    for kpart, origin, cat, mpart in MARGIN_PAIRS:
        kname = f"수입소매_{kpart.replace('수입 ', '')}_{origin}"
        mname = f"{cat}|{mpart}"
        if kname not in kamis_m or mname not in med_m:
            continue
        z = pd.concat([kamis_m[kname].rename("retail"), med_m[mname].rename("wholesale")], axis=1).dropna()
        for t, r in z.iterrows():
            rows.append({"period": t.strftime("%Y-%m"), "kamis_part": kpart, "origin": origin,
                         "meatbox_part": f"{cat} {mpart}", "retail_won_kg": round(r["retail"]),
                         "wholesale_won_kg": round(r["wholesale"]),
                         "margin_pct": round((r["retail"] / r["wholesale"] - 1) * 100, 1)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# 요약 (markdown)
# --------------------------------------------------------------------------
def _fmt(r, n, p=None) -> str:
    if pd.isna(r):
        return f"n/a (n={n})"
    star = "" if p is None or pd.isna(p) else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
    return f"{r:+.2f}{star} (n={n})"


def _best_lag(corr: pd.DataFrame, freq: str, dom: str, imp: str, tr: str) -> pd.Series | None:
    x = corr[(corr["freq"] == freq) & (corr["domestic"] == dom) & (corr["imported"] == imp)
             & (corr["transform"] == tr)].dropna(subset=["r"])
    if x.empty:
        return None
    return x.loc[x["r"].abs().idxmax()]


# 판정에 쓰는 핵심 쌍 (freq, 국내, 수입)
KEY_PAIRS = [
    ("M", "경락_전체", "삼겹양지_월(접합)"),
    ("M", "경락_전체", "수입소매지수"),
    ("M", "한우소매_갈비_1+", "수입소매지수"),
    ("M", "경락_전체", "수입지수_전체"),
    ("M", "경락_전체", "수입지수_미국"),
    ("W", "경락_전체", "수입지수_전체"),
    ("W", "한우소매_갈비_1+", "수입도매_갈비군"),
    ("W", "한우소매_양지_1+", "수입도매_양지군"),
    ("M", "한우소매_양지_1+", "수입도매_양지군"),
]


def _multi_share_note(dfm: pd.DataFrame) -> str:
    sh = dfm.get("경락_합산배분비율")
    if sh is None or not (sh > 0).any():
        return "없음 (전 구간 일별)"
    s = sh[sh > 0]
    return f"{s.index.min():%Y-%m}~{s.index.max():%Y-%m} 중 {len(s)}개월"


def verdict_lines(corr: pd.DataFrame, gr: pd.DataFrame, dfm: pd.DataFrame) -> list[str]:
    """핵심 쌍별 자동 판정. 수준 상관은 추세 공유로 부풀려지므로 변화율·리드래그·Granger 로 판단."""
    L = ["## 0. 자동 판정 (핵심 쌍)\n"]
    sh = dfm.get("경락_합산배분비율", pd.Series(dtype=float))
    for freq, dom, imp in KEY_PAIRS:
        sub = corr[(corr["freq"] == freq) & (corr["domestic"] == dom) & (corr["imported"] == imp)]
        if sub.empty or sub["r"].notna().sum() == 0:
            continue
        lv = sub[sub["transform"] == "level"].iloc[0]
        c0 = sub[(sub["transform"] == "chg") & (sub["lag"] == 0)].iloc[0]
        b = _best_lag(corr, freq, dom, imp, "chg")
        g = gr[(gr["freq"] == freq) & (gr["domestic"] == dom) & (gr["imported"] == imp) & (gr["transform"] == "chg")]
        gp = dict(zip(g["direction"], g["p"]))
        unit = "개월" if freq == "M" else "주"
        lead = "" if b is None else ("동시" if b["lag"] == 0 else
                                      f"{'국내' if b['lag'] > 0 else '수입'} {abs(int(b['lag']))}{unit} 선행")
        if b is not None and b["r"] >= 0.4 and b["p"] < 0.05:
            v = f"변화율 연동 있음(중간 이상) — {lead}"
        elif b is not None and b["r"] >= 0.25 and b["p"] < 0.05:
            v = f"약한 변화율 연동 — {lead}"
        elif lv["r"] >= 0.6 and (pd.isna(c0["r"]) or abs(c0["r"]) < 0.3):
            v = "수준만 동행(추세 공유) — 단기 변화율 연동은 약함"
        else:
            v = "연동 근거 약함"
        flag = ""
        if dom.startswith("경락") and freq == "M" and not sh.empty:
            ov = sh.reindex(dfm[imp].dropna().index).fillna(0)
            if (ov > 0).any():
                flag = (f" ⚠ 겹치는 기간 중 {int((ov > 0).sum())}개월의 경락 월값이 30일 합산 비례배분(시점 흐림 → "
                        f"'국내 선행' 착시 가능; 일별 백필 완료 후 재실행 필요)")
        gtxt = (f"Granger p 국내→수입 {gp['국내→수입']:.3f} / 수입→국내 {gp['수입→국내']:.3f}"
                if pd.notna(gp.get("국내→수입", np.nan)) and pd.notna(gp.get("수입→국내", np.nan)) else "Granger n/a")
        best = f"lag {int(b['lag']):+d} {_fmt(b['r'], int(b['n']), b['p'])}" if b is not None else "-"
        L.append(f"- **{dom} ↔ {imp}** ({'월' if freq == 'M' else '주'}): 수준 {_fmt(lv['r'], int(lv['n']), lv['p'])}, "
                 f"변화율 lag0 {_fmt(c0['r'], int(c0['n']), c0['p'])}, 최대 |r| {best}, {gtxt} → **{v}**{flag}")
    L.append("\n주의: 여러 쌍·여러 시차를 동시에 봤으므로(다중비교) 단일 p<0.05 는 우연일 수 있다. "
             "명절(설·추석)·계절이 양쪽을 같이 움직이는 공통 요인이므로 계절·명절 제거 열과 YoY 열을 함께 볼 것.\n")
    return L


def write_summary(corr: pd.DataFrame, gr: pd.DataFrame, roll: pd.DataFrame, marg: pd.DataFrame,
                  dfm: pd.DataFrame, dfw: pd.DataFrame) -> str:
    L = []
    L.append("# 국내산(한우) vs 수입 소고기 가격 연동성 검증")
    L.append(f"\n생성: {datetime.now():%Y-%m-%d %H:%M} · 스크립트 `src/Models/domestic_vs_import.py` (재실행 가능)\n")
    L.append("표기: r(n), `*` p<0.05, `**` p<0.01. lag k>0 = 국내 변화가 k기 먼저(국내 선행), k<0 = 수입 선행. "
             "chg = 로그 변화율(월 MoM / 주 WoW), yoy = 전년동월비, chg_deseason = 달·명절(설·추석) 더미 제거 잔차.\n")

    L.append("## 1. 데이터 범위\n")
    L.append("| 계열 | 월 시작 | 월 끝 | 월 n | 주 n |")
    L.append("|---|---|---|---|---|")
    n_mb = sum(c.startswith("미트박스_") for c in dfm.columns)
    for c in dfm.columns:
        s = dfm[c].dropna()
        if s.empty or c.startswith("미트박스_"):
            continue
        nw = int(dfw[c].notna().sum()) if c in dfw else 0
        L.append(f"| {c} | {s.index.min():%Y-%m} | {s.index.max():%Y-%m} | {len(s)} | {nw} |")

    L.append(f"\n(미트박스 개별 부위 지수 {n_mb}개는 CSV 참고.) 경락 월값 중 30일 합산 행 비례배분 구간(백필 미완료): "
             + _multi_share_note(dfm) + "\n")
    L[3:3] = verdict_lines(corr, gr, dfm)   # 판정을 맨 앞(표기 설명 바로 뒤)에 배치
    L.append("\n## 2. 수준 vs 변화율 상관 (동시점, lag 0)\n")
    L.append("| 쌍 | 주기 | 수준 | 변화율 | 계절·명절 제거 | YoY | 최대 |r| 변화율 lag |")
    L.append("|---|---|---|---|---|---|---|")
    for freq, pairs in [("M", MONTHLY_PAIRS), ("W", WEEKLY_PAIRS)]:
        for dom, imp, desc in pairs:
            sub = corr[(corr["freq"] == freq) & (corr["domestic"] == dom) & (corr["imported"] == imp)]
            if sub.empty:
                continue
            get = lambda tr, k=0: sub[(sub["transform"] == tr) & (sub["lag"] == k)]
            cells = []
            for tr in ["level", "chg", "chg_deseason", "yoy"]:
                x = get(tr)
                cells.append(_fmt(x["r"].iloc[0], int(x["n"].iloc[0]), x["p"].iloc[0]) if len(x) else "-")
            b = _best_lag(corr, freq, dom, imp, "chg")
            best = f"lag {int(b['lag']):+d}: {_fmt(b['r'], int(b['n']), b['p'])}" if b is not None else "-"
            L.append(f"| {dom} ↔ {imp} | {'월' if freq == 'M' else '주'} | " + " | ".join(cells) + f" | {best} |")

    L.append("\n## 3. 리드/래그 (변화율, 계절·명절 제거 전)\n")
    for freq in ["M", "W"]:
        lags = list(MONTH_LAGS if freq == "M" else WEEK_LAGS)
        L.append(f"\n**{'월' if freq == 'M' else '주'}** — 열 = lag\n")
        L.append("| 쌍 | " + " | ".join(f"{k:+d}" for k in lags) + " |")
        L.append("|---|" + "---|" * len(lags))
        sub = corr[(corr["freq"] == freq) & (corr["transform"] == "chg")]
        for (dom, imp), g in sub.groupby(["domestic", "imported"], sort=False):
            g = g.set_index("lag")
            L.append(f"| {dom} ↔ {imp} | " + " | ".join(
                _fmt(g.loc[k, "r"], int(g.loc[k, "n"]), g.loc[k, "p"]) if k in g.index else "-" for k in lags) + " |")

    L.append("\n## 4. Granger 형 F 검정 (변화율; 월 2시차·주 4시차)\n")
    L.append("| 쌍 | 주기 | 변환 | 국내→수입 p (n) | 수입→국내 p (n) |")
    L.append("|---|---|---|---|---|")
    for (freq, dom, imp, tr), g in gr.groupby(["freq", "domestic", "imported", "transform"], sort=False):
        g = g.set_index("direction")
        cell = lambda d: (f"{g.loc[d, 'p']:.3f} ({int(g.loc[d, 'n'])})" if pd.notna(g.loc[d, "p"])
                          else f"n/a ({int(g.loc[d, 'n'])})")
        L.append(f"| {dom} ↔ {imp} | {'월' if freq == 'M' else '주'} | {tr} | {cell('국내→수입')} | {cell('수입→국내')} |")

    if not roll.empty:
        L.append("\n## 5. 롤링 12개월 상관 (월 변화율) 요약\n")
        L.append("| 쌍 | 창 수 | 최소 | 중앙 | 최대 | 최근 |")
        L.append("|---|---|---|---|---|---|")
        for (dom, imp), g in roll.groupby(["domestic", "imported"], sort=False):
            L.append(f"| {dom} ↔ {imp} | {len(g)} | {g['r'].min():+.2f} | {g['r'].median():+.2f} | "
                     f"{g['r'].max():+.2f} | {g['r'].iloc[-1]:+.2f} ({g['period'].iloc[-1]}) |")

    if not marg.empty:
        L.append("\n## 6. 수입육 유통마진 (KAMIS 소매 ÷ 미트박스 도매 − 1, 월)\n")
        L.append("| 비교 | n(월) | 평균 마진 | 최소 | 최대 | 최근 |")
        L.append("|---|---|---|---|---|---|")
        for (kp, o, mp), g in marg.groupby(["kamis_part", "origin", "meatbox_part"], sort=False):
            L.append(f"| KAMIS {kp}({o}) vs 미트박스 {mp} | {len(g)} | {g['margin_pct'].mean():.0f}% | "
                     f"{g['margin_pct'].min():.0f}% | {g['margin_pct'].max():.0f}% | "
                     f"{g['margin_pct'].iloc[-1]:.0f}% ({g['period'].iloc[-1]}) |")
        L.append("\n※ KAMIS 소매는 대형마트·전통시장 평균 정육 판매가(100g→kg), 미트박스는 B2B 박스 단가(브랜드 중앙값). "
                 "규격·손질 차이가 있어 절대 마진보다 '추이'를 볼 것. 수입 '갈비' 쌍은 근사 매칭.")
    return "\n".join(L)


def main() -> None:
    ensure_dirs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dfm, med_m, _ = build_frame("M")
    dfw, _, _ = build_frame("W")
    dfw = dfw[dfw.index >= pd.Timestamp(MEATBOX_START) - pd.Timedelta(days=7)]

    cm, gm = analyze(dfm, "M", MONTHLY_PAIRS)
    cw, gw = analyze(dfw, "W", WEEKLY_PAIRS)
    corr = pd.concat([cm, cw], ignore_index=True)
    gr = pd.concat([gm, gw], ignore_index=True)
    roll = rolling_corr(dfm, [p for p in MONTHLY_PAIRS if p[0] == "경락_전체" or "소매" in p[1]])
    kam_m = {c: dfm[c] for c in dfm.columns if c.startswith("수입소매_")}
    marg = margins(med_m, kam_m)

    atomic_to_csv(dfm.round(4), OUT_DIR / "domestic_vs_import_monthly.csv", encoding="utf-8-sig")
    atomic_to_csv(dfw.round(4), OUT_DIR / "domestic_vs_import_weekly.csv", encoding="utf-8-sig")
    atomic_to_csv(corr.round(4), OUT_DIR / "domestic_vs_import_corr.csv", index=False, encoding="utf-8-sig")
    atomic_to_csv(gr.round(4), OUT_DIR / "domestic_vs_import_granger.csv", index=False, encoding="utf-8-sig")
    atomic_to_csv(roll.round(4), OUT_DIR / "domestic_vs_import_rolling.csv", index=False, encoding="utf-8-sig")
    atomic_to_csv(marg, OUT_DIR / "import_retail_margin.csv", index=False, encoding="utf-8-sig")

    md = write_summary(corr, gr, roll, marg, dfm, dfw)
    concl = OUT_DIR / "domestic_vs_import_conclusion.md"
    if concl.exists():   # 사람이 작성한 해석(결론) 파일이 있으면 요약 앞에 붙인다
        md = concl.read_text(encoding="utf-8").rstrip() + "\n\n---\n\n" + md
    (OUT_DIR / "domestic_vs_import.md").write_text(md, encoding="utf-8")
    print(f"[완료] 월 {len(dfm)}기 · 주 {len(dfw)}기, 상관 {len(corr)}행, Granger {len(gr)}행 → {OUT_DIR}")


if __name__ == "__main__":
    main()
