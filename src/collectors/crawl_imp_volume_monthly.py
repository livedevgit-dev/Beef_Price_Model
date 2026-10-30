# [파일 정의서]
# - 파일명: src/collectors/crawl_imp_volume_monthly.py
# - 역할: 수집 (KMTA 한국육류유통수출협회 부위별 수입실적)
# - 대상: 수입 소고기 (미국/호주 냉동), 단위 톤
# - 출력: data/0_raw/master_import_volume.csv
#         컬럼: std_date, 구분, 부위별_*_합계 ..., 부위별_계_합계, data_source(KMTA/MFDS)
# - 기능:
#   1. 신규 월(마지막 월 다음 달 ~ 전월) + 최근 N개월 재확인(--recheck, 기본 12) + 식약처(MFDS) 잠정치 월 전부를 조회.
#      KMTA 확정치가 게시된 월은 MFDS 잠정치를 덮어쓰고 data_source=KMTA 로 표시 (식약처 보완분 자동 교체).
#   2. KMTA 수치가 바뀐 월(수정 게시)은 변경 내역을 출력하고 갱신.
#   3. 결측과 0 구분: 사이트의 '-' 만 0, 빈칸·파싱 실패는 NaN → 해당 월을 오류로 거부(부분 저장 안 함).
#   4. 검증: 냉동 섹션에 미국·호주 각 1행, Σ부위 ≈ 사이트 '계'(반올림 허용), 부위 컬럼 수 일치.
#   5. 종료 코드: 조회·파싱·검증 오류 → exit 1 / 미게시 → exit 0. 기존 파일을 읽을 수 없으면 덮어쓰지 않고 exit 1.
#   6. --dry-run: 조회·비교만 하고 저장 안 함.

import argparse
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
from config import DATA_RAW, MASTER_IMPORT_VOLUME_CSV
from utils.io_safe import atomic_to_csv

# =========================================================
# 1. 설정
# =========================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"
SAVE_PATH = MASTER_IMPORT_VOLUME_CSV
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Origin": "https://www.kmta.or.kr",
    "Referer": URL,
}
START_YM = "2019-01"
COUNTRIES = ["미국", "호주"]
PART_COLS = [
    '부위별_갈비_합계', '부위별_등심_합계', '부위별_목심_합계', '부위별_사태_합계', '부위별_설도_합계',
    '부위별_안심_합계', '부위별_앞다리_합계', '부위별_양지_합계', '부위별_우둔_합계', '부위별_채끝_합계',
    '부위별_기타_합계',
]
TOTAL_COL = '부위별_계_합계'
SRC_COL = 'data_source'           # KMTA(협회 확정) / MFDS(식약처 검역 잠정, crawl_imp_food_safety.py)
COLS = ['std_date', '구분'] + PART_COLS + [TOTAL_COL, SRC_COL]
SITE_PARTS = [c.split('_')[1] for c in PART_COLS] + ['계']


# =========================================================
# 2. 기존 파일
# =========================================================
def infer_source(df):
    """data_source 컬럼이 없던 시절 파일 백필: KMTA 는 정수(톤), 식약처 보완분은 소수 1자리(kg/1000)."""
    vals = df[PART_COLS + [TOTAL_COL]].apply(pd.to_numeric, errors='coerce')
    frac = (vals - vals.round()).abs().fillna(0).gt(1e-9).any(axis=1)
    return np.where(frac, 'MFDS', 'KMTA')


def load_existing(path):
    """반환: DataFrame (없으면 빈 프레임). 파일이 있는데 읽을 수 없으면 예외 → 호출측에서 중단."""
    if not Path(path).exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(path, encoding='utf-8-sig', dtype={'std_date': str})
    need = {'std_date', '구분', TOTAL_COL}
    if not need <= set(df.columns):
        raise ValueError(f"필수 컬럼 없음: {need - set(df.columns)}")
    for c in PART_COLS:
        if c not in df.columns:
            df[c] = np.nan
    if SRC_COL not in df.columns:
        df[SRC_COL] = infer_source(df)
        print(f"[백필] {SRC_COL} 컬럼 추가 (정수=KMTA, 소수=MFDS): "
              f"{df.groupby(SRC_COL)['std_date'].agg(['min', 'max', 'count']).to_dict('index')}")
    return df[COLS].copy()


