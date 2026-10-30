"""
[파일 정의서]
- 파일명: collect_macro_ecos.py
- 역할: 수집
- 대상: 국내 거시경제 지표 (한국은행 기준금리·CPI·PPI·수입물가·환율(AUD)·물류비·외식물가)
- 데이터 소스: 한국은행 ECOS Open API (StatisticSearch)
    https://ecos.bok.or.kr/api/StatisticSearch/{KEY}/json/kr/{start}/{end}/{통계표코드}/{주기}/{검색시작}/{검색종료}/{통계항목코드}
- 수집/가공 주기: 일/월 — indicator_id별 기존 raw CSV max(date) 이후만 증분 수집
- 주요 기능:
    1. .env(ECOS_API_KEY) 로딩. 키가 비어 있으면 즉시 graceful skip (파이프라인 중단 없음)
    2. Tier-1 국내 지표 3종을 long format 으로 수집하여 공통 raw CSV(FRED 와 공유)에 병합
    3. 최초 실행 시 2019-01 부터 백필, 이후 증분
    4. indicator 단위 실패는 경고 출력 후 계속 진행
       - INFO-200(해당 데이터 없음 = 아직 미발표) → 정상(exit 0)
       - 네트워크 예외 / HTTP 200 이외 / JSON 파싱 실패 / 그 밖의 RESULT 코드(인증 INFO-100, ERROR-xxx)
         → 오류로 집계, 받은 만큼 저장 후 exit 1 (2026-10 정합성 수정)
    5. 자가 치유 증분: 마지막 달 포함 최근 3개월(일별은 최근 7일)을 매번 다시 받아 해당 구간 행을 교체
       (잠정치·개정 반영)
    6. 기존 raw CSV 를 읽지 못하면 2019년부터 재수집하지 않고 중단(exit 1)
    7. (2026-10 추가) 응답이 1,000행을 넘으면(일별 환율 백필) list_total_count 기준으로 페이지를 나눠 받는다.
       indicator 별 country 지정 가능(기본 'KR').

항목코드가 여러 그룹(Group2: 경상/불변/계절조정, 원화/계약통화/달러 기준 등)으로 나뉜 통계표는
item_code 를 'Group1코드/Group2코드' 로 명시한다. 그룹을 생략하면 ECOS 가 모든 그룹 값을 한꺼번에 돌려주고
같은 (date, indicator_id) 가 여러 개 생겨 dedup(keep=last) 순서에 의존하게 된다.
    (2026-10 점검: kr_retail_* / kr_service_food 는 그동안 응답의 마지막 그룹 = 계절조정지수가 저장돼 왔음
     → 같은 값을 명시 코드로 고정. 저장값 불변 검증 완료)

2026-10 추가 지표 (원가·물류비·외식 소비 — StatisticTableList / StatisticItemList / StatisticSearch 로 검증):
    kr_impi_beef_krw     : 401Y017 / 10121201AA/W  수입물가지수(품목별) 쇠고기, 원화기준   (월)
    kr_impi_beef_lc      : 401Y017 / 10121201AA/C  수입물가지수(품목별) 쇠고기, 계약통화기준 (월)
    kr_fx_aud            : 731Y001 / 0000017       원/호주달러 매매기준율 (일) — 호주산 수입원가 환율 축
                           (원화 측 가격이므로 country='KR'. USD/KRW 는 crawl_com_usd_krw.py 가 별도 xlsx 로 관리)
    kr_cpi_diesel        : 901Y009 / G02102        소비자물가 경유 (월) — 국내 화물 유류비 proxy
    kr_ppi_road_freight  : 404Y014 / 501122AA      생산자물가 도로화물운송서비스 (월) — 국내 배송비
    kr_ppi_cold_storage  : 404Y016 / 50143102AA    생산자물가(품목) 냉장및냉동창고운영 (월) — 냉동육 보관비
    kr_ppi_ocean_freight : 404Y016 / 50121201AA    생산자물가(품목) 외항화물 (월) — 국적선사 해상운임
    kr_cpi_dineout       : 901Y009 / K011          소비자물가 음식 서비스(외식 전체) (월)
    kr_cpi_dineout_beef  : 901Y009 / K01110        소비자물가 쇠고기(외식) (월) — 외식 판매가(전가) 지표
    kr_retail_food       : 901Y100 / G31/T3        상품군별 소매판매액지수 음식료품, 계절조정 (월)
    (검토 후 제외: 601Y002 카드 음식점 승인액 — 2023-08 단종 / 601Y003 신용카드 이용액 — 업종 구분 없음 /
     200Y14x 가계 목적별 소비지출 — 분기)

ECOS 통계표코드 (공식: https://ecos.bok.or.kr/  > 통계검색):
    kr_base_rate = 722Y001  한국은행 기준금리 및 여수신금리 (주기 M)
    kr_cpi_food  = 901Y009  소비자물가지수(2020=100)(전국) (주기 M)
    kr_ppi_food  = 404Y014  생산자물가지수(기본분류) (주기 M)

통계항목코드(item_code)는 ECOS StatisticItemList API 로 검증 완료 (2025-06):
    kr_base_rate : 722Y001 / 0101000 (한국은행 기준금리) — 실제 금리 이력과 일치 검증
    kr_cpi_food  : 901Y009 / A      (식료품 및 비주류음료)
    kr_ppi_food  : 404Y014 / 301AA  (음식료품)
    kr_cpi_total : 901Y009 / 0      (소비자물가 총지수)
    kr_ccsi      : 511Y002 / FME    (소비자심리지수)
    kr_esi       : 513Y001 / E1000  (경제심리지수 원계열)
    (참고 대체코드 — CPI 식료품만: 901Y009/A01, PPI 식료품만: 404Y014/3011AA,
     PPI 농림수산품: 404Y014/101AA)
    item_code 가 틀리면 ECOS 가 INFO-200(무자료)을 반환하고 해당 indicator 만 skip,
    파이프라인은 계속된다.

산출 컬럼(long format) — data/0_raw/macro_indicators_raw.csv (FRED 와 동일 스키마):
    date, country, indicator_id, indicator_name, value, unit, freq, source
    - country = 'KR', source = 'ECOS'
    - 월별 지표의 date 는 해당 월 1일(YYYY-MM-01)로 통일 (FRED 월별과 정합)
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MACRO_RAW_CSV, ensure_dirs
from utils.io_safe import atomic_to_csv

# 사내망 SSL 검사(중간 프록시)로 인한 인증서 오류 대응.
# collect_usda_primal.py 와 동일한 패턴 (verify=False + 경고 억제).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

# --------------------------------------------------------------------------
# 상수
# --------------------------------------------------------------------------
BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
INITIAL_START = date(2019, 1, 1)          # 다른 데이터셋과 정합
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_CALLS = 0.5
MAX_ROWS_PER_CALL = 1000                  # ECOS 1회 응답 상한
REFETCH_MONTHS = 3                        # 월별 지표 재수집 개월 수 (잠정치·개정 반영)
REFETCH_DAYS = 7                          # 일별 지표(환율) 재수집 일수
MAX_PAGES = 20                            # 페이지 반복 상한 (1,000행 × 20 = 일별 50년치 — 무한루프 방지)
NO_DATA_CODES = {"INFO-200"}              # 해당 데이터 없음(미발표) → 오류 아님

COUNTRY = "KR"
SOURCE = "ECOS"

DUPLICATE_KEYS = ["date", "country", "indicator_id"]

# Tier-1 국내 지표 정의
#   item_code: ⚠️ TODO 검증 필요 (위 파일 정의서 참조). 무자료 시 자동 skip.
ECOS_INDICATORS = [
    {
        "indicator_id": "kr_base_rate",
        "stat_code": "722Y001",
        "item_code": "0101000",        # 한국은행 기준금리 (TODO: 항목코드 확인)
        "cycle": "M",
        "indicator_name": "한국은행 기준금리",
        "unit": "%",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_food",
        "stat_code": "901Y009",
        "item_code": "A",             # 식료품 및 비주류음료 (검증: StatisticItemList, 2025-06)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 식료품 및 비주류음료",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_ppi_food",
        "stat_code": "404Y014",
        "item_code": "301AA",         # 음식료품 (식품·음료, 검증: StatisticItemList, 2025-06)
        "cycle": "M",
        "indicator_name": "생산자물가지수 — 음식료품",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_total",
        "stat_code": "901Y009",
        "item_code": "0",            # 총지수 (전체 CPI, 검증: StatisticItemList, 2025-06)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 총지수",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_ccsi",
        "stat_code": "511Y002",
        "item_code": "FME",          # 소비자심리지수 (소비자동향조사 전국 월, 검증 2025-06)
        "cycle": "M",
        "indicator_name": "소비자심리지수(CCSI)",
        "unit": "p (장기평균=100)",
        "freq": "M",
    },
    {
        "indicator_id": "kr_esi",
        "stat_code": "513Y001",
        "item_code": "E1000",        # 경제심리지수(원계열) (검증 2025-06)
        "cycle": "M",
        "indicator_name": "경제심리지수(ESI, 원계열)",
        "unit": "p",
        "freq": "M",
    },
    # ── 수요·유통 지표(2026-07 추가) ─────────────────────────────────────
    #   소비 시장 요인(대형마트 폐업 등 유통 채널 변화·외식 수요·품목별 체감가) 포착용.
    #   판매액·서비스업생산지수는 통계청 발표시차가 커서(현재 ~4개월) 신선도 임계치는 넉넉히 둔다.
    #   항목코드 검증: ECOS StatisticItemList/StatisticSearch 로 월간 데이터 확인(2026-07).
    {
        "indicator_id": "kr_retail_hypermarket",
        "stat_code": "901Y098",
        "item_code": "I74C/I74C",    # 대형마트 / 계절조정지수 (소매업태별 판매액지수)
        "cycle": "M",
        "indicator_name": "소매판매액지수 — 대형마트",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_retail_cvs",
        "stat_code": "901Y098",
        "item_code": "I74J/I74C",    # 편의점 / 계절조정지수
        "cycle": "M",
        "indicator_name": "소매판매액지수 — 편의점",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_retail_dept",
        "stat_code": "901Y098",
        "item_code": "I74B/I74C",    # 백화점 / 계절조정지수
        "cycle": "M",
        "indicator_name": "소매판매액지수 — 백화점",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_service_food",
        "stat_code": "901Y038",
        "item_code": "I51ADB/3",     # 음식점 및 주점업 / 계절조정지수 (서비스업생산지수) — 외식 수요
        "cycle": "M",
        "indicator_name": "서비스업생산지수 — 음식점·주점업",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_beef_imp",
        "stat_code": "901Y009",
        "item_code": "A01202",       # 수입 쇠고기 소비자물가 (삼겹양지 소비 체감가)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 수입 쇠고기",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_beef_dom",
        "stat_code": "901Y009",
        "item_code": "A01201",       # 국산 쇠고기 소비자물가 (한우)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 국산 쇠고기",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_pork",
        "stat_code": "901Y009",
        "item_code": "A01203",       # 돼지고기 소비자물가 (대체수요)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 돼지고기",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    # ── 원가·물류비·외식 소비 지표(2026-10 추가) ──────────────────────────
    #   수입원가: 수입물가 쇠고기(원화=환율 포함 / 계약통화=산지 가격만), 원/호주달러(호주산 원가 축)
    #   물류비: 경유(유류비)·도로화물·냉장냉동창고·외항화물 운임
    #   소비: 외식 물가(전체·쇠고기 외식 = 판매가 전가), 음식료품 소매판매(가정 내 소비량)
    {
        "indicator_id": "kr_impi_beef_krw",
        "stat_code": "401Y017",
        "item_code": "10121201AA/W",  # 쇠고기 / 원화기준 (수입물가지수 품목별)
        "cycle": "M",
        "indicator_name": "수입물가지수 — 쇠고기(원화기준)",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_impi_beef_lc",
        "stat_code": "401Y017",
        "item_code": "10121201AA/C",  # 쇠고기 / 계약통화기준 (환율 효과 제외한 산지 수입단가)
        "cycle": "M",
        "indicator_name": "수입물가지수 — 쇠고기(계약통화기준)",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_fx_aud",
        "stat_code": "731Y001",
        "item_code": "0000017",       # 원/호주달러 (매매기준율)
        "cycle": "D",
        "indicator_name": "원/호주달러 환율(매매기준율)",
        "unit": "원/AUD",
        "freq": "D",
        "country": "KR",              # 원화 측 가격 — KR (호주 산지 지표는 au_* / country='AU')
    },
    {
        "indicator_id": "kr_cpi_diesel",
        "stat_code": "901Y009",
        "item_code": "G02102",        # 경유
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 경유",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_ppi_road_freight",
        "stat_code": "404Y014",
        "item_code": "501122AA",      # 도로화물운송서비스
        "cycle": "M",
        "indicator_name": "생산자물가지수 — 도로화물운송서비스",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_ppi_cold_storage",
        "stat_code": "404Y016",
        "item_code": "50143102AA",    # 냉장및냉동창고운영 (품목별)
        "cycle": "M",
        "indicator_name": "생산자물가지수 — 냉장·냉동창고운영",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_ppi_ocean_freight",
        "stat_code": "404Y016",
        "item_code": "50121201AA",    # 외항화물 (품목별)
        "cycle": "M",
        "indicator_name": "생산자물가지수 — 외항화물",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_dineout",
        "stat_code": "901Y009",
        "item_code": "K011",          # 음식 서비스 (외식 전체)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 외식(음식 서비스)",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_cpi_dineout_beef",
        "stat_code": "901Y009",
        "item_code": "K01110",        # 쇠고기(외식)
        "cycle": "M",
        "indicator_name": "소비자물가지수 — 쇠고기(외식)",
        "unit": "Index 2020=100",
        "freq": "M",
    },
    {
        "indicator_id": "kr_retail_food",
        "stat_code": "901Y100",
        "item_code": "G31/T3",        # 음식료품 / 계절조정지수 (재별·상품군별 판매액지수)
        "cycle": "M",
        "indicator_name": "소매판매액지수 — 음식료품(계절조정)",
        "unit": "Index 2020=100",
        "freq": "M",
    },
]


# --------------------------------------------------------------------------
# 인증 / 유틸
# --------------------------------------------------------------------------
def _get_api_key() -> str | None:
    key = os.getenv("ECOS_API_KEY", "").strip()
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


def _fmt_period(d: date, cycle: str) -> str:
    """ECOS 검색일자 포맷. 월=YYYYMM, 일=YYYYMMDD, 년=YYYY."""
    if cycle == "M":
        return d.strftime("%Y%m")
    if cycle == "D":
        return d.strftime("%Y%m%d")
    if cycle == "A":
        return d.strftime("%Y")
    return d.strftime("%Y%m")


def _next_period_start(last_date: date, cycle: str) -> date:
    """마지막 수집일 다음 주기 시작일."""
    if cycle == "M":
        return (last_date.replace(day=1) + relativedelta(months=1))
    if cycle == "A":
        return date(last_date.year + 1, 1, 1)
    # 일별
    return last_date + relativedelta(days=1)


def _normalize_time(ecos_time: str, cycle: str) -> str | None:
    """ECOS TIME(예: '202401', '20240115')을 표준 date(YYYY-MM-01 / YYYY-MM-DD)로."""
    t = str(ecos_time).strip()
    try:
        if cycle == "M" and len(t) == 6:
            return f"{t[:4]}-{t[4:6]}-01"
        if cycle == "A" and len(t) == 4:
            return f"{t}-01-01"
        if cycle == "D" and len(t) == 8:
            return f"{t[:4]}-{t[4:6]}-{t[6:8]}"
    except Exception:
        return None
    # 길이가 예상과 다르면 pandas 로 best-effort
    dt = pd.to_datetime(t, errors="coerce")
    if pd.isna(dt):
        return None
    return (dt.replace(day=1) if cycle in ("M", "A") else dt).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_indicator(
    api_key: str,
    indicator: dict,
    start: date,
    end: date,
) -> list[dict] | None:
    """long row 리스트 반환. 무자료(INFO-200)면 [], 오류면 None.
    1회 응답 상한(1,000행)을 넘으면 list_total_count 기준으로 페이지를 이어 받는다(일별 환율 백필)."""
    cycle = indicator["cycle"]
    start_p = _fmt_period(start, cycle)
    end_p = _fmt_period(end, cycle)

    rows: list[dict] = []
    for page in range(MAX_PAGES):
        lo = page * MAX_ROWS_PER_CALL + 1
        hi = lo + MAX_ROWS_PER_CALL - 1
        url = (
            f"{BASE_URL}/{api_key}/json/kr/{lo}/{hi}/"
            f"{indicator['stat_code']}/{cycle}/{start_p}/{end_p}/{indicator['item_code']}"
        )
        got = _fetch_page(url, indicator)
        if got is None:
            return None
        page_rows, total = got
        rows.extend(page_rows)
        if not page_rows or len(rows) >= total:
            break
        time.sleep(SLEEP_BETWEEN_CALLS)

    return _to_long_rows(rows, indicator)


def _fetch_page(url: str, indicator: dict) -> tuple[list[dict], int] | None:
    """한 페이지 요청 → (row 리스트, list_total_count). 무자료(INFO-200)면 ([], 0), 오류면 None."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
    except requests.RequestException as e:
        # 예외 메시지에는 인증키가 포함된 URL 이 들어갈 수 있으므로 타입만 출력
        print(f"   └ [예외] {indicator['indicator_id']}: 연결 실패 ({type(e).__name__})")
        return None

    if resp.status_code != 200:
        print(f"   └ [에러] HTTP {resp.status_code} ({indicator['indicator_id']})")
        return None

    try:
        payload = resp.json()
    except ValueError:
        print(f"   └ [에러] JSON 파싱 실패 ({indicator['indicator_id']})")
        return None

    # 오류/무자료: {"RESULT": {"CODE": "INFO-200", "MESSAGE": "..."}}
    if isinstance(payload, dict) and "RESULT" in payload:
        result = payload["RESULT"]
        code = result.get("CODE", "")
        msg = result.get("MESSAGE", "")
        if code in NO_DATA_CODES:
            print(f"   └ [ECOS {code}] {indicator['indicator_id']}: {msg} (미발표 — 정상)")
            return [], 0
        print(f"   └ [ECOS {code}] {indicator['indicator_id']}: {msg} "
              f"(인증키/item_code 확인 필요)")
        return None

    rows: list[dict] = []
    total = 0
    if isinstance(payload, dict) and "StatisticSearch" in payload:
        body = payload["StatisticSearch"]
        rows = body.get("row", []) or []
        try:
            total = int(body.get("list_total_count", len(rows)) or len(rows))
        except (TypeError, ValueError):
            total = len(rows)
    return rows, total


