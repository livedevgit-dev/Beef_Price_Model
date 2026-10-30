# [파일 정의서]
# - 파일명: crawl_imp_stock_monthly.py
# - 역할: 수집 (KMTA 한국육류유통수출협회 재고 데이터)
# - 대상: 수입 소고기 재고 현황 (월별, 부위별 조사재고량)
# - 데이터 소스: 한국육류유통수출협회 홈페이지 (beef_stock_income.php)
# - 주요 기능:
#   1. 증분 수집(마지막 월 다음 달 ~ 이번 달) + 최근 N개월 재확인(--recheck, 기본 3) + 중간 누락 월 재수집
#   2. 특정 월 재수집(--months 2023-04,2022-08) / 전체 재수집(--all) / 파일 검증만(--validate-only)
#   3. 저장 전 검증 (월 단위로 거부/보정):
#      - 응답 월 == 요청 월 (페이지의 선택된 연/월 확인)
#      - 부위 구성(13행: 11개 부위+부산물+합계), Σ부위 == 합계 (반올림 허용 ±max(5, 0.1%))
#      - 부위 간 (재고량·전월%·전년%) 완전 동일 → 행 복제 의심
#      - 사이트의 '전월 대비(%)' 와 실제 전월 재고량으로 계산한 비율이 3개 부위 이상 불일치 → 다른 월 복제 의심
#   4. 보정 규칙: Σ 불일치가 '한 부위'(누락·복제 의심)로 설명되면 그 부위 = 합계 − 나머지 로 역산하고 '비고'에 원값 기록.
#      설명되지 않으면 해당 월 값을 결측(NaN)으로 비우고 '비고'에 사유 기록 (틀린 숫자를 남기지 않음).
#      실제 사례: 2022-08·2025-04 갈비가 기타 행 복제, 2026-03 부산물 누락, 2023-04 전체가 2022-07 복제(사이트 원본 오류).
#   5. 종료 코드: 네트워크·파싱 오류, 응답 월 불일치, 새로 발견된 불량 월 → exit 1 / 미게시("등록된 자료가 없습니다") → exit 0
#      기존 파일을 읽을 수 없으면 덮어쓰지 않고 exit 1.
# - 비고: 2023-05 이후 갈비·등심·목심 등이 -47~-77% 급감(합계 279천→162천톤)하는 구조적 단절이 있음(조사 표본 변경 추정).
#         데이터는 사이트 값 그대로 두고, 모델(build_samgyup_model.py)에서 2023-05 이후만 사용한다.

import argparse
import re
import sys
import time
from datetime import datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, BEEF_STOCK_XLSX
from utils.io_safe import atomic_to_excel

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = 'https://www.kmta.or.kr/kr/info/beef_stock_income.php'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://www.kmta.or.kr',
    'Referer': URL,
}

START_YEAR, START_MONTH = 2019, 1
NOW = datetime.now()

# 저장 컬럼 (사이트 MultiIndex 헤더를 합친 이름 — 다른 리더들이 이 이름으로 읽음, 변경 금지)
C_YM, C_PART, C_QTY, C_MOM, C_YOY, C_NOTE = (
    '기준년월', '부위별 부위별', '조사재고량 조사재고량', '대비(%) 전월', '대비(%) 전년', '비고')
COLS = [C_YM, C_PART, C_QTY, C_MOM, C_YOY, C_NOTE]
PARTS = ['안심', '등심', '채끝', '목심', '앞다리', '우둔', '설도', '양지', '사태', '갈비', '기타', '부산물']
TOTAL = '합계'
NO_DATA_PAT = '등록 된 자|자료가 없'

SUM_TOL_ABS, SUM_TOL_REL = 5, 0.001   # Σ부위 vs 합계 반올림 허용
MOM_TOL_PT = 1.5                       # 사이트 전월% vs 계산 전월% 허용 (정수 반올림)
MOM_MIN_BASE = 300                     # 전월 재고가 너무 작은 부위는 비율 검증 제외
MOM_BAD_PARTS = 3                      # 이 개수 이상 불일치 → 다른 월 복제/오정렬로 판단
REPAIR_RATIO = (0.67, 1.5)             # 역산값/전월값 허용 범위


# =========================================================
# 1. 월 유틸
# =========================================================
def ym_str(y, m):
    return f"{y}-{m:02d}"


def ym_range(start, end):
    return [str(p) for p in pd.period_range(start, end, freq='M')]


def ym_shift(ym, k):
    return str(pd.Period(ym, freq='M') + k)


