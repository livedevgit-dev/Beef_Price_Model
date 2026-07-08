# [파일 정의서]
# - 파일명: src/reports/generate_letter.py
# - 역할: 산출물 생성 (온라인우편 복붙용 — 수입육 시장 트렌드 월간 종합 레터)
# - 대상: 수입육(미국·호주산 소고기) 시장 전반
# - 데이터 소스:
#     · 시세  : dashboard_ready_data.csv (미트박스 B2B 도매시세, 부위별)
#     · 수입량: master_import_volume.csv (국가·부위별 월간, KMTA/식약처)
#     · 재고  : beef_stock_data.xlsx     (부위별 월간 조사재고량, KMTA)
# - 목적: 월 1회, "전월 기준 수입 시장 트렌드 전반"을 한 장으로 정리.
#         온라인 우편은 실제 표(엑셀/HTML 표) 붙여넣기가 안 되므로
#         고정폭(monospace) '텍스트 표'로 구성 → 워드/메모장에 붙여도 칸이 유지됨.
# - 구성:
#     0) 총평           — 시세·수입량·재고 방향을 묶은 한 문단 + 대표부위(삼겹양지)
#     1) 시세 트렌드     — 부위별 오른/내린 Top N (텍스트 표)
#     2) 수입량 — 국가별 — 미국/호주/계 당월·전월·증감 (텍스트 표)
#     3) 수입량 — 부위별 — 전체 부위 증감 (텍스트 표)
#     4) 재고 트렌드     — 부위별 증감 Top N (텍스트 표)
# - 실행 예)
#     python src/reports/generate_letter.py
#     python src/reports/generate_letter.py --month 2026-06
#     python src/reports/generate_letter.py --out D:/letter.txt

import argparse
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    DASHBOARD_READY_CSV,
    MASTER_IMPORT_VOLUME_CSV,
    BEEF_STOCK_XLSX,
    DATA_REPORTS,
    ensure_dirs,
)

FLAGSHIP_PART = "삼겹양지"    # 대표 부위(수입육 벤치마크)
PRICE_TOP_N = 8               # 시세 오른/내린 각 표기 개수
STOCK_TOP_N = 5               # 재고 증가/감소 각 표기 개수
FLAT_THRESHOLD = 0.5          # 총평 방향 판정 임계치(%)
EXCLUDED_PARTS = {"합계", "기타", "부산물", "계"}
COL_GAP = "  "


# ==================================================================
# 고정폭 텍스트 표 유틸 (한글 2칸 폭 — 온라인우편/워드 고정폭 글꼴에서 칸 맞춤)
# ==================================================================
def _char_width(ch: str) -> int:
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _disp_width(text) -> int:
    return sum(_char_width(c) for c in str(text))


def _pad(text, width: int, align: str = "left") -> str:
    text = str(text)
    gap = width - _disp_width(text)
    if gap <= 0:
        return text
    return text + " " * gap if align == "left" else " " * gap + text


