"""
[파일 정의서]
- 파일명: collect_kr_customs_beef.py
- 역할: 수집
- 대상: 국가별 × HSK10 쇠고기 수입 실적 (월별 중량 kg · 금액 USD) — 관세청 수출입무역통계
- 데이터 소스: 공공데이터포털 '관세청_품목별 국가별 수출입실적' (data.go.kr 15100475)
    https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList  (XML)
    인증키: .env 의 EKAPE_API_KEY (공공데이터포털 공용 키 — 한우 경락가 수집기와 같은 키, 디코딩된 원문 그대로 전달)
- 수집/가공 주기: 월단위 — 관세청은 매월 15일 전후에 전전월(例: 11월 중순 → 9월 확정, 10월 잠정) 자료를 게시
- 주요 기능:
    1. HS 6단위(020120/020130/020220/020230)로 요청하면 HSK 10단위 하위 행이 돌아온다 (4단위 요청은 6단위만 반환).
       대상 HSK10: 0202201000(냉동 갈비) 0202209000(냉동 기타 뼈있는) 0202300000(냉동 뼈없는)
                   0201201000(냉장 갈비) 0201209000(냉장 기타 뼈있는) 0201300000(냉장 뼈없는)
    2. cntyCd 를 생략하면 '모든 국가'가 statCd(ISO2)별로 분해되어 돌아온다 → 호출 수 = 연도 × HS6 (국가 루프 불필요).
       저장은 전 국가 (US/AU/NZ/CA/MX 외 기타 국가 포함). 응답 첫 행(year='총계', hsCd='-')은 기간 합계이므로 버린다.
       중량·금액이 모두 0 인 자리표시 행도 버린다.
       ※ 세번 이력: 2008-12 까지는 뼈있는 것이 0201200000/0202200000 하나였고 2009-01 부터 갈비(…201000)/기타(…209000)로 분리.
    3. 요청 구간은 12개월 이하만 허용(13개월 → resultCode 99) → 12개월 청크로 분할 호출.
    4. 증분: 기존 파일의 마지막 월부터 REFETCH_MONTHS(4)개월 전까지 다시 받아 그 구간(월×HS6)의 기존 행을 통째로 교체
       (정정·지연 게시 자가 치유). 아직 게시되지 않은 월은 빈 items → 정상(exit 0).
    5. 최초 실행은 2019-01부터. `--backfill-from YYYY-MM` 으로 장기 이력 확장 (관세청 자료는 1995-01부터 존재).
    6. 실패 처리: 네트워크 예외 / HTTP 200 이외 / XML 파싱 실패 / resultCode 00·03 이외 = 오류 집계 →
       받은 만큼 저장 후 exit 1. 트래픽 초과·인증키 오류(20/22/30/31/32)는 이후 호출도 모두 실패하므로 즉시 중단.
       인증키 미설정 → 건너뜀(exit 0). 기존 CSV 를 읽지 못하면 재수집하지 않고 중단(exit 1).

산출 컬럼 (data/0_raw/kr_customs_beef_import.csv):
    date(YYYY-MM-01), country(ISO2), country_kor, hs10, hs_desc(statKor), chilled(0201→True),
    bone_in(HS 5~6자리 '20'→True / '30'→False), rib(0202201000·0201201000→True),
    imp_kg, imp_usd, unit_value_usd_kg(imp_usd/imp_kg), source('KCS')
"""

from __future__ import annotations

import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, PROJECT_ROOT, ensure_dirs
from utils.io_safe import atomic_to_csv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv(PROJECT_ROOT / ".env")

# config.py 에 KR_CUSTOMS_BEEF_CSV 가 정의되면 그것을 우선 사용
try:
    from config import KR_CUSTOMS_BEEF_CSV as _SAVE_PATH
except ImportError:
    _SAVE_PATH = DATA_RAW / "kr_customs_beef_import.csv"