# =========================================================
# 3. 사이트 조회 (월 1건)
# =========================================================
def _num(v):
    """'1,234' → 1234 / '-' → 0 (KMTA 의 0 표기) / 빈칸·기타 → NaN (0 과 구분)"""
    s = str(v).strip().replace(',', '')
    if s == '-':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return np.nan


def fetch_month(session, ym):
    """반환: (status, df|None, msg). status ∈ OK / UNPUBLISHED / ERROR"""
    y, m = ym.split('-')
    form = {"ymw_y": y, "ymw_m": m, "ymw2_y": y, "ymw2_m": m, "typ": "write", "gubun": "CC01"}
    try:
        r = session.post(URL, data=form, headers=HEADERS, verify=False, timeout=30)
    except requests.RequestException as e:
        return 'ERROR', None, f"요청 실패: {e}"
    if r.status_code != 200:
        return 'ERROR', None, f"HTTP {r.status_code}"
    try:
        tables = pd.read_html(StringIO(r.text))
    except ValueError as e:
        return 'ERROR', None, f"표 파싱 실패: {e}"
    if not tables:
        return 'ERROR', None, "표 없음"

    t = tables[0]
    if t.shape[1] != 1 + len(SITE_PARTS):
        return 'ERROR', None, f"표 구조 변경: 열 {t.shape[1]}개 (기대 {1 + len(SITE_PARTS)})"
    if t.shape[0] == 0:
        return 'UNPUBLISHED', None, "미게시(빈 표)"
    hdr = [str(c[1]) if isinstance(c, tuple) else str(c) for c in t.columns[1:]]
    if hdr != SITE_PARTS:
        return 'ERROR', None, f"부위 헤더 변경: {hdr}"

    first = t.iloc[:, 0].astype(str).str.strip()
    frozen = first[first == '냉동'].index.tolist()
    chilled = first[first == '냉장'].index.tolist()
    if len(frozen) != 1:
        return 'ERROR', None, f"'냉동' 구분행 {len(frozen)}개"
    end = next((i for i in chilled if i > frozen[0]), len(t))
    sec = t.loc[frozen[0] + 1:end - 1]
    sec = sec[sec.iloc[:, 0].astype(str).str.strip().isin(COUNTRIES)]
    got = sec.iloc[:, 0].astype(str).str.strip().tolist()
    if sorted(got) != sorted(COUNTRIES):
        return 'ERROR', None, f"냉동 섹션 국가행 이상: {got}"

    rows = []
    for _, r_ in sec.iterrows():
        vals = [_num(v) for v in r_.iloc[1:]]
        parts, site_total = vals[:-1], vals[-1]
        if any(np.isnan(v) for v in vals):
            return 'ERROR', None, f"{r_.iloc[0]} 빈 값/숫자 아님: {list(r_.iloc[1:])}"
        s = sum(parts)
        if abs(s - site_total) > max(len(parts), 0.005 * site_total):
            return 'ERROR', None, f"{r_.iloc[0]} Σ부위 {s:,.0f} ≠ 사이트 계 {site_total:,.0f}"
        row = {'std_date': ym, '구분': str(r_.iloc[0]).strip()}
        row.update(dict(zip(PART_COLS, parts)))
        row[TOTAL_COL] = s
        row[SRC_COL] = 'KMTA'
        rows.append(row)
    msg = " / ".join(f"{r['구분']} 계 {r[TOTAL_COL]:,.0f}" for r in rows)
    return 'OK', pd.DataFrame(rows)[COLS], msg


# =========================================================
# 4. 비교·병합
# =========================================================
def diff_rows(old, new):
    """같은 월·국가의 기존행 vs 신규행 차이 요약 (|Δ|≥0.5 톤)"""
    out = []
    for c in PART_COLS + [TOTAL_COL]:
        a, b = old.get(c), new.get(c)
        if pd.isna(a) and pd.isna(b):
            continue
        if pd.isna(a) or pd.isna(b) or abs(float(a) - float(b)) >= 0.5:
            out.append(f"{c.split('_')[1]} {a if pd.isna(a) else round(float(a), 1)}→{b if pd.isna(b) else round(float(b), 1)}")
    return out


