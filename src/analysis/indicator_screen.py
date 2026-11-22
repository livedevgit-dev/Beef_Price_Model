"""
[파일 정의서]
- 파일명: indicator_screen.py
- 역할: 분석 (파이프라인 --full 끝에 자동 실행, 정보성)
- 목적: config/indicators.csv 에 등록된 모든 지표가 수입육 가격과 '어느 지평에서, 몇 달 선행해서' 관계가 있는지
        한 표로 점검한다. 지표를 새로 추가하면 다음 전체 갱신 때 자동으로 평가되므로 코드 수정이 필요 없다.
- 방법:
    · 지표: 월 평균 → 로그 변화 Δ_h (h = 1, 3, 6개월). 발표시차(publish_lag_m)만큼 뒤로 밀어 '월말에 알 수 있는 값'으로 맞춤.
    · 타깃: 삼겹양지 월가(samgyup_unified_monthly), 미트박스 미국·호주 도매지수(브랜드 체인), 수입 쇠고기 CPI(장기, 1995~).
    · 지표가 k개월(0~6) 선행할 때 Δ_h 타깃과 Δ_h 지표의 상관 r, 표본 n, 그리고 전후반 분할 부호 일치(stable).
    · 2026-11 교훈: 월(h=1) 상관은 대부분 잡음 — h=6 에서 |r|≥0.3 이고 stable 인 것만 '쓸 만함'으로 표시.
- 산출물: data/3_reports/analysis/indicator_screen.csv (전체), 콘솔에 지평 6개월 상위 15개
- 주의: 조합이 많아 우연한 상관이 섞인다. 이 표는 '후보 선별용'이며 모델 채택은 walk-forward 로 따로 검증할 것.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, DATA_PROCESSED, DATA_REPORTS, MACRO_RAW_CSV  # noqa: E402
from utils.indicator_registry import load_registry  # noqa: E402
from utils.io_safe import atomic_to_csv  # noqa: E402

OUT = DATA_REPORTS / "analysis" / "indicator_screen.csv"
HORIZONS = (1, 3, 6)
LEADS = range(0, 7)
MIN_N = 24
GOOD_R, GOOD_H, GOOD_HALF = 0.40, 6, 0.25     # 선행 7개×지평 3개를 훑으므로 느슨한 기준은 우연 상관을 다수 통과시킴
SELF_PAIRS = {("kr_cpi_beef_imp", "수입 쇠고기 CPI")}  # 지표 = 타깃 자기 상관 제외


def _monthly(s: pd.Series) -> pd.Series:
    s = s.dropna().sort_index()
    m = s.groupby(s.index.to_period("M").to_timestamp()).mean()
    return m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="MS"))


def load_targets() -> dict[str, pd.Series]:
    T = {}
    sg = pd.read_csv(DATA_PROCESSED / "samgyup_unified_monthly.csv", parse_dates=["date"]).set_index("date")["price_won_per_kg"]
    T["삼겹양지(월)"] = _monthly(sg)
    d = pd.read_csv(DASHBOARD_READY_CSV, parse_dates=["date"], low_memory=False)
    d = d[~d["is_filled"].astype(str).str.lower().eq("true") & d["wholesale_price"].notna()]
    for cat, nm in (("미국", "미트박스 미국"), ("호주", "미트박스 호주")):
        g = d[d["category"] == cat].copy()
        g["m"] = g["date"].dt.to_period("M").dt.to_timestamp()
        pv = np.log(g.groupby(["part", "brand", "m"])["wholesale_price"].mean().unstack("m"))
        chg = (pv - pv.shift(1, axis=1)).mean(axis=0)          # 브랜드 체인 로그 변화
        lvl = np.exp(chg.fillna(0).cumsum()) * 100
        lvl[chg.isna()] = np.nan
        T[nm] = _monthly(lvl)
    mac = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    cpi = mac[mac["indicator_id"] == "kr_cpi_beef_imp"].set_index("date")["value"].astype(float)
    if len(cpi):
        T["수입 쇠고기 CPI"] = _monthly(cpi)
    return T


def load_indicators() -> tuple[dict[str, pd.Series], pd.DataFrame]:
    reg = load_registry()
    mac = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    mac["value"] = pd.to_numeric(mac["value"], errors="coerce")
    X = {}
    for iid in reg["indicator_id"]:
        s = mac[mac["indicator_id"] == iid].set_index("date")["value"]
        if s.notna().sum() >= MIN_N:
            X[iid] = _monthly(s)
    return X, reg.set_index("indicator_id")


def _dlog(s: pd.Series, h: int) -> pd.Series:
    if (s <= 0).any():                       # 기온 등 음수 가능 → 차분
        return s - s.shift(h)
    return np.log(s) - np.log(s.shift(h))


def screen() -> pd.DataFrame:
    T = load_targets()
    X, reg = load_indicators()
    rows = []
    for iid, x in X.items():
        lag_pub = int(reg.loc[iid, "publish_lag_m"])
        for tn, y in T.items():
            if (iid, tn) in SELF_PAIRS:
                continue
            for h in HORIZONS:
                dy, dx = _dlog(y, h), _dlog(x, h).shift(lag_pub)
                for k in LEADS:
                    s = pd.concat([dx.shift(k), dy], axis=1).dropna()
                    if len(s) < MIN_N:
                        continue
                    r = s.iloc[:, 0].corr(s.iloc[:, 1])
                    half = len(s) // 2
                    r1 = s.iloc[:half, 0].corr(s.iloc[:half, 1])
                    r2 = s.iloc[half:, 0].corr(s.iloc[half:, 1])
                    stable = bool(np.sign(r1) == np.sign(r2)) and min(abs(r1), abs(r2)) >= GOOD_HALF
                    rows.append({"indicator_id": iid, "group": reg.loc[iid, "group"], "label": reg.loc[iid, "label_ko"],
                                 "target": tn, "horizon_m": h, "lead_m": k, "publish_lag_m": lag_pub,
                                 "n": len(s), "r": round(r, 3), "r_half1": round(r1, 2), "r_half2": round(r2, 2),
                                 "stable": stable, "useful": bool(stable and h >= GOOD_H and abs(r) >= GOOD_R)})
    return pd.DataFrame(rows)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = screen()
    atomic_to_csv(df, OUT, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 220)
    best = (df[df["horizon_m"] == GOOD_H].assign(absr=lambda d: d["r"].abs())
              .sort_values(["useful", "absr"], ascending=False).groupby(["indicator_id", "target"]).head(1)
              .sort_values(["useful", "absr"], ascending=False).head(15))
    print(f"[지표 스크리닝] 지표 {df['indicator_id'].nunique()}종 × 타깃 {df['target'].nunique()}개 → {len(df)}행 저장: {OUT}")
    print(f"[지평 {GOOD_H}개월, 지표별 최적 선행] 상위 15 (useful = 전후반 부호 일치 & |r|≥{GOOD_R}):")
    print(best[["label", "target", "lead_m", "n", "r", "r_half1", "r_half2", "useful"]].to_string(index=False))
    n_useful = df[df["useful"]].groupby("indicator_id").size()
    print(f"[요약] useful 조합이 있는 지표 {len(n_useful)}종: {', '.join(n_useful.index)}")


if __name__ == "__main__":
    main()
