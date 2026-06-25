"""
[파일 정의서]
- 파일명: build_switch_signal.py
- 역할: 분석 (품목 전환 — 상대가치 매도/매수 시그널)
- 대상: 미트박스 수입육 부위 전체
- 데이터 소스: data/2_dashboard/dashboard_ready_data.csv
- 출력: data/2_dashboard/switch_signal.csv
- 로직: 각 부위의 현재가(최근3주 평균)를 자기 이력 분포의 백분위로 평가.
        백분위 높음=고평가(매도 후보), 낮음=저평가(매수 후보). 평균회귀 관점.
- 비고: 삼겹양지 매도 가정 시, 저평가 부위로 전환하는 후보를 제시.
        용도 대체성은 별도 고려 필요(단순 상대가치 스크린).
"""
import sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DASHBOARD_READY_CSV, DATA_DASHBOARD, ensure_dirs

def main():
    ensure_dirs()
    mb = pd.read_csv(DASHBOARD_READY_CSV)
    mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
    mb = mb.dropna(subset=["date","wholesale_price","part"])
    daily = mb.groupby(["part","date"])["wholesale_price"].mean().reset_index()
    latest = daily["date"].max()
    rows=[]
    for part,g in daily.groupby("part"):
        g=g.sort_values("date")
        if len(g)<60: continue
        cur = g[g["date"]>=latest-pd.Timedelta(days=21)]["wholesale_price"].mean()
        if np.isnan(cur): continue
        pct = (g["wholesale_price"]<cur).mean()*100
        m30 = g[g["date"]>=latest-pd.Timedelta(days=30)]["wholesale_price"].mean()
        m60 = g[(g["date"]<latest-pd.Timedelta(days=30))&(g["date"]>=latest-pd.Timedelta(days=60))]["wholesale_price"].mean()
        mom = (m30/m60-1)*100 if (m60 and not np.isnan(m60)) else np.nan
        sig = "매도후보(고평가)" if pct>=75 else ("매수후보(저평가)" if pct<=35 else "중립")
        rows.append({"part":part,"current_price":int(round(cur)),"pct_rank":int(round(pct)),
                     "momentum_30d": (round(mom,1) if not np.isnan(mom) else None),
                     "signal":sig,"n_obs":len(g)})
    out=pd.DataFrame(rows).sort_values("pct_rank",ascending=False)
    out.to_csv(DATA_DASHBOARD/"switch_signal.csv", index=False, encoding="utf-8-sig")
    print(f"[완료] 전환 시그널: switch_signal.csv ({len(out)}개 부위, 기준일 {latest.date()})")
    print(out.to_string(index=False))

if __name__=="__main__":
    main()
