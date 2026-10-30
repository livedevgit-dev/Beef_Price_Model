"""
[파일 정의서]
- 파일명: crawl_han_auction_api.py
- 역할: 수집
- 대상: 한우 (국내 도매시장 소도체 경락가격 + 도축장별 경매두수)
- 데이터 소스: 축산물품질평가원(EKAPE) OpenAPI
    http://data.ekape.or.kr/openapi-data/service/user/grade/auct/cattle
- 수집/가공 주기: 일단위 증분 — 수집 범위는 '어제'까지 (당일 경매는 오전 실행 시점에 미완결이라 제외)
- 주요 기능:
    1. .env(EKAPE_API_KEY) 로딩, 인증키 미설정 시 즉시 종료
    2. qgradeYn='Y' (육질등급별: 1++, 1+, 1, 2, 3, D(=등외), 평균 등) × 결함포함 가격 기준
    3. wide format(도매시장별 c_XXXXAmt/c_XXXXCnt, CCityAmt 등) → long format(market_code, market_name, price, head_count)으로 정규화
    4. 응답은 요청 구간 [startYmd, endYmd] 전체의 '기간 합산'(두수 합계·평균가) 1건이다(일별 분해 아님).
       → DAILY_SINCE(2026-01-01) 이후는 1일 청크로 호출해 일별 값으로 저장.
         그 이전(2019~2025)은 30일 청크 합산 행으로 보존 — auction_start_ymd~auction_end_ymd 가 합산 구간이며
         전처리(preprocess_hanwoo.py)가 period_days 컬럼으로 명시한다.
    5. 매 실행마다 최근 REFETCH_DAYS(7)일을 다시 받아 기존 행을 '교체' (지연 게시·일시 실패 자가 복구).
       DAILY_SINCE 이후에 기간 합산 행이 남아 있으면 그 구간도 1일 단위로 재수집해 교체.
    6. 누적 CSV(`data/0_raw/han_auction_raw.csv`) 병합: 새로 받은 구간과 겹치는 기존 행을 지운 뒤
       (auction_end_ymd, grade_cd, grade_nm, sex_cd, qgrade_yn, defect_include_yn, market_code) 키로 최신 우선 중복 제거
    7. 휴장일(응답 정상·값 없음)은 정상 처리, 네트워크/HTTP/인증/파싱 오류는 '실패'로 집계 →
       끝에 요약 출력 후 실패가 1건이라도 있으면 exit 1 (받은 데이터는 저장, 다음 실행 재수집 창에서 복구)

산출 컬럼(long format):
    auction_start_ymd, auction_end_ymd, grade_type, grade_cd, grade_nm,
    breed_cd, breed_nm, sex_cd, sex_nm,
    qgrade_yn, defect_include_yn,
    market_code, market_name, is_regional_total, is_national_total, price_won_per_kg, head_count
"""

from __future__ import annotations

import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import HAN_AUCTION_RAW_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
API_URL = "http://data.ekape.or.kr/openapi-data/service/user/grade/auct/cattle"
INITIAL_START = datetime(2019, 1, 1)  # EKAPE는 2010-05부터 데이터가 있으나 다른 소스와 정합성 위해 2019-01-01부터
DAILY_SINCE = datetime(2026, 1, 1)    # 이 날부터는 1일 청크(일별 값). 이전은 30일 합산 청크
HIST_CHUNK_DAYS = 30                  # DAILY_SINCE 이전 구간의 호출당 일수 (전체 재구축 시에만 사용)
REFETCH_DAYS = 7                      # 매 실행 재수집·교체하는 최근 일수
MAX_CALLS_PER_RUN = 500               # 1회 실행 호출 상한 (공공데이터포털 일일 트래픽 보호)
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_CALLS = 0.5             # 공공API 트래픽 보호

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