# =========================================================
# 2. 사이트 조회 (월 1건)
# =========================================================
def fetch_month(session, ym):
    """반환: (status, df|None, msg). status ∈ OK / UNPUBLISHED / ERROR"""
    y, m = ym.split('-')
    data = {'typ': 'list_url', 'list_url': '/kr/info/beef_stock_income.php', 'page': '1',
            'board': 'info10', 'scode': '10', 'year': y, 'month': m}
    try:
        r = session.post(URL, headers=HEADERS, data=data, verify=False, timeout=30)
    except requests.RequestException as e:
        return 'ERROR', None, f"요청 실패: {e}"
    if r.status_code != 200:
        return 'ERROR', None, f"HTTP {r.status_code}"
    html = r.text

    # 응답 월 == 요청 월 (페이지의 선택된 연/월 option)
    sel_y = re.search(r"<option value=(\d{4}) selected", html)
    sel_m = re.search(r"<option value=(\d{2}) selected", html)
    if not sel_y or not sel_m:
        return 'ERROR', None, "응답에서 선택된 연/월을 찾지 못함 (페이지 구조 변경?)"
    if f"{sel_y.group(1)}-{sel_m.group(1)}" != ym:
        return 'ERROR', None, f"응답 월 불일치: 요청 {ym} ≠ 응답 {sel_y.group(1)}-{sel_m.group(1)}"

    try:
        dfs = pd.read_html(StringIO(html))
    except ValueError as e:
        return 'ERROR', None, f"표 파싱 실패: {e}"
    if not dfs:
        return 'ERROR', None, "표 없음"
    df = dfs[0]
    if df.astype(str).apply(lambda x: x.str.contains(NO_DATA_PAT, na=False)).any().any():
        return 'UNPUBLISHED', None, "미등록(업데이트 대기)"

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(c) for c in col if "Unnamed" not in str(c)).strip() for col in df.columns]
    if list(df.columns[:4]) != [C_PART, C_QTY, C_MOM, C_YOY]:
        return 'ERROR', None, f"컬럼 구조 변경: {list(df.columns)}"
    df = df.iloc[:, :4].copy()
    for c in (C_QTY, C_MOM, C_YOY):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce')
    df.insert(0, C_YM, ym)
    df[C_NOTE] = ''
    return 'OK', df, f"{len(df)}행"


# =========================================================
# 3. 검증 · 보정
# =========================================================
def _frame(month_df):
    """월 데이터 → 부위 인덱스 (qty, mom, yoy)"""
    if month_df is None or month_df.empty:
        return None
    f = month_df.set_index(C_PART)[[C_QTY, C_MOM, C_YOY]]
    f.columns = ['qty', 'mom', 'yoy']
    f = f[~f.index.duplicated(keep='first')]
    if f['qty'].isna().all():
        return None          # 결측 처리된 월 → 비교 기준으로 쓰지 않음
    return f


def _sum_ok(total, parts_sum):
    return abs(parts_sum - total) <= max(SUM_TOL_ABS, SUM_TOL_REL * total)


def _pct(cur, base):
    if base is None or pd.isna(base) or base <= 0 or pd.isna(cur):
        return np.nan
    return float(round(100 * cur / base))


