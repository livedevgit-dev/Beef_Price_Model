import os
import requests
import pandas as pd
import time
import urllib3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# [파일 정의서]
# - 파일명: src/collectors/api_us_beef_collect_usda.py
# - 역할: 수집
# - 대상: 수입육 (미국 소고기 전체 시장 데이터)
# - 데이터 소스: USDA API (Choice, Select, Ground, Trimmings)
# - 수집/가공 주기: 일단위 (최초 실행 시 2019년부터 전체 수집)
# - 주요 기능: 
#   1. 미국 소고기 도매시장 4대 섹션 전체 데이터 수집
#   2. 대용량 수집 중단 리스크 방지를 위한 6개월(130 영업일) 단위 중간 저장

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

def get_api_key():
    return os.getenv("USDA_API_KEY")

def get_paths():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    save_dir = os.path.join(base_dir, 'data', '0_raw')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    save_path = os.path.join(save_dir, 'usda_beef_history.csv')
    return save_path

def get_last_update_date(save_path):
    if os.path.exists(save_path):
        try:
            df = pd.read_csv(save_path)
            if not df.empty and 'report_date' in df.columns:
                df['dt'] = pd.to_datetime(df['report_date'])
                last_date = df['dt'].max()
                print(f"[시스템] 기존 데이터 발견: 마지막 수집일 {last_date.strftime('%Y-%m-%d')}")
                return last_date
        except Exception:
            pass
    
    print("[시스템] 기존 데이터 없음: 2019-01-01부터 전체 수집을 시작합니다.")
    return datetime(2018, 12, 31)

def generate_new_dates(last_date):
    start_date = last_date + timedelta(days=1)
    end_date = datetime.now()
    if start_date > end_date:
        return []
    dates = pd.date_range(start=start_date, end=end_date, freq='B') # B: 비즈니스 데이(영업일)
    date_strings = [d.strftime('%m/%d/%Y') for d in dates]
    date_strings.sort(reverse=True)
    return date_strings

def save_checkpoint(new_data, save_path):
    """메모리에 쌓인 데이터를 CSV 파일에 병합하고 저장하는 헬퍼 함수입니다."""
    if not new_data:
        return 0
        
    df_new = pd.DataFrame(new_data)
    
    if os.path.exists(save_path):
        df_old = pd.read_csv(save_path)
        df_final = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_final = df_new
        
    # 중복 제거 (날짜 + 품목명 + 등급 기준)
    if 'item_description' in df_final.columns:
        subset_cols = ['report_date', 'item_description', 'grade']
    else:
        subset_cols = None

    if subset_cols:
         df_final.drop_duplicates(subset=subset_cols, inplace=True, keep='last')
    else:
         df_final.drop_duplicates(inplace=True)
    
    # 정렬 (날짜 -> 등급 -> 품목명)
    df_final['temp_dt'] = pd.to_datetime(df_final['report_date'])
    sort_cols = ['temp_dt', 'grade']
    if 'item_description' in df_final.columns:
        sort_cols.append('item_description')
        
    df_final = df_final.sort_values(by=sort_cols, ascending=[False, True, True])
    df_final = df_final.drop(columns=['temp_dt'])
    
    df_final.to_csv(save_path, index=False, encoding='utf-8-sig')
    return len(df_final)

def fetch_and_append():
    api_key = get_api_key()
    save_path = get_paths()
    
    last_date = get_last_update_date(save_path)
    target_dates = generate_new_dates(last_date)
    
    if not target_dates:
        print("[성공] 이미 최신 상태입니다. 수집할 데이터가 없습니다.")
        return

    target_sections = [
        'Choice Cuts',    # 상급 부분육
        'Select Cuts',    # 일반/저가 부분육
        'Ground Beef',    # 다짐육/패티용
        'Beef Trimmings'  # 자투리/가공용
    ]

    total_days = len(target_dates)
    print(f"[안내] 추가 수집 시작: {target_dates[-1]} ~ {target_dates[0]} (총 {total_days}일)")
    
    new_data = []
    chunk_size = 130 # 영업일 기준 약 6개월 치 분량
    
    for i, date_str in enumerate(target_dates):
        print(f"\r[진행중] [{i+1}/{total_days}] {date_str} 데이터 4종 요청 중...", end="")
        
        for section in target_sections:
            base_url = f"https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/{section}"
            query = f"report_date={date_str}"
            
            try:
                response = requests.get(
                    base_url, 
                    auth=(api_key, '') if api_key else None, 
                    params={'q': query}, 
                    verify=False, timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        results = data.get('results', [])
                        if results:
                            clean_name = section.replace(' Cuts', '').replace('Beef ', '')
                            for item in results:
                                item['grade'] = clean_name
                            
                            new_data.extend(results)
                else:
                    time.sleep(0.2)
                    
            except Exception:
                pass
        
        # [중간 저장 로직] 130일(약 6개월) 단위로 파일에 저장하고 메모리 비우기
        if (i + 1) % chunk_size == 0 or (i + 1) == total_days:
            if new_data:
                total_rows = save_checkpoint(new_data, save_path)
                print(f"\n[자동 저장] {date_str}까지의 데이터를 안전하게 기록했습니다. (현재 누적 총 {total_rows}건)")
                new_data = [] # 다음 6개월 치를 위해 메모리 초기화
                time.sleep(1) # 디스크 저장 후 잠시 대기

    print("\n[완료] 지정된 기간의 데이터 수집 및 최종 저장이 모두 끝났습니다.")

if __name__ == "__main__":
    fetch_and_append()