# 응답에서 시장별 가격/두수를 식별하기 위한 정규식
#   c_0101Amt / c_0101Cnt   → 코드: 0101
#   CCityAmt  / CCityCnt    → 코드: City
#   CTotAmt   / CTotCnt     → 코드: Tot
#   CCenterAmt / CCenterCnt → 코드: Center  (대소문자 무관하게 매핑)
MARKET_PATTERN = re.compile(r"^(?:c_|C)(.+?)(Amt|Cnt)$")

# 시장 코드 → 한글명 매핑 (응답에 따로 시장명이 없어 컬럼명 기반으로 운영)
# 권역 합계는 "권역" 표시, 도축장은 명칭 표시
MARKET_NAME_MAP: dict[str, str] = {
    "0101": "농협서울",
    "0320": "도드람",
    "0302": "협신식품",
    "1301": "삼성식품",
    "0323": "농협부천",
    "City": "수도권(권역)",
    "0513": "농협음성",
    "1005": "김해축공",
    "0202": "부경축공",
    "0201": "동원산업",
    "1201": "신흥산업",
    "0905": "농협고령",
    "East": "영남권(권역)",
    "0714": "익산",
    "0809": "농협나주",
    "1401": "삼호축산",
    "West": "호남권(권역)",
    "1101": "제주축협",
    "Tot": "전국(전체)",
    "0613": "관성",
    "Center": "중부권(권역)",
    "0616": "농협포크빌",
    "1015": "창녕축공",
    "0918": "안동봉화",
    "0717": "중앙축산물도매시장",
}
_MARKET_NAME_LC = {k.lower(): v for k, v in MARKET_NAME_MAP.items()}

# 권역/전국 합계 — 비교는 소문자 기준 (응답 컬럼은 CCenterAmt 인데 과거 코드가 'center'로 비교해 누락됐던 문제 대응)
REGIONAL_CODES = {"city", "east", "west", "center"}  # 권역 합계
NATIONAL_CODES = {"tot"}                              # 전국 합계

DUPLICATE_KEYS = [
    "auction_end_ymd",   # 경매일(1일 청크는 시작=종료)
    "grade_cd",
    "grade_nm",
    "sex_cd",
    "qgrade_yn",
    "defect_include_yn",
    "market_code",
]
# CSV 재로딩 시 int/str 혼재로 중복 제거가 어긋나지 않도록 문자열로 고정
STR_COLS = [
    "auction_start_ymd", "auction_end_ymd", "grade_type", "grade_cd", "grade_nm",
    "breed_cd", "breed_nm", "sex_cd", "sex_nm", "qgrade_yn", "defect_include_yn", "market_code",
]


# --------------------------------------------------------------------------
# 유틸
# --------------------------------------------------------------------------
def _get_api_key() -> str:
    key = os.getenv("EKAPE_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "[설정 누락] .env 의 EKAPE_API_KEY 가 비어 있습니다.\n"
            "공공데이터포털에서 발급받은 키를 입력하세요: "
            "https://www.data.go.kr/data/15058822/openapi.do"
        )
    return key


def _load_existing(save_path: Path) -> pd.DataFrame:
    if not save_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(save_path, dtype={c: str for c in STR_COLS}, keep_default_na=False,
                     na_values={"price_won_per_kg": [""], "head_count": [""]}, low_memory=False)
    return df


def _ymd(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str), format="%Y%m%d", errors="coerce")


def _date_chunks(start: datetime, end: datetime, days: int) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        chunks.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _build_chunks(start: datetime, end: datetime) -> list[tuple[str, str]]:
    """DAILY_SINCE 이전은 30일 합산 청크, 이후는 1일 청크."""
    chunks: list[tuple[str, str]] = []
    if start < DAILY_SINCE:
        chunks += _date_chunks(start, min(end, DAILY_SINCE - timedelta(days=1)), HIST_CHUNK_DAYS)
    if end >= DAILY_SINCE:
        chunks += _date_chunks(max(start, DAILY_SINCE), end, 1)
    return chunks