def check_month(ym, month_df, prev_df=None, prev_year_df=None):
    """한 달 데이터 검증.
    반환: (verdict, out_df, msgs). verdict ∈ OK / REPAIRED / BAD
      - REPAIRED: 한 부위를 합계 − 나머지 로 역산 (비고에 원값 기록)
      - BAD     : 값을 신뢰할 수 없음 → 호출측에서 결측 처리/거부
    """
    msgs = []
    cur = _frame(month_df)
    if cur is None:
        return 'BAD', month_df, ["값 없음"]
    unknown = [p for p in cur.index if p not in PARTS + [TOTAL]]
    if unknown:
        return 'BAD', month_df, [f"알 수 없는 부위 {unknown} (사이트 표 구조 변경?)"]
    if TOTAL not in cur.index or pd.isna(cur.loc[TOTAL, 'qty']):
        return 'BAD', month_df, ["합계 행 없음"]
    total = cur.loc[TOTAL, 'qty']
    parts = cur.drop(index=TOTAL)
    missing = [p for p in PARTS if p not in parts.index or pd.isna(parts.loc[p, 'qty'])]
    suspects = set(missing)

    # 부위 간 (재고량, 전월%, 전년%) 완전 동일 → 행 복제 의심
    pv = parts.dropna(subset=['qty'])
    dup = pv[pv['qty'] > 0].duplicated(subset=['qty', 'mom', 'yoy'], keep=False)
    if dup.any():
        suspects |= set(dup[dup].index)
        msgs.append(f"부위 간 동일값 {sorted(dup[dup].index)}={int(pv.loc[dup[dup].index[0], 'qty'])}")

    # 사이트 전월% vs 실제 전월 재고량 비율
    prev = _frame(prev_df)
    mom_bad = []
    if prev is not None:
        for p in cur.index:
            if p in prev.index and prev.loc[p, 'qty'] >= MOM_MIN_BASE and cur.loc[p, 'mom'] > 0:
                calc = 100 * cur.loc[p, 'qty'] / prev.loc[p, 'qty']
                if abs(calc - cur.loc[p, 'mom']) > MOM_TOL_PT:
                    mom_bad.append(p)
    if len([p for p in mom_bad if p not in suspects]) >= MOM_BAD_PARTS:
        return 'BAD', month_df, msgs + [
            f"전월 대비(%) 가 실제 전월 재고와 {len(mom_bad)}개 부위에서 불일치 → 다른 월 데이터 복제/오정렬 의심 ({', '.join(mom_bad[:6])}...)"]

    parts_sum = pv['qty'].sum()
    if _sum_ok(total, parts_sum):
        if missing:
            return 'BAD', month_df, msgs + [f"부위 누락 {missing} (Σ는 일치)"]
        if mom_bad:
            msgs.append(f"[참고] 전월% 불일치(재고량은 정상 범위): {mom_bad}")
        return 'OK', month_df, msgs

    # Σ 불일치 → 의심 부위 1개를 역산해서 설명되는지 확인
    if len(mom_bad) <= 2:
        suspects |= set(p for p in mom_bad if p != TOTAL)
    accepted = []
    for p in sorted(suspects):
        others = [q for q in PARTS if q != p]
        if any(q not in parts.index or pd.isna(parts.loc[q, 'qty']) for q in others):
            continue
        x = total - parts.loc[others, 'qty'].sum()
        if x <= 0:
            continue
        if prev is not None and p in prev.index and prev.loc[p, 'qty'] > 0:
            r = x / prev.loc[p, 'qty']
            if not (REPAIR_RATIO[0] <= r <= REPAIR_RATIO[1]):
                continue
        accepted.append((p, x))
    if len(accepted) != 1:
        return 'BAD', month_df, msgs + [
            f"Σ부위 {parts_sum:,.0f} ≠ 합계 {total:,.0f} (비율 {parts_sum/total:.3f}) — 단일 부위 역산으로 설명 안 됨"]

    p, x = accepted[0]
    out = month_df.copy()
    orig = parts.loc[p, 'qty'] if p in parts.index else np.nan
    pq = prev.loc[p, 'qty'] if prev is not None and p in prev.index else None
    py = _frame(prev_year_df)
    yq = py.loc[p, 'qty'] if py is not None and p in py.index else None
    note = (f"{p} 역산(합계−타부위): 사이트값 {'누락' if pd.isna(orig) else f'{orig:,.0f}'} → {x:,.0f}; "
            f"전월·전년%는 재계산")
    row = {C_YM: ym, C_PART: p, C_QTY: x, C_MOM: _pct(x, pq), C_YOY: _pct(x, yq), C_NOTE: note}
    if p in parts.index:
        out = out[out[C_PART] != p]
    out = pd.concat([out, pd.DataFrame([row])], ignore_index=True)
    return 'REPAIRED', _order(out), msgs + [note]


def _order(df):
    rank = {p: i for i, p in enumerate(PARTS + [TOTAL])}
    df = df.copy()
    df['_r'] = df[C_PART].map(rank).fillna(99)
    return df.sort_values([C_YM, '_r']).drop(columns='_r').reset_index(drop=True)


def blank_month(month_df, reason):
    """값을 결측으로 비우고 사유를 비고에 남긴다 (행은 유지 → 누락 월로 오인되지 않게)."""
    out = month_df.copy()
    out[[C_QTY, C_MOM, C_YOY]] = np.nan
    out[C_NOTE] = f"결측 처리: {reason}"
    return out


def is_blank(month_df):
    return month_df is not None and not month_df.empty and month_df[C_QTY].isna().all()


