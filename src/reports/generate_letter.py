# [파일 정의서]
# - 파일명: src/reports/generate_letter.py
# - 역할: 산출물 생성 (Reporting)
# - 대상: 공통 (온라인우편 레터용)
# - 데이터 소스: dashboard_ready_data.csv, beef_stock_data.xlsx, master_import_volume.csv
# - 주요 기능:
#   1. 시세: 전월 대비 평균 도매가 변동 |증감률| Top 10 (상승·하락 혼합)
#   2. 재고: 전월 대비 변동 부위 증가 Top 3 + 감소 Top 3
#   3. 수입량: 전월 대비 변동 부위 증가 Top 3 + 감소 Top 3
#   4. 위 3개 표를 고정폭(monospace) 정렬 텍스트로 묶어 .txt 파일 + 콘솔로 출력
#
# 실행 예) python src/reports/generate_letter.py
#         python src/reports/generate_letter.py --month 2026-04
#         python src/reports/generate_letter.py --out D:/letter.txt

import argparse
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (  # noqa: E402
    DASHBOARD_READY_CSV,
    BEEF_STOCK_XLSX,
    MASTER_IMPORT_VOLUME_CSV,
    DATA_REPORTS,
    ensure_dirs,
)

# 집계 대상에서 제외할 부위(집계행·기타 버킷)
EXCLUDED_PARTS = {"합계", "기타", "부산물"}

# 컬럼 사이 간격
COL_GAP = "  "


# ==================================================================
# 1. 고정폭 텍스트 정렬 유틸 (한글 2칸 폭 고려)
# ==================================================================
def _char_width(ch: str) -> int:
    """동아시아 전각 문자는 2칸, 그 외는 1칸으로 계산."""
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
    """헤더 + 구분선 + 데이터 행을 고정폭 표 문자열로 반환."""
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


def _period_label(p) -> str:
    return str(p) if p is not None else "-"


# ==================================================================
# 2. 기준월 선정
# ==================================================================
def _pick_months(periods, anchor=None, drop_current=False, today_period=None):
    """
    당월/전월 Period를 반환.
    - anchor 지정 시: anchor 이하의 최신 월을 당월로 사용.
    - anchor 미지정 + drop_current: 실행 시점의 현재 달(부분월)을 제외하고 최신 월 사용.
    - 전월: 데이터상 당월 직전에 존재하는 월(달력상 연속이 아니어도 직전 데이터).
    """
    periods = sorted(set(periods))
    if anchor is not None:
        eligible = [p for p in periods if p <= anchor]
    elif drop_current and today_period is not None:
        eligible = [p for p in periods if p < today_period]
    else:
        eligible = periods

    if len(eligible) < 2:
        return None, None
    return eligible[-1], eligible[-2]


# ==================================================================
# 3. 표 데이터 빌더
# ==================================================================
def build_price_top10(anchor=None, today_period=None):
    """시세: 전월 대비 평균 도매가 |증감률| 상위 10건 (상승·하락 혼합)."""
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(str(DASHBOARD_READY_CSV))
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")

    cur, prev = _pick_months(
        df["month"].unique(),
        anchor=anchor,
        drop_current=(anchor is None),
        today_period=today_period,
    )
    if cur is None:
        return None

    keys = ["part", "category", "brand"]
    cur_avg = df[df["month"] == cur].groupby(keys)["wholesale_price"].mean()
    prev_avg = df[df["month"] == prev].groupby(keys)["wholesale_price"].mean()
    merged = pd.concat([cur_avg.rename("cur"), prev_avg.rename("prev")], axis=1).dropna()
    merged = merged[merged["prev"] != 0]
    if merged.empty:
        return {"cur": cur, "prev": prev, "rows": []}

    merged["pct"] = (merged["cur"] - merged["prev"]) / merged["prev"] * 100
    top = merged.reindex(merged["pct"].abs().sort_values(ascending=False).index).head(10)

    rows = []
    for (part, category, brand), r in top.iterrows():
        label = f"{part} ({category}/{brand})"
        rows.append([label, _fmt_num(r["cur"]), _fmt_num(r["prev"]), _fmt_pct(r["pct"])])
    return {"cur": cur, "prev": prev, "rows": rows}


def _monthly_part_series(df_cur, df_prev, value_col):
    """당월/전월 부위별 합계 → 증감률 DataFrame."""
    cur_v = df_cur.groupby("part")[value_col].sum()
    prev_v = df_prev.groupby("part")[value_col].sum()
    merged = pd.concat([cur_v.rename("cur"), prev_v.rename("prev")], axis=1).dropna()
    merged = merged[merged["prev"] != 0]
    if merged.empty:
        return merged
    merged["pct"] = (merged["cur"] - merged["prev"]) / merged["prev"] * 100
    return merged


def _split_inc_dec(merged, decimals):
    """증가 Top3 / 감소 Top3 행 리스트로 변환."""
    inc = merged[merged["pct"] > 0].sort_values("pct", ascending=False).head(3)
    dec = merged[merged["pct"] < 0].sort_values("pct", ascending=True).head(3)

    def to_rows(sub):
        return [
            [part, _fmt_num(r["cur"], decimals), _fmt_num(r["prev"], decimals), _fmt_pct(r["pct"])]
            for part, r in sub.iterrows()
        ]

    return to_rows(inc), to_rows(dec)


def build_stock_top3(anchor=None):
    """재고: 전월 대비 부위별 증가 Top3 / 감소 Top3 (단위 톤)."""
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

    df = df[~df["inventory"].astype(str).str.contains("없습니다|자료가", na=False)]
    df["inventory"] = df["inventory"].astype(str).str.replace(",", "").astype(float)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    df = df[~df["part"].isin(EXCLUDED_PARTS)]

    cur, prev = _pick_months(df["month"].unique(), anchor=anchor)
    if cur is None:
        return None

    merged = _monthly_part_series(df[df["month"] == cur], df[df["month"] == prev], "inventory")
    inc_rows, dec_rows = _split_inc_dec(merged, decimals=0)
    return {"cur": cur, "prev": prev, "inc": inc_rows, "dec": dec_rows}