API_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
HS6_CODES = ["020120", "020130", "020220", "020230"]   # 냉장 뼈있는/뼈없는, 냉동 뼈있는/뼈없는
RIB_HS10 = {"0202201000", "0201201000"}
INITIAL_START = (2019, 1)       # 최초 수집 시작 (연, 월)
EARLIEST_AVAILABLE = (1995, 1)  # 관세청 통계 제공 시작
REFETCH_MONTHS = 4              # 매 실행 재수집·교체하는 최근 월수 (정정분 반영)
MAX_WINDOW_MONTHS = 12          # API 허용 최대 요청 구간
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_CALLS = 0.3
DUPLICATE_KEYS = ["date", "country", "hs10"]
OUTPUT_COLUMNS = ["date", "country", "country_kor", "hs10", "hs_desc", "chilled", "bone_in", "rib",
                  "imp_kg", "imp_usd", "unit_value_usd_kg", "source"]

# 공공데이터포털 표준 오류코드 중 이후 호출이 모두 실패하는 '중단형'
#   20 SERVICE_ACCESS_DENIED / 22 트래픽 초과 / 30 미등록 키 / 31 기한 만료 / 32 미등록 IP
STOP_CODES = {"20", "22", "30", "31", "32"}
NODATA_CODES = {"00", "03"}     # 03 = NODATA_ERROR (자료 없음) → 정상
STOP_MSG_PATTERN = re.compile(r"LIMITED_NUMBER|EXCEEDS|ACCESS_DENIED|SERVICE_KEY|DEADLINE|UNREGISTERED|서비스키|트래픽",
                              re.IGNORECASE)


class ExistingFileError(RuntimeError):
    pass


class ApiStopError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# 유틸
# --------------------------------------------------------------------------
def _ym_add(ym: tuple[int, int], n: int) -> tuple[int, int]:
    y, m = ym
    idx = y * 12 + (m - 1) + n
    return idx // 12, idx % 12 + 1


def _ym_str(ym: tuple[int, int]) -> str:
    return f"{ym[0]:04d}{ym[1]:02d}"


def _ym_date(ym: tuple[int, int]) -> str:
    return f"{ym[0]:04d}-{ym[1]:02d}-01"


