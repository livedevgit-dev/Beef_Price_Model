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
from config import DATA_RAW, PROJECT_ROOT

# [파일 정의서]
# - 파일명: crawl_com_usd_krw.py
# - 역할: 수집
# - 대상: 공통
# - 데이터 소스: 한국은행 ECOS Open API — 731Y001(주요국통화의 대원화환율) / 0000001(원/미국달러 매매기준율), 주기 D
# - 수집/가공 주기: 일단위
# - 주요 기능: USD/KRW 일별 환율을 수집하여 엑셀(Date, Close)로 저장. 기존 데이터 존재 시 마지막 날짜 이후만 증분 수집.
# - 변경 이력: 2026-10 네이버 금융 일별시세 페이지 폐쇄("이 페이지는 더 이상 제공되지 않습니다")로
#   ECOS 로 소스 교체, 전 기간을 ECOS 단일 소스로 재구축. 날짜·숫자 검증을 통과한 행만 저장하고,
#   수집 실패 시 exit 1 로 파이프라인에 실패를 알린다(무음 실패 방지).

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # 사내망 SSL 프록시 대응
load_dotenv(PROJECT_ROOT / ".env")

# ======================================================
# [설정] 기본 환경 설정
# ======================================================
DATA_RAW.mkdir(parents=True, exist_ok=True)
FILE_PATH = DATA_RAW / "exchange_rate_data.xlsx"

# 초기 구축 시 수집 시작일 (파일이 아예 없을 때)
DEFAULT_START_DATE = date(2019, 1, 1)

BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
STAT_CODE = "731Y001"   # 주요국통화의 대원화환율
ITEM_CODE = "0000001"   # 원/미국달러(매매기준율)
PAGE_SIZE = 1000        # ECOS 1회 응답 상한
REQUEST_TIMEOUT = 30


# ======================================================
# [함수] 기존 파일 로드 (검증 통과 행만)
# ======================================================
def clean_fx(df):
    """Date(YYYY-MM-DD 문자열)·Close(float) 로 정규화하고, 파싱 불가 행은 버린다."""
    out = pd.DataFrame({
        "Date": pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce"),
        "Close": pd.to_numeric(df["Close"], errors="coerce"),
    })
    bad = out["Date"].isna() | out["Close"].isna() | (out["Close"] <= 0)
    if bad.any():
        print(f"[정제] 날짜/값 검증 실패 {int(bad.sum())}행 제거")
    out = out[~bad].drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")
    return out.reset_index(drop=True)


def load_existing():
    if not FILE_PATH.exists():
        return pd.DataFrame(columns=["Date", "Close"])
    return clean_fx(pd.read_excel(FILE_PATH))


# ======================================================
# [핵심 로직] ECOS 일별 환율 조회
# ======================================================
def fetch_ecos(api_key, start, end):
    rows, offset = [], 1
    while True:
        url = (f"{BASE_URL}/{api_key}/json/kr/{offset}/{offset + PAGE_SIZE - 1}/"
               f"{STAT_CODE}/D/{start:%Y%m%d}/{end:%Y%m%d}/{ITEM_CODE}")
        res = requests.get(url, verify=False, timeout=REQUEST_TIMEOUT).json()
        body = res.get("StatisticSearch")
        if body is None:
            result = res.get("RESULT", {})
            if result.get("CODE") == "INFO-200":  # 해당 기간 무자료 (휴일 등)
                break
            raise RuntimeError(f"ECOS 응답 오류: {result or res}")
        page = body.get("row", [])
        rows.extend(page)
        if offset + PAGE_SIZE - 1 >= int(body.get("list_total_count", 0)) or not page:
            break
        offset += PAGE_SIZE
        time.sleep(0.3)
    df = pd.DataFrame(
        {"Date": [datetime.strptime(r["TIME"], "%Y%m%d").strftime("%Y-%m-%d") for r in rows],
         "Close": [r["DATA_VALUE"] for r in rows]},
        columns=["Date", "Close"],
    )
    return clean_fx(df)


def update_exchange_rate():
    api_key = os.getenv("ECOS_API_KEY")
    if not api_key:
        print("[에러] ECOS_API_KEY 가 .env 에 없습니다.")
        return 1

    df_old = load_existing()
    if df_old.empty:
        start = DEFAULT_START_DATE
        print(f"[시작] 기존 데이터가 없습니다. {start}부터 초기 구축을 시작합니다...")
    else:
        last = pd.Timestamp(df_old["Date"].iloc[-1]).date()
        start = last + timedelta(days=1)
        print(f"[경로] 기존 파일 마지막 날짜: {last} → {start}부터 증분 수집")

    end = date.today()
    if start > end:
        print("[완료] 이미 최신 상태입니다.")
        return 0

    try:
        df_new = fetch_ecos(api_key, start, end)
    except Exception as e:
        print(f"[에러] ECOS 환율 수집 실패: {e}")
        return 1

    if df_new.empty:
        print("[완료] 추가할 데이터가 없습니다 (휴일 등).")
        if not FILE_PATH.exists():
            return 1
        return 0

    print(f"[추가] 새로 수집된 데이터: {len(df_new)}일 치")
    df_final = clean_fx(pd.concat([df_old, df_new], ignore_index=True) if not df_old.empty else df_new)
    df_final.to_excel(str(FILE_PATH), index=False, engine="openpyxl")
    print(f"[완료] 업데이트 완료! 최종 데이터 기간: {df_final['Date'].iloc[0]} ~ {df_final['Date'].iloc[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(update_exchange_rate())