def validate_all(df, verbose=True):
    """전체 파일을 시간순으로 검증·보정. 반환: (보정된 df, {월: (verdict, msgs)})"""
    report = {}
    by_month = {ym: g for ym, g in df.groupby(C_YM, sort=True)}
    fixed, seen = {}, {}
    for ym in sorted(by_month):
        g = by_month[ym]
        if is_blank(g):
            fixed[ym] = g
            report[ym] = ('BLANK', [str(g[C_NOTE].iloc[0])])
            continue
        verdict, g2, msgs = check_month(ym, g, fixed.get(ym_shift(ym, -1)), fixed.get(ym_shift(ym, -12)))
        # 다른 월과 전 부위 재고량이 완전히 같으면 복제 (자연 발생 불가) → 나중 월을 불량 처리
        sig = tuple(sorted((p, q) for p, q in zip(g[C_PART], g[C_QTY]) if pd.notna(q) and q > 0))
        if len(sig) >= 10:
            if sig in seen:
                verdict = 'BAD'
                msgs = [f"{seen[sig]} 과 전 부위 재고량 완전 동일(사이트 원본 복제)"] + msgs
            else:
                seen[sig] = ym
        if verdict == 'BAD':
            g2 = blank_month(g, "; ".join(msgs))
        fixed[ym] = g2
        report[ym] = (verdict, msgs)
        if verbose and (verdict != 'OK' or msgs):
            print(f"  [{verdict}] {ym}: {' | '.join(msgs)}")
    out = [fixed[ym] for ym in sorted(fixed)]
    return _order(pd.concat(out, ignore_index=True)) if out else df, report


# =========================================================
# 4. 파일 I/O
# =========================================================
def load_existing(path):
    """기존 파일 읽기. 파일이 있는데 읽을 수 없으면 None 대신 예외 → 덮어쓰기 방지."""
    if not Path(path).exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_excel(path)   # 실패 시 예외 그대로 (호출측에서 중단)
    if C_YM not in df.columns:
        raise ValueError(f"'{C_YM}' 컬럼이 없습니다: {list(df.columns)}")
    if C_NOTE not in df.columns:
        df[C_NOTE] = ''
    df[C_NOTE] = df[C_NOTE].fillna('').astype(str)
    df = df[df[C_YM].astype(str).str.match(r'^\d{4}-\d{2}$', na=False)]
    df = df[~df.astype(str).apply(lambda x: x.str.contains(NO_DATA_PAT, na=False)).any(axis=1)]
    for c in (C_QTY, C_MOM, C_YOY):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df[COLS].reset_index(drop=True)


def _for_save(df):
    df = df[COLS].copy()
    for c in (C_QTY, C_MOM, C_YOY):
        df[c] = pd.to_numeric(df[c], errors='coerce').round().astype('Int64')
    return df


def _month_values(df, ym):
    g = df[df[C_YM] == ym]
    return dict(zip(g[C_PART], g[C_QTY]))


def _diff_line(old, new, ym):
    a, b = _month_values(old, ym), _month_values(new, ym)
    ch = []
    for p in PARTS + [TOTAL]:
        va, vb = a.get(p, np.nan), b.get(p, np.nan)
        if not ((pd.isna(va) and pd.isna(vb)) or (not pd.isna(va) and not pd.isna(vb) and round(va) == round(vb))):
            fa = '-' if pd.isna(va) else f"{va:,.0f}"
            fb = '-' if pd.isna(vb) else f"{vb:,.0f}"
            ch.append(f"{p} {fa}→{fb}")
    return ", ".join(ch)


# =========================================================
# 5. 메인
# =========================================================
def parse_args():
    ap = argparse.ArgumentParser(description="KMTA 월별 수입육 재고 수집·검증")
    ap.add_argument('--months', help="재수집할 월 목록 (예: 2023-04,2022-08)")
    ap.add_argument('--recheck', type=int, default=3, help="최근 N개월 재확인 (기본 3, 0=신규 월만)")
    ap.add_argument('--all', action='store_true', help=f"{START_YEAR}-{START_MONTH:02d}부터 전체 재수집")
    ap.add_argument('--validate-only', action='store_true', help="네트워크 없이 기존 파일만 검증 (저장 안 함)")
    return ap.parse_args()


