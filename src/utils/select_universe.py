"""
[파일 정의서]
- 파일명: select_universe.py
- 역할: 가공 (모델·BI 대상 품목 동적 선정)
- 대상: 미트박스 수입육 전 품목
- 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
- 출력: data/2_dashboard/meatbox_universe.csv
- 기준(활성도, recency 우선):
    Tier 1 : 거래일 >= HIST_MIN AND 최근(RECENT_DAYS)일 거래일 >= RECENT_MIN  → 개별/앵커 가능
    Tier 2 : 최근일 거래일 >= RECENT_MIN AND 거래일 < HIST_MIN               → pooled 모델만
    제외   : 최근일 거래일 < RECENT_MIN                                       → 거래 끊김
- 품목 추가/제거에 자동 대응(하드코딩 금지). 모델·BI 가 이 함수를 공유한다.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, DATA_DASHBOARD, ensure_dirs

RECENT_DAYS = 90
RECENT_MIN = 60      # 최근 90일 중 거래일(주중 거의 매일이면 ~64)
HIST_MIN = 250       # 누적 거래일(약 1년)


def classify_universe(mb: pd.DataFrame,
                      recent_days: int = RECENT_DAYS,
                      recent_min: int = RECENT_MIN,
                      hist_min: int = HIST_MIN) -> pd.DataFrame:
    mb = mb.dropna(subset=["date", "part"]).copy()
    mb = mb[(mb["wholesale_price"].notna()) & (mb["wholesale_price"] > 0)]
    mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
    full_end = mb["date"].max()
    full_span = (full_end - mb["date"].min()).days + 1
    recent_cut = full_end - pd.Timedelta(days=recent_days)

    rows = []
    for part, g in mb.groupby("part"):
        ds = sorted(g["date"].dt.normalize().unique())
        n = len(ds)
        recent = g[g["date"] >= recent_cut]["date"].dt.normalize().nunique()
        max_gap = max(((pd.Timestamp(ds[i+1]) - pd.Timestamp(ds[i])).days for i in range(n-1)), default=0)
        if recent < recent_min:
            tier, status = 0, "제외(거래끊김)"
        elif n >= hist_min:
            tier, status = 1, "Tier1(안정)"
        else:
            tier, status = 2, "Tier2(신규·활성)"
        rows.append({
            "part": part, "n_days": n, "coverage_pct": round(n / full_span * 100),
            "recent_days": recent, "max_gap": max_gap,
            "start": pd.Timestamp(ds[0]).date().isoformat(),
            "tier": tier, "status": status,
        })
    return pd.DataFrame(rows).sort_values(["tier", "n_days"], ascending=[True, False])


def select_universe(mb: pd.DataFrame, **kw) -> list[str]:
    """모델 대상(활성) 품목 리스트 = Tier1 + Tier2."""
    u = classify_universe(mb, **kw)
    return u[u["tier"] > 0]["part"].tolist()


def main():
    ensure_dirs()
    mb = pd.read_csv(DASHBOARD_READY_CSV)
    u = classify_universe(mb)
    out = DATA_DASHBOARD / "meatbox_universe.csv"
    u.to_csv(out, index=False, encoding="utf-8-sig")
    n1 = (u["tier"] == 1).sum(); n2 = (u["tier"] == 2).sum(); n0 = (u["tier"] == 0).sum()
    print(f"[완료] universe 저장: {out}")
    print(f"  Tier1(안정) {n1} / Tier2(신규·활성) {n2} / 제외 {n0}  → 모델대상 {n1+n2}종")
    print(u.to_string(index=False))


if __name__ == "__main__":
    main()