def build_import_top3(anchor=None):
    """수입량: 전월 대비 부위별(국가 합산) 증가 Top3 / 감소 Top3 (단위 톤)."""
    if not MASTER_IMPORT_VOLUME_CSV.exists():
        return None
    df = pd.read_csv(str(MASTER_IMPORT_VOLUME_CSV))
    df["month"] = pd.to_datetime(df["std_date"]).dt.to_period("M")

    val_cols = [c for c in df.columns if c.startswith("부위별_") and "계_합계" not in c]
    long = df.melt(id_vars=["month"], value_vars=val_cols, var_name="part_raw", value_name="vol")
    long["part"] = long["part_raw"].str.replace("부위별_", "").str.replace("_합계", "")
    long["vol"] = pd.to_numeric(long["vol"], errors="coerce")
    long = long[~long["part"].isin(EXCLUDED_PARTS)]

    cur, prev = _pick_months(long["month"].unique(), anchor=anchor)
    if cur is None:
        return None

    merged = _monthly_part_series(long[long["month"] == cur], long[long["month"] == prev], "vol")
    inc_rows, dec_rows = _split_inc_dec(merged, decimals=1)
    return {"cur": cur, "prev": prev, "inc": inc_rows, "dec": dec_rows}


# ==================================================================
# 4. 레터 본문 조립
# ==================================================================
def _section_price(price) -> str:
    lines = ["1. 시세 — 전월 대비 평균 도매가 변동 Top 10"]
    if not price or not price["rows"]:
        lines.append("   (집계 가능한 데이터가 없습니다.)")
        return "\n".join(lines)
    lines.append(
        f"   (기준: {_period_label(price['cur'])} vs {_period_label(price['prev'])}"
        f" · 단위: 원/kg · 미트박스 B2B 도매시세 · 당월·전월 일평균 비교)"
    )
    lines.append("")
    lines.append(
        render_table(
            ["품목 (부위/원산지/브랜드)", "당월", "전월", "증감률"],
            price["rows"],
            ["left", "right", "right", "right"],
        )
    )
    return "\n".join(lines)


def _section_inc_dec(title, caption, block) -> str:
    lines = [title]
    if not block or (not block["inc"] and not block["dec"]):
        lines.append("   (집계 가능한 데이터가 없습니다.)")
        return "\n".join(lines)
    lines.append(
        f"   (기준: {_period_label(block['cur'])} vs {_period_label(block['prev'])} · {caption})"
    )
    headers = ["부위", "당월", "전월", "증감률"]
    aligns = ["left", "right", "right", "right"]

    lines.append("")
    lines.append("   [▲ 증가 Top 3]")
    if block["inc"]:
        lines.append(render_table(headers, block["inc"], aligns))
    else:
        lines.append("   (증가 항목 없음)")

    lines.append("")
    lines.append("   [▼ 감소 Top 3]")
    if block["dec"]:
        lines.append(render_table(headers, block["dec"], aligns))
    else:
        lines.append("   (감소 항목 없음)")
    return "\n".join(lines)


def generate_letter(anchor=None) -> str:
    today_period = pd.Period(datetime.now(), "M")
    price = build_price_top10(anchor=anchor, today_period=today_period)
    stock = build_stock_top3(anchor=anchor)
    imp = build_import_top3(anchor=anchor)

    divider = "=" * 64
    parts = [
        divider,
        "■ 소고기 시세·재고·수입 동향 (전월 대비 변동 요약)",
        f"  생성일시: {datetime.now():%Y-%m-%d %H:%M}",
        divider,
        "",
        "전월 대비 변동폭이 큰 항목을 아래와 같이 정리해 드립니다.",
        "",
        _section_price(price),
        "",
        _section_inc_dec(
            "2. 재고 — 전월 대비 변동 부위 (증가·감소 Top 3)",
            "단위: 톤",
            stock,
        ),
        "",
        _section_inc_dec(
            "3. 수입량 — 전월 대비 변동 부위 (증가·감소 Top 3)",
            "단위: 톤 · 국가 합산",
            imp,
        ),
        "",
        divider,
        "※ 데이터 출처: 시세-미트박스 B2B / 재고·수입-월별 집계자료",
        "※ 증감률(%) = (당월값 - 전월값) / 전월값 × 100",
        "※ 데이터 공개 시차로 표마다 기준월이 다를 수 있습니다.",
        "※ 본 표는 고정폭 글꼴(예: Consolas, D2Coding, 나눔고딕코딩)에서 칸이 맞습니다.",
        divider,
    ]
    return "\n".join(parts)


# ==================================================================
# 5. CLI
# ==================================================================
def main():
    parser = argparse.ArgumentParser(description="온라인우편 레터용 시세/재고/수입 변동 표 생성")
    parser.add_argument(
        "--month",
        help="기준월(YYYY-MM). 미지정 시 각 데이터의 최신 완료 월을 자동 사용.",
        default=None,
    )
    parser.add_argument(
        "--out",
        help="출력 파일 경로. 미지정 시 data/3_reports/letter_<기준월>.txt",
        default=None,
    )
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
        stamp = str(anchor) if anchor is not None else datetime.now().strftime("%Y-%m")
        out_path = DATA_REPORTS / f"letter_{stamp}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(letter, encoding="utf-8")

    print(letter)
    print(f"\n[저장 완료] {out_path}")


if __name__ == "__main__":
    main()