def _to_long_rows(rows: list[dict], indicator: dict) -> list[dict]:
    cycle = indicator["cycle"]
    long_rows: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        raw_value = str(r.get("DATA_VALUE", "")).strip()
        if raw_value in {"", "-"}:
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        norm_date = _normalize_time(r.get("TIME", ""), cycle)
        if norm_date is None:
            continue
        # ECOS 가 단위/항목명을 주면 우선 사용, 없으면 정의 상수
        unit = str(r.get("UNIT_NAME", "") or "").strip() or indicator["unit"]
        long_rows.append({
            "date": norm_date,
            "country": indicator.get("country", COUNTRY),
            "indicator_id": indicator["indicator_id"],
            "indicator_name": indicator["indicator_name"],
            "value": value,
            "unit": unit,
            "freq": indicator["freq"],
            "source": SOURCE,
        })
    return long_rows


# --------------------------------------------------------------------------
# 누적 저장 (공통 raw — FRED 와 공유)
# --------------------------------------------------------------------------
def _merge_and_save(new_rows: list[dict], save_path: Path, windows: dict[str, str]) -> int:
    """windows = {indicator_id: 재수집 시작일} — 해당 indicator 의 시작일 이후 기존 행은 이번 응답으로 교체.
    다른 소스(FRED·KMA) 행은 건드리지 않는다."""
    df_new = pd.DataFrame(new_rows)
    if df_new.empty and not windows:
        return _existing_row_count(save_path)

    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        old_dt = pd.to_datetime(df_old["date"], errors="coerce")
        drop = pd.Series(False, index=df_old.index)
        for iid, start in windows.items():
            drop |= (df_old["indicator_id"] == iid) & (old_dt >= pd.Timestamp(start))
        df_final = pd.concat([df_old[~drop], df_new], ignore_index=True)
    else:
        df_final = df_new

    subset = [c for c in DUPLICATE_KEYS if c in df_final.columns]
    if subset:
        df_final = df_final.drop_duplicates(subset=subset, keep="last")

    df_final["_sort_dt"] = pd.to_datetime(df_final["date"], errors="coerce")
    df_final = df_final.sort_values(
        by=["_sort_dt", "country", "indicator_id"]
    ).drop(columns=["_sort_dt"])

    save_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