def _to_int(text: str | None) -> int | None:
    if text is None:
        return None
    t = str(text).strip()
    if not t or t.lower() == "none":
        return None
    try:
        return int(float(t))
    except (TypeError, ValueError):
        return None


def _apply_market_meta(df: pd.DataFrame) -> pd.DataFrame:
    """market_code 기준으로 시장명·권역/전국 플래그를 다시 계산 (기존 누적분 교정 포함)."""
    code_lc = df["market_code"].astype(str).str.strip().str.lower()
    df["market_name"] = code_lc.map(_MARKET_NAME_LC).fillna(df["market_code"].astype(str))
    df["is_regional_total"] = code_lc.isin(REGIONAL_CODES)
    df["is_national_total"] = code_lc.isin(NATIONAL_CODES)
    return df


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_range(
    api_key: str,
    start_ymd: str,
    end_ymd: str,
    *,
    qgrade_yn: str = "Y",
    defect_include_yn: str = "Y",
) -> list[dict] | None:
    """단일 청크 호출. 등급별 합산 시장별 row 반환(wide).
    정상 응답이면 list(휴장일은 값 없는 item 들), 네트워크/HTTP/파싱/API 오류면 None."""
    params = {
        "serviceKey": api_key,
        "startYmd": start_ymd,
        "endYmd": end_ymd,
        "qgradeYn": qgrade_yn,
        "defectIncludeYn": defect_include_yn,
    }
    try:
        resp = requests.get(
            API_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException as e:
        # 예외 메시지에 serviceKey 가 포함된 URL 이 들어갈 수 있으므로 타입만 출력
        print(f"   └ [예외] 연결 실패 ({type(e).__name__})")
        return None

    if resp.status_code != 200:
        print(f"   └ [에러] HTTP {resp.status_code}")
        return None

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"   └ [에러] XML 파싱 실패: {e} / 응답 일부: {resp.text[:150]!r}")
        return None

    # 인증 실패 등은 <OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode> 로 떨어진다
    reason_el = root.find(".//returnReasonCode")
    if reason_el is not None and (reason_el.text or "").strip() not in {"", "00"}:
        msg = root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg") or ""
        print(f"   └ [API 에러] {reason_el.text} {msg}")
        return None

    result_code = (root.findtext(".//resultCode") or "").strip()
    if result_code != "00":
        msg = root.findtext(".//resultMsg") or ""
        print(f"   └ [API 에러] resultCode={result_code or '(없음)'} {msg}")
        return None

    rows: list[dict] = []
    for item in root.findall(".//item"):
        row = {child.tag: (child.text or "").strip() for child in item}
        rows.append(row)
    return rows


def _wide_to_long(
    wide_rows: list[dict],
    *,
    qgrade_yn: str,
    defect_include_yn: str,
) -> list[dict]:
    """wide 응답을 long format으로 펼친다. 가격·두수가 둘 다 비어있으면 제외."""
    long_rows: list[dict] = []
    for r in wide_rows:
        meta = {
            "auction_start_ymd": r.get("startYmd", ""),
            "auction_end_ymd": r.get("endYmd", ""),
            "grade_type": r.get("gradeType", ""),
            "grade_cd": r.get("gradeCd", ""),
            "grade_nm": r.get("gradeNm", ""),
            "breed_cd": r.get("judgeBreedCd", ""),
            "breed_nm": r.get("judgeBreedNm", ""),
            "sex_cd": r.get("judgeSexCd", ""),
            "sex_nm": r.get("judgeSexNm", ""),
            "qgrade_yn": r.get("qgradeYn", qgrade_yn),
            "defect_include_yn": r.get("defectIncludeYn", defect_include_yn),
        }

        prices: dict[str, int | None] = {}
        counts: dict[str, int | None] = {}
        for col, val in r.items():
            m = MARKET_PATTERN.match(col)
            if not m:
                continue
            code, kind = m.group(1), m.group(2)
            v = _to_int(val)
            if kind == "Amt":
                prices[code] = v
            else:
                counts[code] = v

        market_codes = set(prices.keys()) | set(counts.keys())
        for code in sorted(market_codes):
            price = prices.get(code)
            count = counts.get(code)
            if price is None and count is None:
                continue
            long_rows.append({
                **meta,
                "market_code": code,
                "price_won_per_kg": price,
                "head_count": count,
            })
    return long_rows