def render_table(headers, rows, aligns) -> str:
    """헤더 + 구분선 + 데이터 행을 고정폭 텍스트 표로."""
    if not rows:
        return "   (집계 가능한 데이터가 없습니다.)"
    widths = [_disp_width(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _disp_width(cell))

    def fmt_row(cells):
        return COL_GAP.join(_pad(c, widths[i], aligns[i]) for i, c in enumerate(cells))

    line_len = sum(widths) + len(COL_GAP) * (len(widths) - 1)
    out = [fmt_row(headers), "-" * line_len]
    out.extend(fmt_row(r) for r in rows)
    return "\n".join(out)


def _fmt_num(v, decimals: int = 0) -> str:
    return f"{v:,.{decimals}f}"


def _fmt_pct(v) -> str:
    return f"{v:+.1f}%"


def _period_kr(p) -> str:
    return f"{p.year}년 {p.month}월" if p is not None else "-"


def _direction_word(pct) -> str:
    if pct > FLAT_THRESHOLD:
        return "상승"
    if pct < -FLAT_THRESHOLD:
        return "하락"
    return "보합"


# ==================================================================
# 기준월 선정
# ==================================================================
def _pick_months(periods, anchor=None, today_period=None):
    periods = sorted(set(periods))
    if anchor is not None:
        eligible = [p for p in periods if p <= anchor]
    elif today_period is not None:
        eligible = [p for p in periods if p < today_period]
    else:
        eligible = periods
    if len(eligible) < 2:
        return None, None
    return eligible[-1], eligible[-2]


def _pct_frame(cur_series, prev_series):
    """당월/전월 Series → cur/prev/pct DataFrame (전월 0 제외)."""
    merged = pd.concat([cur_series.rename("cur"), prev_series.rename("prev")], axis=1).dropna()
    merged = merged[merged["prev"] != 0]
    if not merged.empty:
        merged["pct"] = (merged["cur"] - merged["prev"]) / merged["prev"] * 100
    return merged


# ==================================================================
# 1) 시세 트렌드 (부위별 월평균 도매가)
# ==================================================================
def build_price_trend(anchor=None, today_period=None):
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(str(DASHBOARD_READY_CSV))
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "part", "wholesale_price"])
    df = df[df["wholesale_price"] > 0]
    df["month"] = df["date"].dt.to_period("M")

    cur, prev = _pick_months(df["month"].unique(), anchor=anchor, today_period=today_period)
    if cur is None:
        return None

    cur_avg = df[df["month"] == cur].groupby("part")["wholesale_price"].mean()
    prev_avg = df[df["month"] == prev].groupby("part")["wholesale_price"].mean()
    merged = _pct_frame(cur_avg, prev_avg)
    if merged.empty:
        return {"cur": cur, "prev": prev, "empty": True}

    up = merged[merged["pct"] > 0].sort_values("pct", ascending=False)
    down = merged[merged["pct"] < 0].sort_values("pct", ascending=True)
    flagship = None
    if FLAGSHIP_PART in merged.index:
        r = merged.loc[FLAGSHIP_PART]
        flagship = (float(r["cur"]), float(r["prev"]), float(r["pct"]))

    return {
        "cur": cur, "prev": prev, "empty": False,
        "avg_pct": float(merged["pct"].mean()),
        "n_up": int((merged["pct"] > 0).sum()),
        "n_down": int((merged["pct"] < 0).sum()),
        "n_total": int(len(merged)),
        "up": up, "down": down, "flagship": flagship,
    }


def _price_rows(sub, n):
    return [[p, _fmt_num(r["cur"]), _fmt_num(r["prev"]), _fmt_pct(r["pct"])]
            for p, r in sub.head(n).iterrows()]


# ==================================================================
# 2) 수입량 — 국가별 총수입
# ==================================================================
def _load_import():
    if not MASTER_IMPORT_VOLUME_CSV.exists():
        return None
    df = pd.read_csv(str(MASTER_IMPORT_VOLUME_CSV))
    df["month"] = pd.to_datetime(df["std_date"], errors="coerce").dt.to_period("M")
    return df


def build_import_country(df, anchor=None):
    total_col = next((c for c in df.columns if c.startswith("부위별_") and "계_합계" in c), None)
    if total_col is None or "구분" not in df.columns:
        return None
    cur, prev = _pick_months(df["month"].unique(), anchor=anchor)
    if cur is None:
        return None
    cur_v = df[df["month"] == cur].groupby("구분")[total_col].sum()
    prev_v = df[df["month"] == prev].groupby("구분")[total_col].sum()
    merged = _pct_frame(cur_v, prev_v).sort_values("cur", ascending=False)

    rows = [[k, _fmt_num(r["cur"], 1), _fmt_num(r["prev"], 1), _fmt_pct(r["pct"])]
            for k, r in merged.iterrows()]
    # 합계 행
    if not merged.empty:
        tc, tp = merged["cur"].sum(), merged["prev"].sum()
        tpct = (tc - tp) / tp * 100 if tp else 0.0
        rows.append(["계", _fmt_num(tc, 1), _fmt_num(tp, 1), _fmt_pct(tpct)])
    return {"cur": cur, "prev": prev, "rows": rows, "total_pct": (tpct if not merged.empty else None)}


def build_import_parts(df, anchor=None):
    val_cols = [c for c in df.columns if c.startswith("부위별_") and "계_합계" not in c]
    long = df.melt(id_vars=["month"], value_vars=val_cols, var_name="part_raw", value_name="vol")
    long["part"] = long["part_raw"].str.replace("부위별_", "", regex=False).str.replace("_합계", "", regex=False)
    long["vol"] = pd.to_numeric(long["vol"], errors="coerce")
    long = long[~long["part"].isin(EXCLUDED_PARTS)]

    cur, prev = _pick_months(long["month"].unique(), anchor=anchor)
    if cur is None:
        return None
    cur_v = long[long["month"] == cur].groupby("part")["vol"].sum()
    prev_v = long[long["month"] == prev].groupby("part")["vol"].sum()
    merged = _pct_frame(cur_v, prev_v).sort_values("pct", ascending=False)
    rows = [[p, _fmt_num(r["cur"], 1), _fmt_num(r["prev"], 1), _fmt_pct(r["pct"])]
            for p, r in merged.iterrows()]
    return {"cur": cur, "prev": prev, "rows": rows}


