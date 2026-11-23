"""
[파일 정의서]
- 파일명: collect_us_export_gats.py
- 역할: 수집
- 대상: 미국 → 한국 소고기 월간 수출 실적 (HS10 세분류, 물량 kg · 금액 USD) — 미국 통관(Census) 기준
- 데이터 소스: USDA FAS GATS OpenData API (2026-11 실호출 검증)
    https://api.fas.usda.gov/api/gats/censusExports/partnerCode/KS/year/{YYYY}/month/{M}
    인증: 헤더 X-Api-Key (.env 의 FAS_API_KEY — collect_fas_export_sales.py 와 같은 키)
    ※ 한국 파트너 코드는 'KS' (KR 아님). 응답은 전 품목(~700행/월)이며 소고기(HS 0201*/0202*)만 걸러 저장.
    공표 일정(참고): /api/gats/census/data/exports/dataReleaseDates — 당월분은 월말 후 약 35일 뒤 공개
    제공 이력: 1995-01 ~
- 수집/가공 주기: 월간(증분) — 매 실행 시 (기존 마지막 월 - 3개월) ~ 이번 달을 다시 받아 해당 월 행을 교체(정정분 반영)
- 주요 기능:
    1. .env(FAS_API_KEY) 로딩. 키 없으면 즉시 graceful skip(exit 0)
    2. 최초 실행 시 2019-01 부터, --backfill-from YYYY-MM 지정 시 그 달부터 전부 재수집(예: 1995-01 → 약 380회 호출)
    3. 미공표 월은 HTTP 200 + 빈 배열([]) 로 응답 → 정상(exit 0). 이번 달·직전 달이 비는 것이 보통이다.
    4. 응답 필드(실측): date('YYYYMM'), countryCode, hS10Code, censusUOMId1(47=kg), quantity1(kg), quantity2, value(USD)
       → 품목 설명 필드는 없음 (hs_desc 는 빈 문자열로 저장)
    5. 파생 컬럼: chilled(0201=냉장 True / 0202=냉동 False),
       bone_in(5~6번째 자리 10=지육(carcass)·20=골부 → True, 30=정육(boneless) → False),
       unit_value_usd_kg = value / qty_kg
       ※ 지육 코드(0201100010/0090, 0202100010/0090)와 구 코드(0201203000/303000, 0202203000/303000)는 1990~2000년대 이력에만 등장
    8. 참고: 2004-01 ~ 2006-08 (32개월) 은 미국 BSE 로 한국 수입 금지 → 소고기 행이 없다(결측 아닌 실제 0건)
    6. 실패 처리: 네트워크 예외 / HTTP 200 이외(429 는 백오프 재시도 후) / JSON 파싱 실패 = 오류 집계
       → 받은 만큼 저장 후 exit 1. 기존 CSV 를 읽을 수 없으면 재수집하지 않고 중단(exit 1).
    7. 레이트리밋(실측 헤더 X-Ratelimit-Limit: 1000) — 호출 간 0.3초 대기, 429 수신 시 5·15·45초 백오프

산출 컬럼 — data/0_raw/us_export_korea_gats.csv:
    date(YYYY-MM-01), hs10, hs_desc, chilled, bone_in, qty_kg, value_usd, unit_value_usd_kg, source('FAS_GATS')

사용법:
    python src/collectors/collect_us_export_gats.py                       # 증분(최근 3개월 재수집)
    python src/collectors/collect_us_export_gats.py --backfill-from 1995-01   # 장기 이력 백필
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from config import DATA_RAW, PROJECT_ROOT, ensure_dirs  # noqa: E402
from utils.io_safe import atomic_to_csv  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
VERIFY_SSL = False   # 사내망 TLS 프록시 (기존 수집기와 동일 패턴)

load_dotenv(PROJECT_ROOT / ".env")

# config.py 에 상수가 추가되기 전에도 동작하도록 fallback (상수명: US_EXPORT_GATS_CSV)
SAVE_PATH = Path(getattr(config, "US_EXPORT_GATS_CSV", DATA_RAW / "us_export_korea_gats.csv"))

BASE_URL = "https://api.fas.usda.gov/api/gats/censusExports/partnerCode/KS/year/{year}/month/{month}"
INITIAL_START = (2019, 1)
REFETCH_MONTHS = 3          # 매 실행 재수집하는 최근 월 수 (정정분 반영)
REQUEST_TIMEOUT = 60
SLEEP = 0.3                 # 호출 간 대기(초)
RETRY_429_BACKOFF = (5, 15, 45)
BEEF_HS_PREFIXES = ("0201", "0202")
BONE_IN_SUBHEADINGS = ("10", "20")   # HS 5~6자리: 10=지육(carcass), 20=골부(bone-in) → True / 30=정육(boneless) → False
KG_UOM_ID = 47
DUPLICATE_KEYS = ["date", "hs10"]
OUTPUT_COLUMNS = ["date", "hs10", "hs_desc", "chilled", "bone_in",
                  "qty_kg", "value_usd", "unit_value_usd_kg", "source"]

_ERRORS: list[str] = []
_printed_sample = False


class ExistingFileError(RuntimeError):
    pass


def _get_api_key() -> str | None:
    return os.getenv("FAS_API_KEY", "").strip() or None


def _read_last_month(save_path: Path) -> tuple[int, int] | None:
    """기존 파일의 마지막 (year, month). 파일 없으면 None, 읽기 실패면 ExistingFileError."""
    if not save_path.exists():
        return None
    try:
        df = pd.read_csv(save_path, usecols=["date"], low_memory=False)
    except Exception as e:
        raise ExistingFileError(f"기존 파일을 읽을 수 없습니다 ({type(e).__name__}: {e})")
    parsed = pd.to_datetime(df["date"], errors="coerce").dropna()
    if parsed.empty:
        raise ExistingFileError("기존 파일에 유효한 date 가 없습니다")
    last = parsed.max()
    return int(last.year), int(last.month)


def _shift_month(ym: tuple[int, int], delta: int) -> tuple[int, int]:
    y, m = ym
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def _month_range(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur = _shift_month(cur, 1)
    return out


def _fetch_month(api_key: str, year: int, month: int) -> list[dict] | None:
    """해당 월 전 품목 레코드 리스트. 오류(네트워크·HTTP·파싱)면 None, 미공표면 []."""
    url = BASE_URL.format(year=year, month=month)
    headers = {"Accept": "application/json", "X-Api-Key": api_key}
    last_err = None
    backoff_i = 0
    for attempt in range(6):
        try:
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        except requests.RequestException as e:
            last_err = type(e).__name__
            print(f"   └ [예외] 연결 실패 ({last_err}) — 재시도 {attempt + 1}")
            time.sleep(2 + attempt)
            continue
        if r.status_code == 429:
            if backoff_i >= len(RETRY_429_BACKOFF):
                print("   └ [에러] HTTP 429 (레이트리밋) — 백오프 재시도 초과")
                _ERRORS.append(f"HTTP 429 {year}-{month:02d}")
                return None
            wait = RETRY_429_BACKOFF[backoff_i]
            backoff_i += 1
            retry_after = r.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = max(wait, int(retry_after))
            print(f"   └ [대기] HTTP 429 레이트리밋 — {wait}초 후 재시도")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            print(f"   └ [에러] HTTP {r.status_code} ({year}-{month:02d})")
            _ERRORS.append(f"HTTP {r.status_code} {year}-{month:02d}")
            return None
        try:
            payload = r.json()
        except ValueError:
            print(f"   └ [에러] JSON 파싱 실패 ({year}-{month:02d})")
            _ERRORS.append(f"JSON {year}-{month:02d}")
            return None
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return payload["data"]
        print(f"   └ [에러] 예상 밖 응답 형식 ({type(payload).__name__}) ({year}-{month:02d})")
        _ERRORS.append(f"FORMAT {year}-{month:02d}")
        return None
    print(f"   └ [예외] 연결 실패 ({last_err}) — 재시도 초과 ({year}-{month:02d})")
    _ERRORS.append(f"연결 실패 {year}-{month:02d}")
    return None


def _hs10(rec: dict) -> str:
    code = rec.get("hS10Code", rec.get("hs10Code", rec.get("HS10Code", "")))
    return str(code).strip().zfill(10) if code not in (None, "") else ""


def _to_beef_rows(records: list[dict], year: int, month: int) -> list[dict]:
    """전 품목 응답에서 소고기(0201*/0202*)만 추출해 산출 스키마로 변환."""
    global _printed_sample
    if records and not _printed_sample:
        print(f"   └ [참고] 원본 레코드 예시: {records[0]}")
        _printed_sample = True
    date_str = f"{year:04d}-{month:02d}-01"
    rows = []
    for rec in records:
        hs = _hs10(rec)
        if not hs.startswith(BEEF_HS_PREFIXES):
            continue
        uom = rec.get("censusUOMId1")
        if uom is not None and int(uom) != KG_UOM_ID:
            print(f"   └ [경고] {hs} 의 수량 단위 ID={uom} (kg=47 아님) — 단가 해석 주의")
        qty = rec.get("quantity1")
        val = rec.get("value")
        qty_f = float(qty) if qty is not None else float("nan")
        val_f = float(val) if val is not None else float("nan")
        unit_val = val_f / qty_f if qty_f and qty_f > 0 else float("nan")
        rows.append({
            "date": date_str,
            "hs10": hs,
            "hs_desc": str(rec.get("hS10Description", rec.get("description", "")) or ""),
            "chilled": hs.startswith("0201"),
            "bone_in": hs[4:6] in BONE_IN_SUBHEADINGS,
            "qty_kg": qty_f,
            "value_usd": val_f,
            "unit_value_usd_kg": round(unit_val, 4) if unit_val == unit_val else unit_val,
            "source": "FAS_GATS",
        })
    return rows


def _merge_and_save(new_rows: list[dict], replaced_months: set[str], save_path: Path) -> int:
    """replaced_months(YYYY-MM-01) 에 해당하는 기존 행은 통째로 제거하고 새 행으로 교체."""
    df_new = pd.DataFrame(new_rows, columns=OUTPUT_COLUMNS)
    if save_path.exists():
        df_old = pd.read_csv(save_path, low_memory=False, dtype={"hs10": str})
        old_dt = pd.to_datetime(df_old["date"], errors="coerce").dt.strftime("%Y-%m-01")
        df_final = pd.concat([df_old[~old_dt.isin(replaced_months)], df_new], ignore_index=True)
    else:
        df_final = df_new
    df_final["hs10"] = df_final["hs10"].astype(str).str.zfill(10)
    df_final = df_final.drop_duplicates(subset=DUPLICATE_KEYS, keep="last")
    df_final["_dt"] = pd.to_datetime(df_final["date"], errors="coerce")
    df_final = df_final.sort_values(["_dt", "hs10"]).drop(columns=["_dt"])
    df_final = df_final[OUTPUT_COLUMNS]
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


def collect_us_export_gats(backfill_from: tuple[int, int] | None = None) -> int:
    """backfill_from=(year, month): 지정하면 그 달부터 이번 달까지 전부 다시 받아 해당 월 행을 교체."""
    ensure_dirs()
    save_path = SAVE_PATH
    api_key = _get_api_key()
    if api_key is None:
        print(
            "[건너뜀] .env 의 FAS_API_KEY 가 비어 있습니다.\n"
            "         발급(무료): https://api.fas.usda.gov  → .env 에 FAS_API_KEY=... 입력"
        )
        return 0

    try:
        last_ym = _read_last_month(save_path)
    except ExistingFileError as e:
        print(f"[중단] {e}: {save_path}")
        print("        처음부터 재수집하지 않습니다. 파일을 확인/복구한 뒤 다시 실행하세요.")
        return 1

    now = datetime.now()
    this_ym = (now.year, now.month)
    if backfill_from is not None:
        start = backfill_from
        print(f"[시스템] 백필 모드 → {start[0]}-{start[1]:02d} 부터 전체 재수집 (기존 동일 월 행 교체)")
    elif last_ym is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {start[0]}-{start[1]:02d} 부터 전체 수집")
    else:
        start = _shift_month(last_ym, -REFETCH_MONTHS)
        print(f"[시스템] 기존 데이터 마지막 월: {last_ym[0]}-{last_ym[1]:02d} → "
              f"{start[0]}-{start[1]:02d} 부터 증분 수집 (최근 {REFETCH_MONTHS}개월 재수집)")

    months = _month_range(start, this_ym)
    if not months:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return 0
    print(f"[안내] 요청 월 {len(months)}건 ({months[0][0]}-{months[0][1]:02d} ~ {months[-1][0]}-{months[-1][1]:02d})")

    new_rows: list[dict] = []
    replaced_months: set[str] = set()
    empty_months: list[str] = []
    for i, (y, m) in enumerate(months, 1):
        label = f"{y}-{m:02d}"
        verbose = len(months) <= 24 or i % 12 == 1 or i == len(months)
        if verbose:
            print(f" - [{i}/{len(months)}] {label}")
        records = _fetch_month(api_key, y, m)
        if records is None:
            pass  # 오류는 _ERRORS 에 집계됨
        elif records:
            beef = _to_beef_rows(records, y, m)
            replaced_months.add(f"{y:04d}-{m:02d}-01")
            new_rows.extend(beef)
            if verbose:
                print(f"   └ 전품목 {len(records)}행 중 소고기 {len(beef)}행")
        else:
            empty_months.append(label)   # 미공표 → 정상
            if verbose:
                print("   └ 데이터 없음 (미공표)")
        time.sleep(SLEEP)

    if empty_months:
        print(f"[안내] 미공표(빈 응답) 월: {', '.join(empty_months)}")

    if replaced_months:
        total = _merge_and_save(new_rows, replaced_months, save_path)
        print(f"[완료] 소고기 {len(new_rows)}행 ({len(replaced_months)}개월) 병합 — 누적 총 {total}행 ({save_path})")
    else:
        print("[안내] API 에서 신규 데이터가 반환되지 않았습니다.")

    if _ERRORS:
        print(f"[오류] 요청 {len(_ERRORS)}건 실패 — 받은 데이터만 저장했습니다: {_ERRORS[:5]}")
        return 1
    return 0


def _parse_ym(s: str) -> tuple[int, int]:
    dt = datetime.strptime(s.strip(), "%Y-%m")
    return dt.year, dt.month


if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(description="USDA FAS GATS 미국→한국 소고기 월간 수출(HS10) 증분 수집")
    _ap.add_argument("--backfill-from", help="YYYY-MM — 이 달부터 전부 다시 받아 교체(장기 이력 확장, 최소 1995-01)")
    _a = _ap.parse_args()
    _bf = _parse_ym(_a.backfill_from) if _a.backfill_from else None
    sys.exit(collect_us_export_gats(_bf))