def main():
    args = parse_args()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    save_path = BEEF_STOCK_XLSX

    try:
        existing = load_existing(save_path)
    except Exception as e:
        print(f"[실패] 기존 재고 파일을 읽을 수 없어 중단합니다 (덮어쓰기 방지): {save_path}\n  사유: {e}")
        return 1

    if args.validate_only:
        print(f"[검증] {save_path.name} ({existing[C_YM].nunique()}개월)")
        _, report = validate_all(existing)
        bad = [ym for ym, (v, _) in report.items() if v in ('BAD', 'REPAIRED')]
        blank = [ym for ym, (v, _) in report.items() if v == 'BLANK']
        print(f"[검증 결과] 정상 {sum(v == 'OK' for v, _ in report.values())}개월 · "
              f"결측처리 유지 {blank} · 미보정 불량 {bad}")
        return 1 if bad else 0

    cur_ym = ym_str(NOW.year, NOW.month)
    have = sorted(existing[C_YM].unique())
    if args.months:
        targets = sorted({m.strip() for m in args.months.split(',') if m.strip()})
        bad_fmt = [m for m in targets if not re.match(r'^\d{4}-\d{2}$', m)]
        if bad_fmt:
            print(f"[실패] --months 형식 오류: {bad_fmt} (YYYY-MM)")
            return 1
        mode = "지정 월 재수집"
    elif args.all or not have:
        targets = ym_range(ym_str(START_YEAR, START_MONTH), cur_ym)
        mode = "전체 수집"
    else:
        last = have[-1]
        new = ym_range(ym_shift(last, 1), cur_ym) if last < cur_ym else []
        recheck = [m for m in ym_range(ym_shift(last, -(args.recheck - 1)), last)] if args.recheck > 0 else []
        holes = [m for m in ym_range(have[0], last) if m not in have]
        # 결측 처리된 월(사이트 원본 오류)은 매번 재조회하지 않음 → --months 로 명시 재확인
        blank_months = {ym for ym, g in existing.groupby(C_YM) if is_blank(g)}
        targets = sorted(set(new) | (set(recheck) - blank_months) | set(holes))
        mode = f"증분+최근 {args.recheck}개월 재확인" + (f"+누락 {holes}" if holes else "")

    print(f"[시작] KMTA 재고 [{mode}] 대상 {len(targets)}개월: {targets[0] if targets else '-'} ~ {targets[-1] if targets else '-'}")
    print("=" * 60)

    errors, fetched, unpublished = [], {}, []
    session = requests.Session()
    for ym in targets:
        if ym > cur_ym:
            continue
        status, df, msg = fetch_month(session, ym)
        print(f"[조회] {ym} ... {status} {msg}")
        if status == 'ERROR':
            errors.append(f"{ym}: {msg}")
        elif status == 'UNPUBLISHED':
            unpublished.append(ym)
            if ym in have and not is_blank(existing[existing[C_YM] == ym]):
                print(f"   [경고] {ym} 는 기존 파일에 있으나 사이트에서 미등록으로 응답 → 기존 값 유지")
        else:
            fetched[ym] = df
        time.sleep(0.5)

    # 병합: 받은 월은 사이트 원값으로 교체 (검증·보정은 아래 validate_all 에서 일괄)
    merged = existing[~existing[C_YM].isin(fetched)]
    if fetched:
        merged = pd.concat([merged] + list(fetched.values()), ignore_index=True)
    merged = _order(merged)

    print("-" * 60)
    print("[검증] 전체 월 검증·보정")
    final, report = validate_all(merged)

    # 새로 불량 판정된 월 (기존에 결측 처리돼 있던 월은 제외) → exit 1
    old_blank = {ym for ym, g in existing.groupby(C_YM) if is_blank(g)}
    newly_bad = [ym for ym, (v, _) in report.items() if v == 'BAD' and ym not in old_blank]
    repaired = [ym for ym, (v, _) in report.items() if v == 'REPAIRED']

    changed_months = []
    for ym in sorted(set(final[C_YM]) | set(existing[C_YM])):
        line = _diff_line(existing, final, ym)
        if line:
            changed_months.append(ym)
            print(f"  [변경] {ym}: {line}")
    note_changed = not existing.empty and (
        set(existing[C_YM]) != set(final[C_YM]) or
        existing.sort_values([C_YM, C_PART])[C_NOTE].tolist() != final.sort_values([C_YM, C_PART])[C_NOTE].tolist())

    if changed_months or note_changed or existing.empty:
        if final.empty:
            print("[경고] 저장할 데이터가 없습니다.")
        else:
            atomic_to_excel(_for_save(final), save_path, index=False)
            print(f"[저장] {save_path.name}: {final[C_YM].nunique()}개월 {len(final)}행 (변경 {len(changed_months)}개월)")
    else:
        print("[정보] 변경 사항 없음 — 파일 유지")

    print("=" * 60)
    if unpublished:
        print(f"[정보] 미등록(협회 업데이트 대기): {unpublished}")
    if repaired:
        print(f"[보정] 단일 부위 역산: {repaired}")
    if newly_bad:
        print(f"[실패] 검증 불통과 → 결측 처리: {newly_bad}")
    if errors:
        print("[실패] 조회 오류:\n  " + "\n  ".join(errors))
    if errors or newly_bad:
        return 1
    print("[완료] 재고 수집·검증 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