# --------------------------------------------------------------------------
# 누적 저장
# --------------------------------------------------------------------------
def _overlap_mask(df: pd.DataFrame, intervals: list[tuple[str, str]]) -> pd.Series:
    """df 의 [auction_start_ymd, auction_end_ymd] 가 intervals 중 하나라도 겹치면 True."""
    mask = pd.Series(False, index=df.index)
    if df.empty or not intervals:
        return mask
    s = df["auction_start_ymd"].astype(str)
    e = df["auction_end_ymd"].astype(str)
    for a, b in intervals:
        mask |= (s <= b) & (e >= a)   # YYYYMMDD 문자열 비교 = 날짜 비교
    return mask


def _merge_and_save(
    df_old: pd.DataFrame,
    new_rows: list[dict],
    fetched: list[tuple[str, str]],
    failed: list[tuple[str, str]],
    today_ymd: str,
    save_path: Path,
) -> int:
    """fetched(정상 응답 구간)와 겹치는 기존 행은 새 응답으로 교체.
    단, 실패 구간과도 겹치는 기존 기간합산 행은 남기고 그 구간의 새 행을 버린다(이중 집계 방지 → 다음 실행에 재시도)."""
    df_new = pd.DataFrame(new_rows)
    if not df_old.empty:
        keep_old = _overlap_mask(df_old, failed)
        drop_old = _overlap_mask(df_old, fetched) & ~keep_old
        # 당일(미완결) 이후 행은 무조건 제거 — 과거 08시 실행이 저장한 부분 집계분 정리
        drop_old |= df_old["auction_end_ymd"].astype(str) >= today_ymd
        kept_spans = (
            df_old.loc[keep_old, ["auction_start_ymd", "auction_end_ymd"]]
            .drop_duplicates().itertuples(index=False, name=None)
        )
        if not df_new.empty:
            df_new = df_new[~_overlap_mask(df_new, list(kept_spans))]
        df_old = df_old[~drop_old]

    df_final = pd.concat([df_old, df_new], ignore_index=True)
    if df_final.empty:
        return 0
    for c in STR_COLS:
        if c in df_final.columns:
            df_final[c] = df_final[c].fillna("").astype(str)
    df_final = _apply_market_meta(df_final)

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    df_final = df_final.drop_duplicates(subset=subset, keep="last")

    df_final["_sort_dt"] = _ymd(df_final["auction_end_ymd"])
    df_final = df_final.sort_values(by=["_sort_dt", "grade_cd", "market_code"]).drop(columns=["_sort_dt"])

    cols = ["auction_start_ymd", "auction_end_ymd", "grade_type", "grade_cd", "grade_nm",
            "breed_cd", "breed_nm", "sex_cd", "sex_nm", "qgrade_yn", "defect_include_yn",
            "market_code", "market_name", "is_regional_total", "is_national_total",
            "price_won_per_kg", "head_count"]
    df_final = df_final[[c for c in cols if c in df_final.columns]]
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_han_auction_increment() -> int:
    """증분 수집. 반환값 = 실패(오류) 청크 수."""
    ensure_dirs()
    save_path = Path(HAN_AUCTION_RAW_CSV)
    api_key = _get_api_key()

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    today_ymd = today.strftime("%Y%m%d")

    df_old = _load_existing(save_path)
    if df_old.empty:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start.date()}부터 전체 수집")
    else:
        end_dt = _ymd(df_old["auction_end_ymd"])
        start_dt = _ymd(df_old["auction_start_ymd"])
        complete = end_dt < today
        last_date = end_dt[complete].max()
        # 시작점 = min(마지막 완결 경매일+1, 최근 7일 재수집 창, DAILY_SINCE 이후 남은 기간합산 행 시작일)
        cands = [yesterday - timedelta(days=REFETCH_DAYS - 1)]
        if pd.notna(last_date):
            cands.append(last_date.to_pydatetime() + timedelta(days=1))
        multi = (end_dt >= DAILY_SINCE) & (start_dt < end_dt) & complete
        if multi.any():
            cands.append(start_dt[multi].min().to_pydatetime())
            print(f"[안내] {DAILY_SINCE.date()} 이후 기간합산 행 {int(multi.sum())}건 → 1일 단위로 재수집·교체")
        start = min(cands)
        print(
            f"[시스템] 기존 데이터 마지막 경매일(완결): "
            f"{last_date.date() if pd.notna(last_date) else '-'} → {start.date()}부터 수집 "
            f"(최근 {REFETCH_DAYS}일 재수집 포함, 당일 제외)"
        )

    if start > yesterday:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return 0

    chunks = _build_chunks(start, yesterday)
    if len(chunks) > MAX_CALLS_PER_RUN:
        # 기존 기간합산 행을 중간에서 자르지 않도록 그 행 시작 전까지로 절단 → 나머지는 다음 실행
        cut = chunks[MAX_CALLS_PER_RUN - 1][1]
        if not df_old.empty:
            s, e = df_old["auction_start_ymd"], df_old["auction_end_ymd"]
            straddle = s[(s <= cut) & (e > cut)]
            if not straddle.empty:
                cut = (datetime.strptime(straddle.min(), "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
        chunks = [c for c in chunks[:MAX_CALLS_PER_RUN] if c[1] <= cut]
        print(f"[안내] 호출 상한 {MAX_CALLS_PER_RUN}건 → 이번 실행은 {cut}까지만 수집, 나머지는 다음 실행")
    print(f"[안내] {len(chunks)}회 호출 ({chunks[0][0]} ~ {chunks[-1][1]})")

    new_long_rows: list[dict] = []
    fetched: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []
    holidays = 0

    for i, (s, e) in enumerate(chunks, 1):
        wide = _fetch_range(api_key, s, e, qgrade_yn="Y", defect_include_yn="Y")
        if wide is None:
            print(f" - [{i}/{len(chunks)}] {s} ~ {e} 실패")
            failed.append((s, e))
        else:
            fetched.append((s, e))
            long_rows = _wide_to_long(wide, qgrade_yn="Y", defect_include_yn="Y")
            if long_rows:
                new_long_rows.extend(long_rows)
                if len(chunks) <= 31 or i % 30 == 0 or i == len(chunks):
                    print(f" - [{i}/{len(chunks)}] {s} ~ {e}: wide {len(wide)}행 → long {len(long_rows)}행")
            else:
                holidays += 1   # 정상 응답 + 값 없음 = 휴장일
        time.sleep(SLEEP_BETWEEN_CALLS)

    if fetched or not df_old.empty:
        total = _merge_and_save(df_old, new_long_rows, fetched, failed, today_ymd, save_path)
        print(f"[완료] 신규 long row {len(new_long_rows)}건 반영 — 누적 총 {total}건 ({save_path})")

    print(
        f"[요약] 호출 {len(chunks)}회: 정상 {len(fetched)} (휴장·무거래 {holidays}) / 실패 {len(failed)}"
    )
    if failed:
        print(
            f"[경고] 실패 구간 {len(failed)}건 (첫 3건: {failed[:3]}) — "
            f"최근 {REFETCH_DAYS}일 이내는 다음 실행 재수집 창에서 다시 받습니다. 그보다 오래된 구간은 수동 재실행 필요."
        )
    return len(failed)


if __name__ == "__main__":
    sys.exit(1 if collect_han_auction_increment() else 0)
