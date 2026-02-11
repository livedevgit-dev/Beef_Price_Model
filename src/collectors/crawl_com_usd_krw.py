import pandas as pd
import requests
import os
import time
import warnings
from datetime import datetime

# [파일 정의서]
# - 파일명: crawl_com_usd_krw.py
# - 역할: 수집 (환율 데이터)
# - 대상: USD/KRW 환율 (네이버 금융)
# - 방식: 웹 크롤링 (증분 업데이트)
# - 주요 기능: 네이버 금융에서 USD/KRW 일별 환율을 수집하여 엑셀로 저장
#              기존 데이터가 있을 경우 최신 데이터만 증분 수집

# ======================================================
# [설정] 기본 환경 설정
# ======================================================
warnings.filterwarnings("ignore") # 보안 경고 무시

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)
OUTPUT_DIR = os.path.join(project_root, "data", "0_raw")
OUTPUT_FILE = "exchange_rate_data.xlsx"
FILE_PATH = os.path.join(OUTPUT_DIR, OUTPUT_FILE)

# 초기 구축 시 수집 시작일 (파일이 아예 없을 때)
DEFAULT_START_DATE = "2019-01-01"

# ======================================================
# [함수] 기존 파일에서 '가장 최근 날짜' 확인하기
# ======================================================
def get_last_saved_date():
    if os.path.exists(FILE_PATH):
        try:
            df_exist = pd.read_excel(FILE_PATH)
            if not df_exist.empty and 'Date' in df_exist.columns:
                # 날짜 기준 정렬 후 가장 마지막(최신) 날짜 가져오기
                last_date = df_exist['Date'].max()
                return last_date, df_exist
        except Exception as e:
            print(f"[경고] 기존 파일 읽기 실패: {e}")
    return None, None

# ======================================================
# [핵심 로직] 환율 데이터 업데이트 (증분 수집)
# ======================================================
def update_exchange_rate():
    # 1. 기존 데이터 확인
    last_date, df_old = get_last_saved_date()
    
    if last_date:
        print(f"[경로] 기존 파일이 존재합니다. 마지막 업데이트: {last_date}")
        print("[업데이트] 최신 데이터만 검색하여 업데이트를 시도합니다...")
        target_cutoff_date = last_date # 이 날짜 이후 데이터만 필요함
    else:
        print(f"[시작] 기존 파일이 없습니다. {DEFAULT_START_DATE}부터 초기 구축을 시작합니다...")
        target_cutoff_date = "2019-12-31" # 2020-01-01을 포함하기 위해 하루 전으로 설정
        df_old = pd.DataFrame() # 빈 데이터프레임 생성

    # 2. 크롤링 시작
    new_data_list = []
    page = 1
    stop_scraping = False # 수집 중단 플래그

    while True:
        url = f"https://finance.naver.com/marketindex/exchangeDailyQuote.naver?marketindexCd=FX_USDKRW&page={page}"
        
        try:
            response = requests.get(url, verify=False)
            tables = pd.read_html(response.text, encoding='cp949')
            
            if not tables:
                break
            
            df_page = tables[0]
            if df_page.empty:
                break
            
            # 전처리: 날짜 포맷 통일 및 컬럼 정리
            df_page = df_page[['날짜', '매매기준율']]
            df_page.columns = ['Date', 'Close']
            df_page['Date'] = df_page['Date'].str.replace('.', '-')
            
            # [중요] 수집 중단 조건 체크 (이미 있는 날짜를 만났는가?)
            # 가져온 페이지의 데이터 중 '기준 날짜(target_cutoff_date)'보다 작거나 같은 게 있으면
            # 그 이후는 이미 우리한테 있는 데이터이므로 더 볼 필요가 없음
            
            # 이번 페이지에서 "새로운 데이터"만 필터링 (기준일보다 큰 날짜)
            df_new = df_page[df_page['Date'] > target_cutoff_date]
            
            # 만약 필터링된 데이터가 페이지 전체 데이터보다 적다면?
            # -> 즉, 과거 데이터가 섞여 나오기 시작했다는 뜻 -> 이제 그만해도 됨
            if len(df_new) < len(df_page):
                stop_scraping = True
            
            # 새로운 데이터가 있으면 리스트에 담기
            if not df_new.empty:
                new_data_list.append(df_new)
                # 로그: 1페이지는 항상 보여주고, 그 외에는 10페이지 단위
                if page == 1 or page % 10 == 0:
                    print(f"   Running... {page}페이지에서 최신 데이터 발견 ({len(df_new)}건)")
            
            # 더 이상 새로운 데이터가 없거나, 중단 플래그가 떴으면 종료
            if stop_scraping:
                print("[완료] 최신 데이터 수집을 완료했습니다. (기존 데이터 시점 도달)")
                break
                
            # 안전장치: 너무 많이 돌지 않게 (초기 구축 시 200페이지 제한)
            if page > 200: 
                break
                
            page += 1
            time.sleep(0.1)
            
        except Exception as e:
            print(f"[에러] 에러 발생: {e}")
            break

    # 3. 데이터 병합 및 저장
    if new_data_list:
        df_new_total = pd.concat(new_data_list, ignore_index=True)
        print(f"[추가] 새로 추가된 데이터: {len(df_new_total)}일 치")
        
        # 기존 데이터와 합치기
        if not df_old.empty:
            df_final = pd.concat([df_old, df_new_total], ignore_index=True)
        else:
            df_final = df_new_total
            
        # 중복 제거 (혹시 모를 중복 방지)
        df_final = df_final.drop_duplicates(subset=['Date'], keep='last')
        
        # 날짜순 정렬
        df_final = df_final.sort_values(by='Date')
        
        # 저장
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        df_final.to_excel(FILE_PATH, index=False, engine='openpyxl')
        print(f"[완료] 업데이트 완료! 최종 데이터 기간: {df_final.iloc[0]['Date']} ~ {df_final.iloc[-1]['Date']}")
        
    else:
        print("[완료] 이미 최신 상태입니다. 추가할 데이터가 없습니다.")

if __name__ == "__main__":
    update_exchange_rate()