# [파일 정의서]
# - 파일명: crawl_imp_stock_monthly.py
# - 역할: 수집 (KMTA 한국육류유통수출협회 재고 데이터)
# - 대상: 수입 소고기 재고 현황 (월별)
# - 데이터 소스: 한국육류유통수출협회 홈페이지
# - 주요 기능: 빈 데이터("등록된 자료가 없습니다") 예외 처리 및 부위별 증분 수집

import requests
import pandas as pd
import time
import os
import urllib3
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, BEEF_STOCK_XLSX

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

START_YEAR = 2019
START_MONTH = 1
CURRENT_YEAR = datetime.now().year
CURRENT_MONTH = datetime.now().month

def get_last_collected_date(file_path):
    path = Path(file_path) if isinstance(file_path, str) else file_path
    if not path.exists():
        return START_YEAR, START_MONTH
    
    try:
        existing_df = pd.read_excel(file_path)
        if existing_df.empty or '기준년월' not in existing_df.columns:
            return START_YEAR, START_MONTH
        
        # 가짜 텍스트가 들어간 데이터가 있을 수 있으므로, 숫자(날짜) 형태의 데이터만 남겨서 체크
        valid_dates = existing_df[existing_df['기준년월'].str.match(r'^\d{4}-\d{2}$', na=False)]
        if valid_dates.empty:
            return START_YEAR, START_MONTH
            
        last_date = valid_dates['기준년월'].max()
        year, month = map(int, last_date.split('-'))
        
        month += 1
        if month > 12:
            month = 1
            year += 1
        
        return year, month
    except Exception as e:
        print(f"[경고] 기존 파일 읽기 실패: {e}. 처음부터 수집합니다.")
        return START_YEAR, START_MONTH

def get_stock_data(start_year=None, start_month=None, existing_df=None):
    url = 'https://www.kmta.or.kr/kr/info/beef_stock_income.php'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Origin': 'https://www.kmta.or.kr',
        'Referer': 'https://www.kmta.or.kr/kr/info/beef_stock_income.php'
    }

    collect_start_year = start_year if start_year else START_YEAR
    collect_start_month = start_month if start_month else START_MONTH

    all_data = []
    
    if existing_df is not None and not existing_df.empty:
        print(f"[정보] 기존 데이터 {len(existing_df)}건 확인됨")
        print(f"[시작] [증분 수집] {collect_start_year}.{collect_start_month:02d} ~ {CURRENT_YEAR}.{CURRENT_MONTH} (신규 데이터만)")
    else:
        print(f"[시작] [전체 수집] {collect_start_year}.{collect_start_month:02d} ~ {CURRENT_YEAR}.{CURRENT_MONTH}")
    print("="*60)

    for year in range(collect_start_year, CURRENT_YEAR + 1):
        start_m = collect_start_month if year == collect_start_year else 1
        end_m = CURRENT_MONTH if year == CURRENT_YEAR else 12
        
        for month in range(start_m, end_m + 1):
            str_month = f"{month:02d}"
            
            data = {
                'typ': 'list_url',
                'list_url': '/kr/info/beef_stock_income.php',
                'page': '1',
                'board': 'info10',
                'scode': '10',
                'year': str(year),
                'month': str_month
            }

            try:
                print(f"[조회] {year}년 {str_month}월...", end="")
                response = requests.post(url, headers=headers, data=data, verify=False)
                
                dfs = pd.read_html(response.text)
                if not dfs:
                    print(" [경고] 표 없음")
                    continue
                
                df = dfs[0]

                # [핵심 수정 1] "등록된 자료가 없습니다" 등 텍스트 유효성 검증
                # 표 내용 전체를 문자열로 변환하여 에러 문구가 포함되어 있는지 확인합니다.
                if df.astype(str).apply(lambda x: x.str.contains('등록 된 자|자료가 없', na=False)).any().any():
                    print(" [건너뜀] 해당 월 데이터 미등록 (업데이트 대기중)")
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    new_cols = []
                    for col in df.columns:
                        clean_col = " ".join([str(c) for c in col if "Unnamed" not in str(c)]).strip()
                        new_cols.append(clean_col)
                    df.columns = new_cols

                df.insert(0, '기준년월', f"{year}-{str_month}")
                
                all_data.append(df)
                print(f" [완료] 완료 ({len(df)}개 품목)")
                time.sleep(0.1)

            except Exception as e:
                print(f" [에러] 에러: {e}")
                continue

    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        return final_df
    else:
        return pd.DataFrame()

if __name__ == "__main__":
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    save_path = BEEF_STOCK_XLSX
    
    last_year, last_month = get_last_collected_date(save_path)
    
    existing_df = None
    if Path(save_path).exists():
        try:
            existing_df = pd.read_excel(save_path)
            # 가짜 텍스트 행이 이미 엑셀에 들어가 있다면 읽어올 때 미리 청소합니다
            existing_df = existing_df[~existing_df.astype(str).apply(lambda x: x.str.contains('등록 된 자|자료가 없', na=False)).any(axis=1)]
        except:
            existing_df = None
    
    if last_year > CURRENT_YEAR or (last_year == CURRENT_YEAR and last_month > CURRENT_MONTH):
        print("\n" + "="*40)
        print("[정보] 이미 최신 데이터입니다. 수집할 데이터가 없습니다.")
        print(f"[경로] 기존 파일: {save_path}")
        print("="*40)
    else:
        new_data_list = get_stock_data(last_year, last_month, existing_df)
        
        if isinstance(new_data_list, pd.DataFrame) and not new_data_list.empty:
            new_data_df = new_data_list
            
            if existing_df is not None and not existing_df.empty:
                final_df = pd.concat([existing_df, new_data_df], ignore_index=True)
                
                # [핵심 수정 2] 기준년월 하나만으로 중복 제거하면 다른 부위가 다 날아가는 버그 수정
                # '기준년월'과 '부위명(보통 두번째 컬럼)'을 조합하여 중복을 필터링합니다.
                part_col = final_df.columns[1] 
                final_df = final_df.drop_duplicates(subset=['기준년월', part_col], keep='last')
                
                print(f"\n[병합] 기존 {len(existing_df)}건 + 신규 {len(new_data_df)}건 = 총 {len(final_df)}건")
            else:
                final_df = new_data_df
            
            final_df.to_excel(save_path, index=False)
            
            print("\n" + "="*40)
            print(f"[완료] 재고 데이터 수집 및 저장 성공!")
            print(f"[전체] 총 {len(final_df)}건")
            print("="*40)
        elif existing_df is not None and not existing_df.empty:
            existing_df.to_excel(save_path, index=False) # 청소된 데이터 다시 저장
            print("\n" + "="*40)
            print("[정보] 신규 등록된 데이터가 없습니다 (협회 미업데이트)")
            print("="*40)
        else:
            print("\n[경고] 수집된 데이터가 없습니다.")