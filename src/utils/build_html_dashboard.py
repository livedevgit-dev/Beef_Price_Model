"""
[파일 정의서]
- 파일명: build_html_dashboard.py
- 역할: 시각화 (Streamlit 서버 없이 더블클릭으로 여는 단일 HTML 대시보드)
- 데이터 소스: data/2_dashboard/*.csv, data/1_processed/samgyup_unified_monthly.csv, usda_plate_usd_kg.csv,
               data/0_raw/exchange_rate_data.xlsx, master_import_volume.csv, beef_stock_data.xlsx,
               macro_indicators_raw.csv, data/3_reports/market_report_latest.txt
- 산출물: dashboard/beef_dashboard.html (plotly.js 내장 — 인터넷 없이도 열림, git 추적 제외)
- 주요 기능: 현황판·리포트·시그널 / 수입육 시세 / 삼겹양지 예측 / 수입·재고 / USDA·환율 / 한우 / 거시 / FAS
             탭을 한 파일에 담는다. 섹션별 데이터 로드 실패는 해당 탭만 비우고 계속한다.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (PROJECT_ROOT, DATA_DASHBOARD, DATA_PROCESSED, DATA_REPORTS, DASHBOARD_READY_CSV,
                    EXCHANGE_RATE_XLSX, USDA_PLATE_USD_KG_CSV, MASTER_IMPORT_VOLUME_CSV, BEEF_STOCK_XLSX,
                    HANWOO_DASHBOARD_CSV, MACRO_RAW_CSV, FAS_SIGNAL_CSV)

OUT_DIR = PROJECT_ROOT / "dashboard"
OUT_FILE = OUT_DIR / "beef_dashboard.html"

FEATURE_LABELS = {
    "usda_plate": "USDA 플레이트 원가", "fx": "환율(USD/KRW)", "import_yj": "양지 수입량", "stock_yj": "양지 재고",
    "fas_china": "미국→중국 수출", "fas_korea": "미국→한국 수출", "cof_inventory": "미국 비육우 사육두수",
    "cof_placements": "미국 비육장 입식두수", "us_soybean_meal": "대두박 가격", "kr_ppi_food": "PPI 음식료품",
    "kr_cpi_food": "CPI 식료품", "us_wti": "WTI 유가", "kr_base_rate": "기준금리", "kr_temp_avg": "평균기온",
    "kr_precip": "강수량",
}


def _xy(s: pd.Series, digits=1, keep_gaps=False):
    """인덱스(날짜)·값 Series → {"x": [...], "y": [...]}.
    keep_gaps=True 면 앞뒤 결측만 자르고 중간 결측은 null 로 남겨 차트에서 선이 끊기게 한다(공백 구간 보간 방지)."""
    if keep_gaps:
        valid = s.dropna()
        s = s.loc[valid.index.min():valid.index.max()] if len(valid) else valid
    else:
        s = s.dropna()
    return {"x": [pd.Timestamp(i).strftime("%Y-%m-%d") for i in s.index],
            "y": [None if pd.isna(v) else round(float(v), digits) for v in s.values]}


def _clean(o):
    """JSON 직렬화용: NaN/inf → None."""
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def _records(df):
    return json.loads(df.to_json(orient="records", force_ascii=False))


# ------------------------------------------------------------------ 섹션별 빌더
def build_status():
    df = pd.read_csv(DATA_DASHBOARD / "data_status.csv")
    return _records(df)


def build_report():
    p = DATA_REPORTS / "market_report_latest.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def build_switch():
    return _records(pd.read_csv(DATA_DASHBOARD / "switch_signal.csv"))


def build_meatbox():
    d = pd.read_csv(DASHBOARD_READY_CSV, parse_dates=["date"])
    if "is_filled" in d.columns:   # 직전 값으로 채운 날 제외 — 실제 관측 브랜드만 평균
        d = d[~d["is_filled"].astype(str).str.lower().eq("true")]
    uni = pd.read_csv(DATA_DASHBOARD / "meatbox_universe.csv").set_index("part")["status"].to_dict()
    series, summary = {}, []
    for (part, cat), g in d.groupby(["part", "category"]):
        pv = g.pivot_table(index="date", columns="brand", values="wholesale_price", aggfunc="mean").sort_index()
        # 일별 평균은 브랜드 구성에 민감 → 평소(최근 60관측일 중앙값) 브랜드 수의 절반 미만만 잡힌 날은 제외
        n_brand = pv.notna().sum(axis=1)
        typical = n_brand.rolling(60, min_periods=1).median()
        s = pv.mean(axis=1)[n_brand >= (typical * 0.5).clip(lower=1)]
        if s.empty:
            continue
        series.setdefault(part, {})[cat] = _xy(s, 0)
        last_date, last = s.index[-1], s.iloc[-1]

        def chg(days):
            # 같은 브랜드끼리 비교한 변동률의 중앙값 (부분 수집일·브랜드 교체로 인한 평균 착시 방지)
            # 비교 시점 직전 14일 안의 브랜드별 마지막 관측만 사용 (몇 달 만에 재등장한 브랜드의 옛 가격과 비교 방지)
            cut = last_date - pd.Timedelta(days=days)
            win = pv[(pv.index <= cut) & (pv.index > cut - pd.Timedelta(days=14))]
            if win.empty:
                return None
            r = (pv.loc[last_date] / win.ffill().iloc[-1] - 1).dropna()
            return round(float(r.median()) * 100, 1) if len(r) else None
        summary.append({"part": part, "country": cat, "date": last_date.strftime("%Y-%m-%d"),
                        "price": round(float(last)), "chg7": chg(7), "chg30": chg(30),
                        "status": uni.get(part, "-")})
    parts = sorted(series, key=lambda p: (str(uni.get(p, "")).startswith("제외"), p))
    return {"parts": [{"name": p, "status": uni.get(p, "-")} for p in parts],
            "series": series, "summary": summary}


def build_samgyup():
    f = pd.read_csv(DATA_DASHBOARD / "samgyup_forecast.csv", parse_dates=["date"]).set_index("date")
    act, fc = f[f["type"] == "actual"], f[f["type"] == "forecast"]
    # 예측선은 마지막 실적에서 이어지도록 시작점 포함
    bridge = pd.concat([act.tail(1), fc])
    imp = pd.read_csv(DATA_DASHBOARD / "samgyup_feature_importance.csv")
    imp["label"] = imp["feature"].map(FEATURE_LABELS).fillna(imp["feature"])
    return {"actual": _xy(act["base"].resample("MS").mean(), 0, keep_gaps=True),
            "forecast": {**_xy(bridge["base"], 0),
                         "low": [None if pd.isna(v) else round(v) for v in bridge["low"]],
                         "high": [None if pd.isna(v) else round(v) for v in bridge["high"]]},
            "importance": _records(imp[["label", "std_coef"]])}


def build_usda_fx():
    u = pd.read_csv(USDA_PLATE_USD_KG_CSV, parse_dates=["report_date"])
    u = u[u["primal_desc"].astype(str).str.contains("Plate", case=False, na=False)]
    plate = u.groupby("report_date")["choice_usd_per_kg"].mean()
    ex = pd.read_excel(EXCHANGE_RATE_XLSX)
    fx = pd.Series(pd.to_numeric(ex["Close"], errors="coerce").values,
                   index=pd.to_datetime(ex["Date"], errors="coerce")).dropna()
    # 원천은 2005년부터 있으나(2026-11 백필) 일별 차트는 다른 탭과 같은 2019~ 창만 그린다
    plate, fx = plate[plate.index >= "2019-01-01"], fx[fx.index >= "2019-01-01"]
    return {"plate": _xy(plate, 3), "fx": _xy(fx, 1)}


def build_import_stock():
    imp = pd.read_csv(MASTER_IMPORT_VOLUME_CSV)
    imp["m"] = pd.to_datetime(imp["std_date"].astype(str) + "-01", errors="coerce")
    cols = [c for c in imp.columns if c.startswith("부위별_") and c.endswith("_합계")]
    order = ["계"] + [c.split("_")[1] for c in cols if c.split("_")[1] != "계"]
    imports = {}
    for c in cols:
        part = c.split("_")[1]
        for ctry, g in imp.groupby("구분"):
            imports.setdefault(part, {})[ctry] = _xy(g.groupby("m")[c].sum(), 1)
    stk = pd.read_excel(BEEF_STOCK_XLSX)
    stk["m"] = pd.to_datetime(stk["기준년월"].astype(str) + "-01", errors="coerce")
    stock = {str(p): _xy(g.groupby("m")["조사재고량 조사재고량"].sum(min_count=1), 0, keep_gaps=True)
             for p, g in stk.groupby("부위별 부위별")}
    stock_order = ["합계"] + sorted(p for p in stock if p != "합계")
    return {"import_parts": order, "imports": imports, "stock_parts": stock_order, "stock": stock}


def build_hanwoo():
    h = pd.read_csv(HANWOO_DASHBOARD_CSV, low_memory=False, parse_dates=["date"])
    h["is_national_total"] = h["is_national_total"].astype(str).str.lower().eq("true")
    nat = h[(h["source"] == "ekape_auction") & h["is_national_total"]]
    auction = {}
    for g in ["1++", "1+", "1"]:
        # 월평균은 두수 가중 (2026년부터 일별 행, 그 이전은 30일 합산 행이 섞여 단순평균이면 왜곡)
        x = nat[nat["grade"] == g].dropna(subset=["price_won_per_kg"]).set_index("date")
        w = pd.to_numeric(x["head_count"], errors="coerce").fillna(0)
        amt = (x["price_won_per_kg"] * w).resample("MS").sum()
        heads = w.resample("MS").sum()
        auction[g] = _xy((amt / heads.where(heads > 0)), 0, keep_gaps=True)
    latest = {}
    for g in ["1++", "1+", "1"]:
        s = nat[nat["grade"] == g].dropna(subset=["price_won_per_kg"]).sort_values("date")
        if len(s):
            latest[g] = {"date": s["date"].iloc[-1].strftime("%Y-%m-%d"), "price": float(s["price_won_per_kg"].iloc[-1])}
    # KAMIS: 축산물은 도매(02) 요청에도 소매값이 와서 2026-10-30부터 소매만 수집 — 소매 단일 선
    kamis = {}
    k = h[h["source"] == "kamis_retail"]
    if "is_outlier" in k.columns:
        k = k[~k["is_outlier"].astype(str).str.lower().eq("true")]
    for (part, grade), g in k.groupby(["part", "grade"]):
        s = g.groupby("date")["price_won_per_kg"].mean().resample("W-MON").mean()
        kamis.setdefault(part, {}).setdefault(str(grade), {})["소매"] = _xy(s, 0, keep_gaps=True)
    return {"auction": auction, "auction_latest": latest, "kamis": kamis,
            "kamis_parts": sorted(kamis), "kamis_grades": ["1++", "1+", "1"]}


def build_macro():
    r = pd.read_csv(MACRO_RAW_CSV, parse_dates=["date"])
    r["value"] = pd.to_numeric(r["value"], errors="coerce")
    # 원천은 1990/2005년부터 있으나(장기 백필) 차트는 다른 탭과 같은 2019~ 창만 그린다
    r = r[r["date"] >= "2019-01-01"]
    try:
        from utils.indicator_registry import labels as _reg_labels, groups as _reg_groups
        lab, grp = _reg_labels(), _reg_groups()
    except Exception:
        lab, grp = {}, {}
    out = []
    for iid, g in r.groupby("indicator_id"):
        s = g.groupby("date")["value"].mean().resample("MS").mean()
        meta = g.iloc[-1]
        name = str(meta["indicator_name"])
        if iid in lab and lab[iid]:
            name = f"{lab[iid]} — {name}"
        out.append({"id": iid, "name": name, "unit": str(meta["unit"]), "group": grp.get(iid, ""),
                    "country": str(meta["country"]), **_xy(s, 3, keep_gaps=True)})
    out.sort(key=lambda m: (m["country"] != "KR", m["group"], m["name"]))
    return out


def build_fas():
    f = pd.read_csv(FAS_SIGNAL_CSV, parse_dates=["date"]).set_index("date")
    # 주 4회/5회 달의 차이가 왜곡되지 않도록 월내 주평균(톤/주) 사용, 집계 중인 달은 표시만
    china = f["china_wk_avg"] if "china_wk_avg" in f else f["china_exp"]
    korea = f["korea_wk_avg"] if "korea_wk_avg" in f else f["korea_exp"]
    cols = ["date", "china_exp", "korea_exp", "china_vs_med", "korea_vs_med", "alert_level", "note"]
    if "is_partial" in f:
        cols.append("is_partial")
    return {"china": _xy(china, 0), "korea": _xy(korea, 0),
            "china_base": float(f["china_base"].dropna().iloc[-1]) if "china_base" in f else None,
            "recent": _records(f.reset_index().tail(12).assign(date=lambda x: x["date"].dt.strftime("%Y-%m"))[cols])}


def build_quota():
    """호주산 저율관세 쿼터 소진 이력 (analysis/au_safeguard_event.py 산출)."""
    return _records(pd.read_csv(DATA_REPORTS / "analysis" / "au_safeguard_history.csv"))


def build_margin():
    """KAMIS 수입 쇠고기 소매가 vs 미트박스 도매가 (Models/domestic_vs_import.py 산출)."""
    m = pd.read_csv(DATA_REPORTS / "analysis" / "import_retail_margin.csv")
    m["date"] = pd.to_datetime(m["period"].astype(str) + "-01")
    items = []
    for (kp, origin, mp), g in m.groupby(["kamis_part", "origin", "meatbox_part"], sort=False):
        g = g.set_index("date").sort_index()
        items.append({"key": f"{kp}|{origin}|{mp}", "label": f"{origin} {kp.replace('수입 ', '')} ↔ 도매 {mp}",
                      "retail": _xy(g["retail_won_kg"], 0), "wholesale": _xy(g["wholesale_won_kg"], 0),
                      "margin": _xy(g["margin_pct"], 1)})
    return {"items": items}


def build_customs():
    """관세청 통관 단가·물량(국가×부위군, preprocess_kr_customs_beef.py 산출) + 호주산 ASG 소진율."""
    from config import KR_CUSTOMS_BEEF_MONTHLY_CSV, AU_SAFEGUARD_USAGE_CSV
    m = pd.read_csv(KR_CUSTOMS_BEEF_MONTHLY_CSV, parse_dates=["date"])
    m = m[m["date"] >= "2010-01-01"]
    labels = {"frozen_boneless": "냉동 뼈없음(삼겹양지·차돌·목심 등)", "frozen_rib": "냉동 갈비(LA갈비·찜갈비)",
              "frozen_bone_in_other": "냉동 뼈있음 기타", "chilled_boneless": "냉장 뼈없음", "chilled_rib": "냉장 갈비",
              "frozen_all": "냉동 전체", "chilled_all": "냉장 전체", "all": "전체"}
    groups = [g for g in labels if g in set(m["group"])]
    uv, vol = {}, {}
    for g in groups:
        uv[g], vol[g] = {}, {}
        for c in ("US", "AU", "ALL"):
            s = m[(m["group"] == g) & (m["country"] == c)].set_index("date").sort_index()
            if s.empty:
                continue
            uv[g][c] = _xy(s["unit_value_usd_kg"].where(s["imp_kg"] > 0), 2, keep_gaps=True)
            vol[g][c] = _xy(s["imp_kg"] / 1000, 0, keep_gaps=True)
    # 미국 측 FOB 단가(GATS, 선적 기준 — 관세청 CIF 보다 약 1개월 선행)를 같은 부위군에 겹쳐 그린다
    try:
        from config import US_EXPORT_KOREA_MONTHLY_CSV
        gx = pd.read_csv(US_EXPORT_KOREA_MONTHLY_CSV, parse_dates=["date"])
        gx = gx[gx["date"] >= "2010-01-01"]
        gmap = {"frozen_boneless": "frozen_boneless", "frozen_rib": "frozen_bone_in", "frozen_bone_in_other": "frozen_bone_in",
                "chilled_boneless": "chilled_boneless", "chilled_rib": "chilled_bone_in", "all": "all_beef"}
        for g, gg in gmap.items():
            s = gx[gx["group"] == gg].set_index("date").sort_index()
            if g in uv and not s.empty:
                uv[g]["US_FOB"] = _xy(s["unit_value_usd_kg"].where(s["qty_kg"] > 0), 2, keep_gaps=True)
                vol[g]["US_FOB"] = _xy(s["qty_kg"] / 1000, 0, keep_gaps=True)
    except Exception as e:
        print(f"  [customs] GATS 겹치기 생략: {e}")
    sg = pd.read_csv(AU_SAFEGUARD_USAGE_CSV, parse_dates=["date"])
    cur_year = int(sg["year"].max())
    cur = sg[sg["year"] == cur_year].sort_values("date")
    cur_rows = [{"month": d.strftime("%Y-%m"), "month_kt": round(r.month_kg / 1e6, 1), "cum_kt": round(r.cum_kg / 1e6, 1),
                 "usage_pct": None if pd.isna(r.usage_pct) else round(float(r.usage_pct), 1),
                 "projected": "" if pd.isna(r.projected_trigger_month) else str(r.projected_trigger_month)}
                for d, r in zip(cur["date"], cur.itertuples())]
    yr = []
    for y, g in sg.groupby("year"):
        g = g.sort_values("date")
        hit = g[g["usage_pct"] >= 100]
        yr.append({"year": int(y), "quota_kt": None if pd.isna(g["quota_kg"].iloc[-1]) else round(g["quota_kg"].iloc[-1] / 1e6, 1),
                   "total_kt": round(g["cum_kg"].iloc[-1] / 1e6, 1),
                   "final_pct": None if pd.isna(g["usage_pct"].iloc[-1]) else round(float(g["usage_pct"].iloc[-1]), 1),
                   "hit_month": hit["date"].iloc[0].strftime("%Y-%m") if len(hit) else "", "status": str(g["quota_status"].iloc[-1])})
    yr = [r for r in yr if r["year"] >= 2014]
    return {"groups": [[g, labels[g]] for g in groups], "unit_value": uv, "volume_kt": vol,
            "safeguard": {"year": cur_year, "rows": cur_rows, "by_year": yr}}


def build_cost_signal():
    """원가 대비 괴리(미트박스 미국산 품목 vs USDA 부위 원가×환율) + 6개월 추세 신호.
    근거: analysis/panel_and_longrun_note.md (2026-11-09) — 월 단위 예측은 불가, 마진 괴리는 반감기 ~5개월로 되돌아오고
    미국 원가(USD)·환율의 6개월 변화는 수입육 가격 6개월 추세 방향을 ~72% 맞힘(2012~2026 OOS)."""
    from analysis import panel_cost_model as PCM
    from analysis import cost_passthrough_long as CPL
    from utils.part_mapping import NO_DIRECT_USDA_PARTS

    panel = PCM.build_panel("M")
    panel = panel[(panel["is_au"] == 0) & panel["y_chg"].notna()].copy()
    panel["part"] = panel["item"].str.split("·").str[1]
    items = []
    for item, g in panel.groupby("item", sort=False):
        g = g.sort_values("date")
        last = g.iloc[-1]
        part = last["part"]
        direct = (part not in NO_DIRECT_USDA_PARTS) and not str(last["cost_src"]).startswith("Primal")
        if len(g) < 8:
            continue
        items.append({"part": part, "cost_src": str(last["cost_src"]), "direct": bool(direct),
                      "asof": pd.Timestamp(last["date"]).strftime("%Y-%m"), "n": int(len(g)),
                      "gap_pct": round(float(np.expm1(last["gap"]) * 100), 1) if pd.notna(last["gap"]) else None,
                      "price_3m_pct": round(float(np.expm1(last["own_3"]) * 100), 1) if pd.notna(last["own_3"]) else None,
                      "cost_3m_pct": round(float(np.expm1(last["cost_3"]) * 100), 1) if pd.notna(last["cost_3"]) else None})
    items.sort(key=lambda r: (not r["direct"], r["part"]))

    # 6개월 추세 신호: ΔCPI(수입 쇠고기, t→t+6) ~ Δ6 플레이트 USD + Δ6 환율 (2005~ 전체 적합, drift 대비)
    _, D = CPL.load()
    L = np.log(CPL.load()[0])
    y6 = (L["cpi_imp"].shift(-6) - L["cpi_imp"])
    x1 = L["plate_usd"] - L["plate_usd"].shift(6)
    x2 = L["fx"] - L["fx"].shift(6)
    fit = pd.concat([y6, x1, x2], axis=1).dropna()
    A = np.column_stack([np.ones(len(fit)), fit.iloc[:, 1], fit.iloc[:, 2]])
    b, *_ = np.linalg.lstsq(A, fit.iloc[:, 0].values, rcond=None)
    drift = float(fit.iloc[:, 0].mean())
    cur = pd.concat([x1, x2], axis=1).dropna().iloc[-1]
    pred = float(b[0] + b[1] * cur.iloc[0] + b[2] * cur.iloc[1])
    signal = pred - drift
    trend = {"asof": pd.Timestamp(cur.name).strftime("%Y-%m"), "plate_usd_6m_pct": round(float(np.expm1(cur.iloc[0]) * 100), 1),
             "fx_6m_pct": round(float(np.expm1(cur.iloc[1]) * 100), 1), "pred_6m_pct": round(float(np.expm1(pred) * 100), 1),
             "drift_6m_pct": round(float(np.expm1(drift) * 100), 1), "signal_pct": round(float(signal * 100), 1),
             "direction": "상승 우세" if signal > 0.01 else ("하락 우세" if signal < -0.01 else "추세 중립"),
             "n_fit": int(len(fit))}
    return {"items": items, "trend": trend}


SECTIONS = {
    "status": build_status, "report": build_report, "switch": build_switch, "meatbox": build_meatbox,
    "samgyup": build_samgyup, "usda_fx": build_usda_fx, "import_stock": build_import_stock,
    "hanwoo": build_hanwoo, "macro": build_macro, "fas": build_fas, "margin": build_margin, "quota": build_quota,
    "cost_signal": build_cost_signal, "customs": build_customs,
}


def main():
    data = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M")}
    failed = []
    for key, fn in SECTIONS.items():
        try:
            data[key] = fn()
        except Exception as e:
            print(f"[경고] {key} 섹션 생성 실패: {e}")
            data[key] = None
            failed.append(key)
    payload = json.dumps(_clean(data), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    template = (Path(__file__).with_name("html_dashboard_template.html")).read_text(encoding="utf-8")
    html = (template.replace("/*__PLOTLY_JS__*/", get_plotlyjs())
                    .replace("/*__DATA__*/null", payload))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    size_mb = OUT_FILE.stat().st_size / 1e6
    print(f"[완료] HTML 대시보드 저장: {OUT_FILE} ({size_mb:.1f} MB)")
    if failed:
        print(f"[주의] 비어 있는 섹션: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
