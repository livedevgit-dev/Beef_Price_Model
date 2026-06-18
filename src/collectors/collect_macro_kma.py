"""
[파일 정의서]
- 파일명: collect_macro_kma.py
- 역할: 수집
- 대상: 국내 기후 지표 (평균기온·최고기온·강수량) — 축산물 소비/공급 계절성 외생변수
- 데이터 소스: 기상청 지상(종관, ASOS) 일자료 조회서비스 (공공데이터포털)
    http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList
- 수집/가공 주기: 일단위 — indicator_id별 기존 raw CSV max(date) 이후만 증분 수집
- 주요 기능:
    1. .env(KMA_API_KEY) 로딩. 키가 비어 있으면 즉시 graceful skip (파이프라인 중단 없음)
    2. 전국 대표 관측소(서울·부산·대구·광주·대전 등) 일자료를 받아 날짜별 평균 → 전국 대표값
    3. 공통 raw CSV(FRED/ECOS 와 공유)에 long format 으로 병합
    4. 최초 실행 시 2019-01-01 부터 연 단위 청크로 백필, 이후 증분

수집 지표 (long format) — data/0_raw/macro_indicators_raw.csv (동일 스키마):
    kr_temp_avg  평균기온 (전국 대표 관측소 평균, °C)
    kr_temp_max  최고기온 (전국 대표 관측소 평균, °C)
    kr_precip    일강수량 (전국 대표 관측소 평균, mm; 무강수=0)
    - country = 'KR', source = 'KMA', freq = 'D'

참고:
- ASOS 필드: tm(일자), avgTa(평균기온), maxTa(최고기온), sumRn(일강수량; 무강수 시 공백→0)
- 서비스키는 공공데이터포털 "기상청_지상(종관, ASOS) 일자료 조회서비스" 활용신청 후 발급.
  ⚠️ requests 가 자동 URL 인코딩하므로 .env 에는 **Decoding(일반) 인증키**를 넣을 것.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MACRO_RAW_CSV, ensure_dirs

# 사내망 SSL 검사(중간 프록시) 대응 (USDA 수집기와 동일 패턴)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
BASE_URL = "http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
INITIAL_START = date(2019, 1, 1)
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_CALLS = 0.4
NUM_OF_ROWS = 999

COUNTRY = "KR"
SOURCE = "KMA"
DUPLICATE_KEYS = ["date", "country", "indicator_id"]

# 전국 대표 관측소 (지점번호: 이름) — 권역 분산. 필요 시 가감.
STATIONS = {
    108: "서울",
    159: "부산",
    143: "대구",
    156: "광주",
    133: "대전",
}

# ASOS 필드 → indicator 매핑
INDICATORS = [
    {"indicator_id": "kr_temp_avg", "field": "avgTa", "indicator_name": "평균기온(전국대표)", "unit": "°C"},
    {"indicator_id": "kr_temp_max", "field": "maxTa", "indicator_name": "최고기온(전국대표)", "unit": "°C"},
    {"indicator_id": "kr_precip", "field": "sumRn", "indicator_name": "일강수량(전국대표)", "unit": "mm"},
]


# --------------------------------------------------------------------------
# 인증 / 유틸
# --------------------------------------------------------------------------
def _get_api_key() -> str | None:
    key = os.getenv("KMA_API_KEY", "").strip()
    return key or None


def _read_last_date(df_existing: pd.DataFrame, indicator_id: str) -> date | None:
    if df_existing.empty:
        return None
    sub = df_existing.loc[df_existing["indicator_id"] == indicator_id, "date"]
    if sub.empty:
        return None
    parsed = pd.to_datetime(sub, errors="coerce").dropna()
    if parsed.empty:
        return None
    return parsed.max().date()


def _generate_year_ranges(start: date, end: date) -> list[tuple[date, date]]:
    ranges: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        year_end = date(cursor.year, 12, 31)
        chunk_end = min(year_end, end)
        ranges.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return ranges


def _parse_float(raw) -> float | None:
    s = str(raw).strip()
    if s in {"", "-"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# API 호출 (관측소 × 연 단위 청크)
# --------------------------------------------------------------------------
def _fetch_station_year(api_key: str, stn_id: int, start: date, end: date) -> list[dict]:
    params = {
        "serviceKey": api_key,
        "pageNo": "1",
        "numOfRows": str(NUM_OF_ROWS),
        "dataType": "JSON",
        "dataCd": "ASOS",
        "dateCd": "DAY",
        "startDt": start.strftime("%Y%m%d"),
        "endDt": end.strftime("%Y%m%d"),
        "stnIds": str(stn_id),
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
    except requests.RequestException as e:
        # 예외 메시지에 serviceKey 가 포함될 수 있으므로 타입만 출력
        print(f"   └ [예외] 지점 {stn_id} {start.year}: 연결 실패 ({type(e).__name__})")
        return []
    if resp.status_code != 200:
        print(f"   └ [에러] HTTP {resp.status_code} (지점 {stn_id} {start.year})")
        return []
    try:
        payload = resp.json()
    except ValueError:
        # 인증 실패 등은 XML/텍스트로 떨어질 수 있음 (키 노출 방지 위해 본문 미출력)
        print(f"   └ [에러] JSON 파싱 실패 (지점 {stn_id} {start.year}) — 키/활용신청 확인 필요")
        return []

    body = payload.get("response", {}).get("body", {})
    header = payload.get("response", {}).get("header", {})
    code = header.get("resultCode", "")
    if code not in ("", "00"):
        # 03=NODATA 등은 정상적인 무자료 처리
        if code != "03":
            print(f"   └ [KMA {code}] {header.get('resultMsg','')} (지점 {stn_id} {start.year})")
        return []

    items = body.get("items", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    return items if isinstance(items, list) else []


# --------------------------------------------------------------------------
# 누적 저장 (공통 raw)
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
    df_final["_sort_dt"] = pd.to_datetime(df_final["date"], errors="coerce")
    df_final = df_final.sort_values(by=["_sort_dt", "country", "indicator_id"]).drop(columns=["_sort_dt"])
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


def _load_existing(save_path: Path) -> pd.DataFrame:
    if not save_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(save_path, low_memory=False)
    except Exception:
        return pd.DataFrame()


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_macro_kma_increment() -> None:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)

    api_key = _get_api_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 KMA_API_KEY 가 비어 있습니다.\n"
            "         발급 후 입력하면 다음 실행부터 기후 지표가 자동 수집됩니다.\n"
            "         발급: 공공데이터포털 '기상청_지상(종관, ASOS) 일자료 조회서비스' 활용신청\n"
            "         https://www.data.go.kr/data/15059093/openapi.do"
        )
        return

    df_existing = _load_existing(save_path)
    today = date.today()

    # 증분 시작일: 3개 지표 중 가장 오래된(최소) 마지막일 기준 (모두 같은 날 갱신되므로 사실상 동일)
    last_dates = [
        _read_last_date(df_existing, ind["indicator_id"]) for ind in INDICATORS
    ]
    last_dates = [d for d in last_dates if d is not None]
    if not last_dates:
        start = INITIAL_START
        print(f"[시스템] 기존 기후 데이터 없음 → {start} 부터 전체 수집")
    else:
        start = min(last_dates) + timedelta(days=1)
        print(f"[시스템] 기후 데이터 마지막일 {min(last_dates)} → {start} 부터 증분")

    if start > today:
        print("[성공] 이미 최신 상태입니다.")
        return

    year_ranges = _generate_year_ranges(start, today)
    print(f"[안내] {len(STATIONS)}개 지점 × {len(year_ranges)}개 연도청크 수집 ({start} ~ {today})")

    # 관측소별 일자료 수집 → 날짜별 필드 누적
    # raw_by_date[date_str][field] = [관측소값들]
    raw_by_date: dict[str, dict[str, list[float]]] = {}
    for stn_id in STATIONS:
        for s, e in year_ranges:
            items = _fetch_station_year(api_key, stn_id, s, e)
            for it in items:
                if not isinstance(it, dict):
                    continue
                tm = str(it.get("tm", "")).strip()  # 'YYYY-MM-DD'
                if not tm:
                    continue
                bucket = raw_by_date.setdefault(tm, {})
                for ind in INDICATORS:
                    field = ind["field"]
                    val = _parse_float(it.get(field))
                    if field == "sumRn" and val is None:
                        val = 0.0  # 무강수는 0 으로 간주
                    if val is not None:
                        bucket.setdefault(field, []).append(val)
            time.sleep(SLEEP_BETWEEN_CALLS)

    if not raw_by_date:
        print("[안내] KMA 신규 데이터가 없습니다.")
        return

    # 날짜별 관측소 평균 → long rows
    new_rows: list[dict] = []
    for tm, fields in raw_by_date.items():
        for ind in INDICATORS:
            vals = fields.get(ind["field"])
            if not vals:
                continue
            avg = sum(vals) / len(vals)
            new_rows.append({
                "date": tm,
                "country": COUNTRY,
                "indicator_id": ind["indicator_id"],
                "indicator_name": ind["indicator_name"],
                "value": round(avg, 2),
                "unit": ind["unit"],
                "freq": "D",
                "source": SOURCE,
            })

    if not new_rows:
        print("[안내] 파싱된 기후 데이터가 없습니다.")
        return

    total = _merge_and_save(new_rows, save_path)
    print(f"[완료] KMA 신규 {len(new_rows)}건 병합 — raw 누적 총 {total}건 ({save_path})")


if __name__ == "__main__":
    collect_macro_kma_increment()
