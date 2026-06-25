"""
[파일 정의서]
- 파일명: collect_fas_export_sales.py
- 역할: 수집
- 대상: 미국 소고기(beef) 국가별 주간 수출선약 (덤핑/다이버전 조기경보)
- 데이터 소스: USDA FAS Export Sales (ESR) Open Data API (공식 Swagger 검증)
    https://apps.fas.usda.gov/OpenData/api/esr/...   (인증: 헤더 API_KEY)
    키 발급: FAS Open Data Portal https://apps.fas.usda.gov/opendatawebv2/ (가입 → API Keys)
- 수집/가공 주기: 주간(증분) — marketYear 단위 조회
- 주요 기능:
    1. .env(FAS_API_KEY) 로딩. 키 없으면 즉시 graceful skip
    2. ⚠️ 상품·국가 코드를 하드코딩하지 않고 /commodities, /countries 로 런타임 조회
       → beef 상품코드, China / Korea, South 국가코드를 응답에서 직접 찾음(할루시네이션 방지)
    3. marketYear 2019~현재 범위로 beef 수출 주간 데이터 수집 → 국가별 long format 저장
    4. 검증 포인트: 중국행 급감 / 한국행 급증 = 덤핑 다이버전 조기경보

산출 컬럼(long) — data/0_raw/fas_export_sales_raw.csv:
    week_ending, market_year, commodity_code, commodity_name,
    country_code, country_name, weekly_exports, outstanding_sales,
    gross_new_sales, current_my_net_sales, current_my_total_commitment, unit

주의: FAS ESR API는 2026년 전후로 엔드포인트 마이그레이션 중이다. 본 수집기는 실제 호출로 확인한
      base(https://api.fas.usda.gov/api/esr) 기준이며, exports 경로는 첫 실제 응답으로 검증 후 고정한다.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import FAS_EXPORT_SALES_CSV, ensure_dirs

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False

load_dotenv()

BASE_URL = "https://api.fas.usda.gov/api/esr"  # 실호출 검증: 신 게이트웨이 (인증: ?api_key= 쿼리). 구 apps.fas/OpenData 는 500(폐기)
INITIAL_MARKET_YEAR = 2019
REQUEST_TIMEOUT = 30
SLEEP = 0.4

# 응답에서 찾을 대상 (이름 기반 매칭 — 코드는 런타임 조회)
BEEF_NAME_KEYS = ("beef",)              # commodityName 에 'beef' 포함

DUPLICATE_KEYS = ["week_ending", "commodity_code", "country_code"]


def _get_api_key() -> str | None:
    return os.getenv("FAS_API_KEY", "").strip() or None


def _get(path: str, api_key: str, params: dict | None = None):
    """FAS API GET. 인증은 헤더 API_KEY (공식 스펙). 키 노출 방지 위해 에러엔 경로만 출력."""
    url = f"{BASE_URL}/{path.lstrip('/')}"
    p = {"api_key": api_key}
    if params:
        p.update(params)
    last_err = None
    for attempt in range(3):  # 사내망 ProxyError 등 일시 오류 재시도
        try:
            r = requests.get(url, params=p, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL,
                             headers={"Accept": "application/json", "X-Api-Key": api_key})
        except requests.RequestException as e:
            last_err = type(e).__name__
            time.sleep(1.0)
            continue
        if r.status_code != 200:
            print(f"   └ [에러] HTTP {r.status_code} ({path}) — 키/엔드포인트 확인 필요")
            return None
        try:
            return r.json()
        except ValueError:
            print(f"   └ [에러] JSON 파싱 실패 ({path})")
            return None
    print(f"   └ [예외] {path}: 연결 실패 ({last_err}) — 재시도 초과")
    return None


def _find_beef_commodities(api_key: str) -> list[dict]:
    data = _get("commodities", api_key)
    if not isinstance(data, list):
        return []
    out = []
    for c in data:
        name = str(c.get("commodityName", "")).lower()
        if any(k in name for k in BEEF_NAME_KEYS):
            out.append({"code": c.get("commodityCode"), "name": c.get("commodityName")})
    return out


def _find_target_countries(api_key: str) -> dict[int, str]:
    """중국 본토 / 대한민국을 국가명에서 견고하게 탐색 (홍콩·대만·북한 제외)."""
    data = _get("countries", api_key)
    if not isinstance(data, list):
        return {}
    mapping = {}
    for c in data:
        # 전체명은 countryDescription 에 있음 (countryName 은 'KOR REP' 식 약어)
        nm = (str(c.get("countryDescription", "")) + " " + str(c.get("countryName", ""))).strip().lower()
        code = c.get("countryCode")
        if "china" in nm and not any(x in nm for x in ("hong", "taiwan", "macau", "macao")):
            mapping[code] = "중국"
        elif "korea" in nm and not any(x in nm for x in ("dem", "dpr", "d.p.r", "people", "no kor")):
            mapping[code] = "한국"
    return mapping


def _fetch_exports(api_key: str, commodity_code, country_code, market_year: int) -> list[dict]:
    # 공식 Swagger 경로: /exports/commodityCode/{cc}/countryCode/{cn}/marketYear/{yyyy}
    path = f"exports/commodityCode/{commodity_code}/countryCode/{country_code}/marketYear/{market_year}"
    data = _get(path, api_key)
    return data if isinstance(data, list) else []


def _merge_and_save(rows: list[dict], save_path: Path) -> int:
    df_new = pd.DataFrame(rows)
    if df_new.empty:
        return _count(save_path)
    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    sub = [c for c in DUPLICATE_KEYS if c in df.columns]
    if sub:
        df = df.drop_duplicates(subset=sub, keep="last")
    df["_dt"] = pd.to_datetime(df["week_ending"], errors="coerce")
    df = df.sort_values(["_dt", "country_code"]).drop(columns=["_dt"])
    save_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(str(save_path), index=False, encoding="utf-8-sig")
    return len(df)


def _count(p: Path) -> int:
    if not p.exists():
        return 0
    try:
        return sum(1 for _ in open(p, "r", encoding="utf-8-sig")) - 1
    except OSError:
        return 0


def collect_fas_export_sales() -> None:
    ensure_dirs()
    save_path = Path(FAS_EXPORT_SALES_CSV)
    api_key = _get_api_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 FAS_API_KEY 가 비어 있습니다.\n"
            "         발급(무료): https://api.fas.usda.gov  → .env 에 FAS_API_KEY=... 입력"
        )
        return

    print("[FAS] 상품/국가 코드 런타임 조회 중...")
    beefs = _find_beef_commodities(api_key)
    countries = _find_target_countries(api_key)
    if not beefs:
        print("[중단] beef 상품코드를 찾지 못했습니다 (인증 실패 또는 엔드포인트 변경 가능).")
        return
    if not countries:
        print("[중단] 중국/한국 국가코드를 찾지 못했습니다 (countries 응답 확인 필요).")
        return
    print(f"   └ beef 상품: {beefs}")
    print(f"   └ 대상 국가: {countries}")

    this_year = date.today().year
    market_years = list(range(INITIAL_MARKET_YEAR, this_year + 1))

    rows: list[dict] = []
    for b in beefs:
        cc, cname = b["code"], b["name"]
        for ccode, cnm in countries.items():
            for my in market_years:
                recs = _fetch_exports(api_key, cc, ccode, my)
                for r in recs:
                    rows.append({
                        "week_ending": r.get("weekEndingDate"),
                        "market_year": my,
                        "commodity_code": cc,
                        "commodity_name": cname,
                        "country_code": ccode,
                        "country_name": cnm,
                        "weekly_exports": r.get("weeklyExports"),
                        "outstanding_sales": r.get("outstandingSales"),
                        "gross_new_sales": r.get("grossNewSales"),
                        "current_my_net_sales": r.get("currentMYNetSales"),
                        "current_my_total_commitment": r.get("currentMYTotalCommitment"),
                        "unit": r.get("unitId"),
                    })
                time.sleep(SLEEP)
        print(f"   └ '{cname}' 수집 누적 {len(rows)} rows")

    if not rows:
        print("[안내] 수집된 FAS 데이터가 없습니다 (엔드포인트/코드 확인 필요).")
        return

    total = _merge_and_save(rows, save_path)
    print(f"[완료] FAS 신규 {len(rows)}건 병합 — 누적 {total}건 ({save_path})")


if __name__ == "__main__":
    collect_fas_export_sales()