def _months_between(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur = _ym_add(cur, 1)
    return out


def _generate_windows(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """12개월 이하 청크로 분할 (API 제한)."""
    windows, cur = [], start
    while cur <= end:
        w_end = min(_ym_add(cur, MAX_WINDOW_MONTHS - 1), end)
        windows.append((cur, w_end))
        cur = _ym_add(w_end, 1)
    return windows


def _read_last_month(save_path: Path) -> tuple[int, int] | None:
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
    return last.year, last.month


def _to_int(text: str | None) -> int | None:
    if text is None:
        return None
    t = text.strip().replace(",", "")
    if not t or t == "-":
        return None
    try:
        return int(float(t))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# API 호출
# --------------------------------------------------------------------------
def _fetch_window(key: str, hs6: str, start: tuple[int, int], end: tuple[int, int]) -> list[dict] | None:
    """해당 구간·HS6 의 전 국가 10단위 행을 dict 리스트로 반환.
    오류(네트워크·HTTP·파싱·오류코드)면 None, 자료 없음이면 []. 중단형 오류는 ApiStopError."""
    params = {"serviceKey": key, "strtYymm": _ym_str(start), "endYymm": _ym_str(end), "hsSgn": hs6}
    response = None
    for attempt in range(3):
        try:
            response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT, verify=False)
            if response.status_code >= 500:
                print(f"   └ [예외] 서버 오류 HTTP {response.status_code} — 재시도 {attempt + 1}/3")
                response = None
                time.sleep(3 + attempt * 2)
                continue
            break
        except requests.RequestException as e:
            print(f"   └ [예외] 연결 실패 ({type(e).__name__}) — 재시도 {attempt + 1}/3")
            time.sleep(2 + attempt)
    if response is None:
        return None
    if response.status_code == 429:
        raise ApiStopError("HTTP 429 — 일일 트래픽 초과")
    if response.status_code != 200:
        print(f"   └ [에러] 상태 코드 {response.status_code}")
        return None

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        print(f"   └ [에러] XML 파싱 실패: {response.text[:200]!r}")
        return None

    code = (root.findtext(".//resultCode") or root.findtext(".//returnReasonCode") or "").strip()
    msg = (root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg") or "").strip()
    if code in STOP_CODES or (code not in NODATA_CODES and STOP_MSG_PATTERN.search(msg)):
        raise ApiStopError(f"resultCode={code} {msg}")
    if code not in NODATA_CODES:
        print(f"   └ [에러] resultCode={code} {msg}")
        return None

    rows: list[dict] = []
    for item in root.iter("item"):
        year = (item.findtext("year") or "").strip()
        hs10 = (item.findtext("hsCd") or "").strip()
        cnty = (item.findtext("statCd") or "").strip()
        # 기간 합계 행(year='총계', hsCd='-') 및 비정상 행 제외
        if not re.fullmatch(r"\d{4}\.\d{2}", year) or not re.fullmatch(r"\d{10}", hs10) or not cnty or cnty == "-":
            continue
        imp_kg = _to_int(item.findtext("impWgt"))
        imp_usd = _to_int(item.findtext("impDlr"))
        # 값 없음 또는 0/0 자리표시 행(한 번이라도 수입한 국가는 이후 모든 월에 0행이 붙음) 제외
        if (imp_kg is None and imp_usd is None) or ((imp_kg or 0) == 0 and (imp_usd or 0) == 0):
            continue
        rows.append({
            "date": f"{year[:4]}-{year[5:7]}-01",
            "country": cnty,
            "country_kor": (item.findtext("statCdCntnKor1") or "").strip(),
            "hs10": hs10,
            "hs_desc": (item.findtext("statKor") or "").strip(),
            "chilled": hs10.startswith("0201"),
            "bone_in": hs10[4:6] == "20",
            "rib": hs10 in RIB_HS10,
            "imp_kg": imp_kg,
            "imp_usd": imp_usd,
            "source": "KCS",
        })
    return rows


# --------------------------------------------------------------------------
# 병합·저장
# --------------------------------------------------------------------------
def _merge_and_save(new_rows: list[dict], covered: set[tuple[str, str]], save_path: Path) -> int:
    """covered = 성공적으로 받은 (date, hs6) 집합 — 그 구간의 기존 행은 통째로 교체(삭제된 국가 행도 반영)."""
    df_new = pd.DataFrame(new_rows, columns=[c for c in OUTPUT_COLUMNS if c != "unit_value_usd_kg"])
    if save_path.exists():
        df_old = pd.read_csv(save_path, dtype={"hs10": str, "country": str}, low_memory=False)
        old_key = list(zip(df_old["date"].astype(str), df_old["hs10"].astype(str).str[:6]))
        keep = [k not in covered for k in old_key]
        df_final = pd.concat([df_old[keep], df_new], ignore_index=True)
    else:
        df_final = df_new

    df_final = df_final.drop_duplicates(subset=DUPLICATE_KEYS, keep="last")
    df_final["imp_kg"] = pd.to_numeric(df_final["imp_kg"], errors="coerce")
    df_final["imp_usd"] = pd.to_numeric(df_final["imp_usd"], errors="coerce")
    kg = df_final["imp_kg"].where(df_final["imp_kg"] > 0)
    df_final["unit_value_usd_kg"] = (df_final["imp_usd"] / kg).round(4)
    df_final = df_final[OUTPUT_COLUMNS].sort_values(["date", "hs10", "country"]).reset_index(drop=True)
    atomic_to_csv(df_final, save_path, index=False, encoding="utf-8-sig")
    return len(df_final)


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def collect_customs_increment(backfill_from: tuple[int, int] | None = None) -> int:
    """backfill_from=(연,월) 을 주면 그 월부터 현재까지 전부 다시 받아 해당 구간을 교체 (예: --backfill-from 1995-01)."""
    ensure_dirs()
    save_path = Path(_SAVE_PATH)

    key = os.getenv("EKAPE_API_KEY", "").strip()
    if not key:
        print("[건너뜀] .env 의 EKAPE_API_KEY(공공데이터포털 키)가 비어 있어 관세청 수입실적 수집을 생략합니다.")
        return 0

    try:
        last_month = _read_last_month(save_path)
    except ExistingFileError as e:
        print(f"[중단] {e}: {save_path}")
        print("        처음부터 재수집하지 않습니다. 파일을 확인/복구한 뒤 다시 실행하세요.")
        return 1

    now = datetime.now()
    end = (now.year, now.month)   # 당월까지 요청 (미게시 월은 빈 응답 → 정상)

    if backfill_from is not None:
        start = max(backfill_from, EARLIEST_AVAILABLE)
        print(f"[시스템] 백필 모드 → {_ym_date(start)[:7]}부터 전체 재수집 (기존 동일 구간 행 교체)")
    elif last_month is None:
        start = INITIAL_START
        print(f"[시스템] 기존 데이터 없음 → {_ym_date(start)[:7]}부터 전체 수집")
    else:
        start = _ym_add(last_month, -(REFETCH_MONTHS - 1))
        print(f"[시스템] 기존 데이터 마지막 월: {_ym_date(last_month)[:7]} → {_ym_date(start)[:7]}부터 증분 수집 "
              f"(최근 {REFETCH_MONTHS}개월 재수집)")

    if start > end:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return 0

    windows = _generate_windows(start, end)
    total_calls = len(windows) * len(HS6_CODES)
    print(f"[안내] 요청 구간 {len(windows)}개 × HS6 {len(HS6_CODES)}개 = 호출 {total_calls}회 "
          f"({_ym_date(start)[:7]} ~ {_ym_date(end)[:7]}, 전 국가)")

    new_rows: list[dict] = []
    covered: set[tuple[str, str]] = set()
    errors = 0
    calls = 0
    stopped = False
    try:
        for i, (ws, we) in enumerate(windows, 1):
            for hs6 in HS6_CODES:
                calls += 1
                print(f" - [{calls}/{total_calls}] {_ym_date(ws)[:7]} ~ {_ym_date(we)[:7]} HS {hs6}")
                rows = _fetch_window(key, hs6, ws, we)
                if rows is None:
                    errors += 1
                else:
                    covered.update((_ym_date(m), hs6) for m in _months_between(ws, we))
                    if rows:
                        print(f"   └ 수집: {len(rows)}건")
                        new_rows.extend(rows)
                    else:
                        print("   └ 자료 없음 (미게시 월)")
                time.sleep(SLEEP_BETWEEN_CALLS)
    except ApiStopError as e:
        print(f"[중단] 이후 호출이 모두 실패하는 오류 → 즉시 중단: {e}")
        errors += 1
        stopped = True

    # 신규 행이 없어도 기존 파일이 있고 성공 구간이 있으면 병합(삭제 반영); 파일도 행도 없으면 빈 파일을 만들지 않음
    if new_rows or (covered and save_path.exists()):
        total = _merge_and_save(new_rows, covered, save_path)
        print(f"[완료] 신규 {len(new_rows)}건 병합 — 누적 총 {total}건 ({save_path})")
    else:
        print("[안내] API에서 신규 데이터가 반환되지 않았습니다.")

    if errors:
        print(f"[오류] 요청 {errors}건 실패{' (중단)' if stopped else ''} — 받은 데이터만 저장했습니다. "
              f"다음 실행 때 최근 구간을 다시 받습니다.")
        return 1
    return 0


if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(description="관세청 국가별·HSK10 쇠고기 수입실적 월별 증분 수집")
    _ap.add_argument("--backfill-from", help="YYYY-MM — 이 월부터 전부 다시 받아 교체 (최장 1995-01)")
    _a = _ap.parse_args()
    _bf = None
    if _a.backfill_from:
        _m = re.fullmatch(r"(\d{4})-(\d{2})", _a.backfill_from.strip())
        if not _m:
            _ap.error("--backfill-from 은 YYYY-MM 형식이어야 합니다")
        _bf = (int(_m.group(1)), int(_m.group(2)))
    sys.exit(collect_customs_increment(_bf))