def parse_args():
    ap = argparse.ArgumentParser(description="KMTA 월별 수입실적(미국/호주 냉동) 수집")
    ap.add_argument('--recheck', type=int, default=12, help="최근 N개월 재확인 (기본 12)")
    ap.add_argument('--months', help="지정 월만 조회 (예: 2026-02,2026-03)")
    ap.add_argument('--all', action='store_true', help=f"{START_YM}부터 전체 재조회")
    ap.add_argument('--dry-run', action='store_true', help="조회·비교만, 저장 안 함")
    return ap.parse_args()


def main():
    args = parse_args()
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    try:
        existing = load_existing(SAVE_PATH)
    except Exception as e:
        print(f"[실패] 기존 수입량 파일을 읽을 수 없어 중단합니다 (덮어쓰기 방지): {SAVE_PATH}\n  사유: {e}")
        return 1

    now = datetime.now()
    last_complete = str(pd.Period(now, freq='M') - 1)       # 전월까지 (당월은 집계 전)
    have = sorted(existing['std_date'].astype(str).unique())
    if args.months:
        targets = sorted({m.strip() for m in args.months.split(',') if m.strip()})
    elif args.all or not have:
        targets = [str(p) for p in pd.period_range(START_YM, last_complete, freq='M')]
    else:
        start = min(have[-1], str(pd.Period(last_complete, freq='M') - (args.recheck - 1)))
        window = [str(p) for p in pd.period_range(start, last_complete, freq='M')]
        mfds = sorted(existing.loc[existing[SRC_COL] == 'MFDS', 'std_date'].astype(str).unique())
        targets = sorted(set(window) | set(mfds))

    print(f"--- [시작] KMTA 미국/호주 냉동 수입실적 ({SAVE_PATH.name}) 대상 {len(targets)}개월: "
          f"{targets[0] if targets else '-'} ~ {targets[-1] if targets else '-'} ---")

    session = requests.Session()
    fetched, errors, unpublished = [], [], []
    for ym in targets:
        status, df, msg = fetch_month(session, ym)
        print(f">> {ym} {status} {msg}")
        if status == 'OK':
            fetched.append(df)
        elif status == 'UNPUBLISHED':
            unpublished.append(ym)
        else:
            errors.append(f"{ym}: {msg}")
        time.sleep(0.5)

    # 병합: KMTA 행이 같은 월·국가의 기존행(MFDS 잠정 또는 이전 KMTA)을 대체
    final = existing.copy()
    changes = []
    if fetched:
        new = pd.concat(fetched, ignore_index=True)
        key = lambda d: d['std_date'].astype(str) + '|' + d['구분'].astype(str)
        old_idx = dict(zip(key(existing), existing.index))
        for _, r in new.iterrows():
            k = f"{r['std_date']}|{r['구분']}"
            if k in old_idx:
                o = existing.loc[old_idx[k]]
                d = diff_rows(o, r)
                if d or o[SRC_COL] != 'KMTA':
                    changes.append(f"{k} [{o[SRC_COL]}→KMTA] " + (", ".join(d) if d else "값 동일"))
            else:
                changes.append(f"{k} [신규 KMTA] 계 {r[TOTAL_COL]:,.0f}")
        final = pd.concat([existing[~key(existing).isin(set(key(new)))], new], ignore_index=True)

    final = final.sort_values(by=['std_date', '구분'], ascending=[False, True])[COLS]

    print("\n" + "=" * 50)
    for c in changes:
        print(f"[변경] {c}")
    src_added = SRC_COL not in pd.read_csv(SAVE_PATH, nrows=0, encoding='utf-8-sig').columns if SAVE_PATH.exists() else True
    if (changes or src_added) and not final.empty:
        if args.dry_run:
            print(f"[dry-run] 저장하지 않음 (변경 {len(changes)}건)")
        else:
            atomic_to_csv(final, SAVE_PATH, index=False, encoding='utf-8-sig')
            print(f"[저장] {SAVE_PATH} ({len(final)}행, 변경 {len(changes)}건, 최신 {final.iloc[0]['std_date']})")
    else:
        print("[정보] 변경 없음 — 기존 파일 유지")
    print(f"[출처] {final.groupby(SRC_COL)['std_date'].agg(['min', 'max', 'count']).to_dict('index')}")
    if unpublished:
        print(f"[정보] KMTA 미게시: {unpublished}")
    if errors:
        print("[실패] 조회/검증 오류 (해당 월은 반영 안 함):\n  " + "\n  ".join(errors))
        return 1
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