def _existing_row_count(save_path: Path) -> int:
    if not save_path.exists():
        return 0
    try:
        return sum(1 for _ in open(save_path, "r", encoding="utf-8-sig")) - 1
    except OSError:
        return 0


def _load_existing(save_path: Path) -> pd.DataFrame:
    """파일이 없으면 빈 DF. 있는데 읽지 못하면 예외 (2019년부터 재수집해 덮어쓰는 사고 방지)."""
    if not save_path.exists():
        return pd.DataFrame()
    return pd.read_csv(save_path, low_memory=False)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_macro_ecos_increment() -> int:
    ensure_dirs()
    save_path = Path(MACRO_RAW_CSV)

    api_key = _get_api_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 ECOS_API_KEY 가 비어 있습니다.\n"
            "         발급 후 입력하면 다음 실행부터 국내 거시지표가 자동 수집됩니다.\n"
            "         발급: https://ecos.bok.or.kr/api/"
        )
        return 0

    try:
        df_existing = _load_existing(save_path)
    except Exception as e:
        print(f"[중단] 기존 raw 를 읽을 수 없습니다 ({type(e).__name__}): {save_path}")
        return 1
    today = date.today()

    new_rows: list[dict] = []
    windows: dict[str, str] = {}
    errors: list[str] = []
    for indicator in ECOS_INDICATORS:
        last_date = _read_last_date(df_existing, indicator["indicator_id"])
        if last_date is None:
            start = INITIAL_START
            print(f"[수집] {indicator['indicator_id']} ({indicator['stat_code']}) "
                  f"— 기존 없음 → {start} 부터 전체")
        else:
            if indicator["cycle"] == "M":
                # 마지막 달 포함 최근 3개월 재수집 (잠정치·개정 반영)
                start = last_date.replace(day=1) - relativedelta(months=REFETCH_MONTHS - 1)
            elif indicator["cycle"] == "D":
                # 일별(환율): 최근 7일 재수집 (영업일 소급 정정 반영)
                start = last_date - relativedelta(days=REFETCH_DAYS)
            else:
                start = _next_period_start(last_date, indicator["cycle"])
            print(f"[수집] {indicator['indicator_id']} ({indicator['stat_code']}) "
                  f"— 마지막 {last_date} → {start} 부터 재수집·증분")

        if start > today:
            print("   └ 이미 최신")
            continue

        rows = _fetch_indicator(api_key, indicator, start, today)
        if rows is None:
            errors.append(indicator["indicator_id"])
        else:
            print(f"   └ 수신 {len(rows)}건")
            new_rows.extend(rows)
            if rows:  # 빈 응답으로 기존 구간을 지우지 않도록, 받은 게 있을 때만 교체
                windows[indicator["indicator_id"]] = start.strftime("%Y-%m-%d")
        time.sleep(SLEEP_BETWEEN_CALLS)

    if new_rows or windows:
        total = _merge_and_save(new_rows, save_path, windows)
        print(f"[완료] ECOS {len(new_rows)}건 반영(최근 구간 교체) — raw 누적 총 {total}건 ({save_path})")
    else:
        print("[안내] ECOS 신규 데이터가 없습니다.")

    if errors:
        print(f"[오류] ECOS 수집 실패 {len(errors)}종 (기존 값 유지): {errors}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(collect_macro_ecos_increment())
