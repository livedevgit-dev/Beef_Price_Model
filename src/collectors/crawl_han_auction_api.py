"""
[파일 정의서]
- 파일명: crawl_han_auction_api.py
- 역할: 수집
- 대상: 한우 (국내 도매시장 소도체 경락가격 + 도축장별 경매두수)
- 데이터 소스: 축산물품질평가원(EKAPE) OpenAPI
    http://data.ekape.or.kr/openapi-data/service/user/grade/auct/cattle
- 수집/가공 주기: 일단위 — 기존 CSV의 마지막 auction_date 이후만 증분 수집
- 주요 기능:
    1. .env(EKAPE_API_KEY) 로딩, 인증키 미설정 시 즉시 종료
    2. qgradeYn='Y' (육질등급별: 1++, 1+, 1, 2, 3, 등외) × 결함포함 가격 기준
    3. wide format(도매시장별 c_XXXXAmt/c_XXXXCnt 컬럼) → long format(market_code, market_name, price, head_count)으로 정규화 후 저장
    4. 호출당 1~30일 범위로 잘라 요청 (EKAPE는 응답에 일별 합산만 들어오는 구조라 큰 범위도 가능하나, 안정성을 위해 30일 청크)
    5. 누적 CSV(`data/0_raw/han_auction_raw.csv`)에 (auction_start_ymd, auction_end_ymd, grade_cd, sex_cd, market_code) 키 기준 중복 제거 병합

산출 컬럼(long format):
    auction_start_ymd, auction_end_ymd, grade_type, grade_cd, grade_nm,
    breed_cd, breed_nm, sex_cd, sex_nm,
    qgrade_yn, defect_include_yn,
    market_code, market_name, price_won_per_kg, head_count
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

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
API_URL = "http://data.ekape.or.kr/openapi-data/service/user/grade/auct/cattle"
INITIAL_START = datetime(2019, 1, 1)  # EKAPE는 2010-05부터 데이터가 있으나 다른 소스와 정합성 위해 2019-01-01부터
CHUNK_DAYS = 30                       # API 호출당 일수
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
#   c_centerAmt / c_centerCnt → 코드: center
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
    "center": "중부권(권역)",
    "0616": "농협포크빌",
    "1015": "창녕축공",
    "0918": "안동봉화",
    "0717": "중앙축산물도매시장",
}

REGIONAL_CODES = {"City", "East", "West", "center"}  # 권역 합계
NATIONAL_CODES = {"Tot"}                              # 전국 합계

DUPLICATE_KEYS = [
    "auction_start_ymd",
    "auction_end_ymd",
    "grade_cd",
    "sex_cd",
    "qgrade_yn",
    "defect_include_yn",
    "market_code",
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


def _read_last_date(save_path: Path) -> datetime | None:
    if not save_path.exists():
        return None
    try:
        df = pd.read_csv(save_path, usecols=["auction_end_ymd"], low_memory=False)
    except Exception:
        return None
    if df.empty:
        return None
    parsed = pd.to_datetime(
        df["auction_end_ymd"].astype(str), format="%Y%m%d", errors="coerce"
    ).dropna()
    if parsed.empty:
        return None
    return parsed.max().to_pydatetime()


def _date_chunks(start: datetime, end: datetime, days: int) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        chunks.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cursor = chunk_end + timedelta(days=1)
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
) -> list[dict]:
    """단일 청크 호출. 등급별 합산 시장별 row 반환(wide)."""
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
        print(f"   └ [예외] {e}")
        return []

    if resp.status_code != 200:
        print(f"   └ [에러] HTTP {resp.status_code}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"   └ [에러] XML 파싱 실패: {e}")
        return []

    result_code_el = root.find(".//resultCode")
    result_msg_el = root.find(".//resultMsg")
    result_code = result_code_el.text if result_code_el is not None else ""
    if result_code and result_code != "00":
        msg = result_msg_el.text if result_msg_el is not None else ""
        print(f"   └ [API 에러] {result_code} {msg}")
        return []

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
                "market_name": MARKET_NAME_MAP.get(code, code),
                "is_regional_total": code in REGIONAL_CODES,
                "is_national_total": code in NATIONAL_CODES,
                "price_won_per_kg": price,
                "head_count": count,
            })
    return long_rows


# --------------------------------------------------------------------------
# 누적 저장
# --------------------------------------------------------------------------
def _merge_and_save(new_rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(new_rows)
    if df_new.empty:
        return _existing_row_count(save_path)

    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    if subset:
        df_final = df_final.drop_duplicates(subset=subset, keep="last")

    if "auction_end_ymd" in df_final.columns:
        df_final["_sort_dt"] = pd.to_datetime(
            df_final["auction_end_ymd"].astype(str), format="%Y%m%d", errors="coerce"
        )
        df_final = df_final.sort_values(
            by=["_sort_dt", "grade_cd", "market_code"]
        ).drop(columns=["_sort_dt"])

    save_path.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(str(save_path), index=False, encoding="utf-8-sig")
    return len(df_final)


def _existing_row_count(save_path: Path) -> int:
    if not save_path.exists():
        return 0
    try:
        return sum(1 for _ in open(save_path, "r", encoding="utf-8-sig")) - 1
    except OSError:
        return 0


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_han_auction_increment() -> None:
    ensure_dirs()
    save_path = Path(HAN_AUCTION_RAW_CSV)
    api_key = _get_api_key()

    last_date = _read_last_date(save_path)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if last_date is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start.date()}부터 전체 수집")
    else:
        start = last_date + timedelta(days=1)
        print(
            f"[시스템] 기존 데이터 마지막 경매일: {last_date.date()} "
            f"→ {start.date()}부터 증분 수집"
        )

    if start > today:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return

    chunks = _date_chunks(start, today, CHUNK_DAYS)
    print(
        f"[안내] {len(chunks)}개 청크 × {CHUNK_DAYS}일 호출 "
        f"({start.date()} ~ {today.date()})"
    )

    new_long_rows: list[dict] = []
    success_chunks = 0
    failed_chunks: list[tuple[str, str]] = []

    for i, (s, e) in enumerate(chunks, 1):
        print(f" - [{i}/{len(chunks)}] {s} ~ {e}")
        wide = _fetch_range(api_key, s, e, qgrade_yn="Y", defect_include_yn="Y")
        if not wide:
            failed_chunks.append((s, e))
            time.sleep(SLEEP_BETWEEN_CALLS)
            continue
        long_rows = _wide_to_long(wide, qgrade_yn="Y", defect_include_yn="Y")
        if long_rows:
            print(f"   └ 수집: wide {len(wide)}행 → long {len(long_rows)}행")
            new_long_rows.extend(long_rows)
            success_chunks += 1
        else:
            print("   └ 응답에 유효 가격/두수 없음")
        time.sleep(SLEEP_BETWEEN_CALLS)

    if not new_long_rows:
        print("[안내] API에서 신규 데이터가 반환되지 않았습니다.")
        if failed_chunks:
            print(f"[경고] 실패 청크 {len(failed_chunks)}건. 첫 3건: {failed_chunks[:3]}")
        return

    total = _merge_and_save(new_long_rows, save_path)
    print(
        f"[완료] 신규 long row {len(new_long_rows)}건 병합 — "
        f"누적 총 {total}건 ({save_path})"
    )
    if failed_chunks:
        print(
            f"[경고] 실패 청크 {len(failed_chunks)}건 — 재실행 시 같은 범위를 자동 재시도합니다."
        )


if __name__ == "__main__":
    collect_han_auction_increment()
