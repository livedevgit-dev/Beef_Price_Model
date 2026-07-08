# [파일 정의서]
# - 파일명: src/reports/generate_letter.py
# - 역할: 산출물 생성 (온라인우편 복붙용 — 수입육 시장 트렌드 레터)
# - 대상: 수입육(미트박스 B2B 도매시세) 중심
# - 데이터 소스: dashboard_ready_data.csv(시세), master_import_volume.csv(수입량)
# - 목적: "제가 실행하면 전월 기준으로 최근 수입육 시장 트렌드가 한눈에 정리되는"
#         간단한 복붙용 텍스트 양식 생성. 표보다 요약·핵심 수치 중심.
# - 구성:
#     1) 이번 달 총평 (전월 대비 전반 방향 + 평균 변동률 + 오른/내린 부위 수)
#     2) 대표 부위(삼겹양지) 시세 한 줄
#     3) 전월 대비 많이 오른/내린 부위 Top 5
#     4) 수입 물량 한 줄 요약 (최신 확정월 기준)
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
    DATA_REPORTS,
    ensure_dirs,
)

# 대표 부위 (수입육 벤치마크). 데이터에 있으면 총평 아래 단독 표기.
FLAGSHIP_PART = "삼겹양지"
# 상승/하락 부위 표기 개수
TOP_N = 5
# 총평 방향 판정 임계치(%)
FLAT_THRESHOLD = 0.5


# ==================================================================
# 고정폭 정렬 유틸 (한글 2칸 폭 — 우편/메모장 등 고정폭 글꼴에서 칸 맞춤)
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


def _fmt_pct(v) -> str:
    return f"{v:+.1f}%"


# ==================================================================
# 기준월 선정 (전월 = 최신 '완료' 월)
# ==================================================================
def _pick_months(periods, anchor=None, today_period=None):
    """
    당월/전월 Period 반환.
    - anchor 지정: anchor 이하 최신 월을 당월로.
    - 미지정: 실행 시점의 현재 달(부분월)을 제외한 최신 완료월을 당월로.
    """
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


# ==================================================================
# 시세 트렌드 집계 (부위별 월평균 도매가 → 전월 대비 변동)
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

    # 부위별 월평균(국가·브랜드 합산 평균)
    cur_avg = df[df["month"] == cur].groupby("part")["wholesale_price"].mean()
    prev_avg = df[df["month"] == prev].groupby("part")["wholesale_price"].mean()
    merged = pd.concat([cur_avg.rename("cur"), prev_avg.rename("prev")], axis=1).dropna()
    merged = merged[merged["prev"] > 0]
    if merged.empty:
        return {"cur": cur, "prev": prev, "empty": True}

    merged["pct"] = (merged["cur"] - merged["prev"]) / merged["prev"] * 100

    up = merged[merged["pct"] > 0].sort_values("pct", ascending=False)
    down = merged[merged["pct"] < 0].sort_values("pct", ascending=True)
    avg_pct = float(merged["pct"].mean())

    flagship = None
    if FLAGSHIP_PART in merged.index:
        r = merged.loc[FLAGSHIP_PART]
        flagship = (float(r["cur"]), float(r["prev"]), float(r["pct"]))

    return {
        "cur": cur, "prev": prev, "empty": False,
        "avg_pct": avg_pct,
        "n_up": int((merged["pct"] > 0).sum()),
        "n_down": int((merged["pct"] < 0).sum()),
        "n_total": int(len(merged)),
        "up": up.head(TOP_N), "down": down.head(TOP_N),
        "flagship": flagship,
    }


# ==================================================================
# 수입 물량 한 줄 요약 (최신 확정월 기준 전월 대비)
# ==================================================================
def build_import_line(anchor=None):
    if not MASTER_IMPORT_VOLUME_CSV.exists():
        return None
    try:
        df = pd.read_csv(str(MASTER_IMPORT_VOLUME_CSV))
        df["month"] = pd.to_datetime(df["std_date"]).dt.to_period("M")
    except Exception:
        return None

    total_col = next((c for c in df.columns if c.startswith("부위별_") and "계_합계" in c), None)
    if total_col is None:
        return None
    grp = df.groupby("month")[total_col].sum()

    months = sorted(grp.index)
    if anchor is not None:
        months = [m for m in months if m <= anchor]
    if len(months) < 2:
        return None
    cur, prev = months[-1], months[-2]
    cv, pv = grp.get(cur), grp.get(prev)
    if pv is None or pv == 0 or cv is None:
        return None
    pct = (cv - pv) / pv * 100
    return {"cur": cur, "prev": prev, "cur_val": float(cv), "pct": pct}