# ==================================================================
# 4) 재고 트렌드 (부위별 조사재고량)
# ==================================================================
def build_stock(anchor=None):
    if not BEEF_STOCK_XLSX.exists():
        return None
    df = pd.read_excel(str(BEEF_STOCK_XLSX))
    col_map = {}
    for col in df.columns:
        if "기준년월" in col:
            col_map[col] = "date"
        elif "부위별" in col:
            col_map[col] = "part"
        elif "조사재고량" in col:
            col_map[col] = "inventory"
    df = df.rename(columns=col_map)
    if not {"date", "part", "inventory"} <= set(df.columns):
        return None

    df = df[~df["inventory"].astype(str).str.contains("없습니다|자료가", na=False)]
    df["inventory"] = pd.to_numeric(df["inventory"].astype(str).str.replace(",", ""), errors="coerce")
    df = df.dropna(subset=["inventory"])
    df["month"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
    df = df[~df["part"].isin(EXCLUDED_PARTS)]

    cur, prev = _pick_months(df["month"].dropna().unique(), anchor=anchor)
    if cur is None:
        return None
    cur_v = df[df["month"] == cur].groupby("part")["inventory"].sum()
    prev_v = df[df["month"] == prev].groupby("part")["inventory"].sum()
    merged = _pct_frame(cur_v, prev_v)
    inc = merged[merged["pct"] > 0].sort_values("pct", ascending=False).head(STOCK_TOP_N)
    dec = merged[merged["pct"] < 0].sort_values("pct", ascending=True).head(STOCK_TOP_N)

    def rows(sub):
        return [[p, _fmt_num(r["cur"]), _fmt_num(r["prev"]), _fmt_pct(r["pct"])]
                for p, r in sub.iterrows()]

    return {"cur": cur, "prev": prev, "inc": rows(inc), "dec": rows(dec)}


# ==================================================================
# 본문 조립
# ==================================================================
def generate_letter(anchor=None) -> str:
    today_period = pd.Period(datetime.now(), "M")
    trend = build_price_trend(anchor=anchor, today_period=today_period)
    imp_df = _load_import()
    imp_country = build_import_country(imp_df, anchor=anchor) if imp_df is not None else None
    imp_parts = build_import_parts(imp_df, anchor=anchor) if imp_df is not None else None
    stock = build_stock(anchor=anchor)

    divider = "=" * 60
    sub = "-" * 60
    L = [divider]

    cur = trend["cur"] if trend and not trend.get("empty") else None
    L.append(f"■ 수입육 시장 동향 월간 리포트{' — ' + _period_kr(cur) + ' 기준' if cur else ''}")
    L.append(f"  생성일시: {datetime.now():%Y-%m-%d %H:%M}")
    L.append(divider)

    # 0) 총평
    L.append("")
    L.append("[총평]")
    if trend and not trend.get("empty"):
        price_dir = _direction_word(trend["avg_pct"])
        line = (f"· 도매 시세: {_period_kr(trend['cur'])}은 전월({_period_kr(trend['prev'])}) 대비 "
                f"전반적으로 '{price_dir}' (부위 평균 {_fmt_pct(trend['avg_pct'])}, "
                f"오른 {trend['n_up']}·내린 {trend['n_down']} / {trend['n_total']}개 부위)")
        L.append(line)
        if trend["flagship"]:
            cv, pv, pc = trend["flagship"]
            L.append(f"· 대표부위 삼겹양지: {cv:,.0f}원/kg (전월 {pv:,.0f} → {_fmt_pct(pc)})")
    else:
        L.append("· 도매 시세: 집계 가능한 데이터가 부족합니다.")
    if imp_country and imp_country.get("total_pct") is not None:
        L.append(f"· 수입 물량: {_period_kr(imp_country['cur'])} 전월 대비 "
                 f"{_fmt_pct(imp_country['total_pct'])} (미국·호주 합산)")
    if stock:
        L.append(f"· 재고: {_period_kr(stock['cur'])} 기준 (증가 {len(stock['inc'])}·감소 {len(stock['dec'])} 부위)")

    # 1) 시세 트렌드
    L.append("")
    L.append("[1] 도매 시세 트렌드 — 부위별 (원/kg, 미트박스 B2B)")
    if trend and not trend.get("empty"):
        L.append(f"  기준: {_period_kr(trend['cur'])} vs {_period_kr(trend['prev'])} (월평균)")
        L.append("")
        L.append(f" ▲ 오른 부위 Top {PRICE_TOP_N}")
        L.append(render_table(["부위", "당월", "전월", "증감률"],
                              _price_rows(trend["up"], PRICE_TOP_N),
                              ["left", "right", "right", "right"]))
        L.append("")
        L.append(f" ▼ 내린 부위 Top {PRICE_TOP_N}")
        L.append(render_table(["부위", "당월", "전월", "증감률"],
                              _price_rows(trend["down"], PRICE_TOP_N),
                              ["left", "right", "right", "right"]))
    else:
        L.append("  (집계 가능한 데이터가 없습니다.)")

    # 2) 수입량 국가별
    L.append("")
    L.append("[2] 수입 물량 — 국가별 (톤)")
    if imp_country:
        L.append(f"  기준: {_period_kr(imp_country['cur'])} vs {_period_kr(imp_country['prev'])}")
        L.append(render_table(["국가", "당월", "전월", "증감률"],
                              imp_country["rows"], ["left", "right", "right", "right"]))
    else:
        L.append("  (집계 가능한 데이터가 없습니다.)")

    # 3) 수입량 부위별
    L.append("")
    L.append("[3] 수입 물량 — 부위별 (톤, 국가 합산)")
    if imp_parts:
        L.append(f"  기준: {_period_kr(imp_parts['cur'])} vs {_period_kr(imp_parts['prev'])}")
        L.append(render_table(["부위", "당월", "전월", "증감률"],
                              imp_parts["rows"], ["left", "right", "right", "right"]))
    else:
        L.append("  (집계 가능한 데이터가 없습니다.)")

    # 4) 재고
    L.append("")
    L.append("[4] 재고 트렌드 — 부위별 (톤)")
    if stock:
        L.append(f"  기준: {_period_kr(stock['cur'])} vs {_period_kr(stock['prev'])}")
        L.append("")
        L.append(f" ▲ 증가 Top {STOCK_TOP_N}")
        L.append(render_table(["부위", "당월", "전월", "증감률"], stock["inc"],
                              ["left", "right", "right", "right"]))
        L.append("")
        L.append(f" ▼ 감소 Top {STOCK_TOP_N}")
        L.append(render_table(["부위", "당월", "전월", "증감률"], stock["dec"],
                              ["left", "right", "right", "right"]))
    else:
        L.append("  (집계 가능한 데이터가 없습니다.)")

    # 꼬리말
    L.append("")
    L.append(divider)
    L.append("※ 출처: 시세-미트박스 B2B 도매시세 / 수입량-KMTA·식약처 / 재고-KMTA")
    L.append("※ 증감률(%) = (당월값 - 전월값) / 전월값 × 100")
    L.append("※ 데이터 공개 시차로 표마다 기준월이 다를 수 있습니다.")
    L.append("※ 고정폭 글꼴(나눔고딕코딩·D2Coding·Consolas 등)에서 칸이 맞습니다.")
    L.append(divider)
    return "\n".join(L)


# ==================================================================
# CLI
# ==================================================================
def main():
    parser = argparse.ArgumentParser(description="온라인우편 복붙용 수입육 시장 월간 종합 레터 생성")
    parser.add_argument("--month", default=None,
                        help="기준월(YYYY-MM). 미지정 시 최신 완료월(전월)을 자동 사용.")
    parser.add_argument("--out", default=None,
                        help="출력 파일 경로. 미지정 시 data/3_reports/letter_<기준월>.txt")
    args = parser.parse_args()

    anchor = None
    if args.month:
        try:
            anchor = pd.Period(args.month, "M")
        except Exception:
            print(f"[오류] --month 형식이 올바르지 않습니다(YYYY-MM): {args.month}")
            sys.exit(1)

    letter = generate_letter(anchor=anchor)

    ensure_dirs()
    if args.out:
        out_path = Path(args.out)
    else:
        today_period = pd.Period(datetime.now(), "M")
        trend = build_price_trend(anchor=anchor, today_period=today_period)
        if trend and trend.get("cur") is not None:
            stamp = str(trend["cur"])
        else:
            stamp = str(anchor) if anchor is not None else datetime.now().strftime("%Y-%m")
        out_path = DATA_REPORTS / f"letter_{stamp}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(letter, encoding="utf-8")

    print(letter)
    print(f"\n[저장 완료] {out_path}")


if __name__ == "__main__":
    main()