# ==================================================================
# 레터 본문 조립
# ==================================================================
def _direction_word(pct) -> str:
    if pct > FLAT_THRESHOLD:
        return "상승"
    if pct < -FLAT_THRESHOLD:
        return "하락"
    return "보합"


def _period_kr(p) -> str:
    return f"{p.year}년 {p.month}월" if p is not None else "-"


def _movers_block(title, sub, marker):
    if sub is None or sub.empty:
        return [title, f"  ({marker} 해당 부위 없음)"]
    name_w = max(_disp_width(str(p)) for p in sub.index)
    lines = [title]
    for part, r in sub.iterrows():
        lines.append(
            f"  {marker} {_pad(part, name_w)}  {r['cur']:>7,.0f}원/kg  ({_fmt_pct(r['pct'])})"
        )
    return lines


def generate_letter(anchor=None) -> str:
    today_period = pd.Period(datetime.now(), "M")
    trend = build_price_trend(anchor=anchor, today_period=today_period)
    imp = build_import_line(anchor=anchor)

    divider = "=" * 60
    L = [divider]

    if not trend or trend.get("empty"):
        cur = trend["cur"] if trend else None
        L.append("■ 수입육 시장 동향 리포트")
        L.append(f"  생성일시: {datetime.now():%Y-%m-%d %H:%M}")
        L.append(divider)
        L.append("")
        L.append("집계 가능한 시세 데이터가 부족합니다.")
        L.append(divider)
        return "\n".join(L)

    cur, prev = trend["cur"], trend["prev"]
    L.append(f"■ 수입육 시장 동향 리포트 — {_period_kr(cur)} 기준")
    L.append(f"  생성일시: {datetime.now():%Y-%m-%d %H:%M}")
    L.append(divider)

    # 1) 이번 달 총평
    direction = _direction_word(trend["avg_pct"])
    L.append("")
    L.append("[이번 달 총평]")
    L.append(
        f"{_period_kr(cur)} 수입육 도매가는 전월({_period_kr(prev)}) 대비 전반적으로 "
        f"'{direction}' 흐름입니다."
    )
    L.append(
        f"  · 부위 평균 변동: {_fmt_pct(trend['avg_pct'])}  (미트박스 B2B 도매시세, 월평균 기준)"
    )
    L.append(
        f"  · 오른 부위 {trend['n_up']}개 / 내린 부위 {trend['n_down']}개 "
        f"(집계 {trend['n_total']}개 부위)"
    )

    # 2) 대표 부위 (삼겹양지)
    if trend["flagship"]:
        cv, pv, pc = trend["flagship"]
        L.append("")
        L.append("[대표 부위 — 삼겹양지(미국·호주산)]")
        L.append(f"  · {cv:,.0f}원/kg  (전월 {pv:,.0f} → {_fmt_pct(pc)})")

    # 3) 오른/내린 부위 Top N
    L.append("")
    L.extend(_movers_block(f"[전월 대비 많이 오른 부위 Top {TOP_N}]", trend["up"], "▲"))
    L.append("")
    L.extend(_movers_block(f"[전월 대비 많이 내린 부위 Top {TOP_N}]", trend["down"], "▼"))

    # 4) 수입 물량 한 줄
    if imp:
        L.append("")
        L.append("[수입 물량]")
        L.append(
            f"  · {_period_kr(imp['cur'])} 총 수입량 약 {imp['cur_val']:,.0f}톤 "
            f"(전월 대비 {_fmt_pct(imp['pct'])})"
        )

    # 꼬리말
    L.append("")
    L.append(divider)
    L.append("※ 출처: 시세-미트박스 B2B 도매시세 / 수입량-KMTA·식약처")
    L.append("※ 증감률(%) = (당월 평균 - 전월 평균) / 전월 평균 × 100")
    L.append("※ 데이터 공개 시차로 시세와 수입량의 기준월이 다를 수 있습니다.")
    L.append("※ 고정폭 글꼴(예: 나눔고딕코딩·Consolas)에서 칸이 맞습니다.")
    L.append(divider)
    return "\n".join(L)


# ==================================================================
# CLI
# ==================================================================
def main():
    parser = argparse.ArgumentParser(description="온라인우편 복붙용 수입육 시장 트렌드 레터 생성")
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
        # 파일명은 '기준월'(레터의 당월)로 — 실행월과 어긋나지 않게
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
