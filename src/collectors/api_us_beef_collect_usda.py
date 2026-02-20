import os
import requests
import pandas as pd
import time
import urllib3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# [파일 정의서]
# - 파일명: src/collectors/api_us_beef_collect_usda.py
# - 역할: 수집 (미국 소고기 전체 시장 데이터)
# - 범위: Choice(상급), Select(일반/저가), Ground Beef(다짐육), Trimmings(자투리)
# - 저장: data/0_raw/usda_beef_history.csv

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
                print(f"🔄 기존 데이터 발견: 마지막 수집일 {last_date.strftime('%Y-%m-%d')}")
                return last_date
        except Exception:
            pass
    
    print("✨ 기존 데이터 없음: 2019-01-01부터 시작합니다.")
    return datetime(2018, 12, 31)

def generate_new_dates(last_date):
    start_date = last_date + timedelta(days=1)
    end_date = datetime.now()
    if start_date > end_date:
        return []
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    date_strings = [d.strftime('%m/%d/%Y') for d in dates]
    date_strings.sort(reverse=True)
    return date_strings

def fetch_and_append():
    api_key = get_api_key()
    save_path = get_paths()
    
    # 1. 수집 대상 날짜 확인
    last_date = get_last_update_date(save_path)
    target_dates = generate_new_dates(last_date)
    
    if not target_dates:
        print("✅ 이미 최신 상태입니다.")
        return

    # [핵심 수정] 수집 대상 섹션 4종으로 확대
    target_sections = [
        'Choice Cuts',    # 상급 부분육
        'Select Cuts',    # 일반/저가 부분육 (우삼겹 등)
        'Ground Beef',    # 다짐육/패티용
        'Beef Trimmings'  # 자투리/가공용
    ]

    print(f"🚀 추가 수집 시작: {target_dates[-1]} ~ {target_dates[0]} (총 {len(target_dates)}일)")
    print(f"🎯 수집 섹션: {target_sections}")
    
    new_data = []
    
    # 2. 날짜별 & 섹션별 데이터 요청
    for i, date_str in enumerate(target_dates):
        # 진행률 표시 (줄바꿈 없이 갱신)
        print(f"\r⏳ [{i+1}/{len(target_dates)}] {date_str} 데이터 4종 요청 중...", end="")
        
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
                            # [데이터 태깅] 어떤 섹션에서 온 데이터인지 표기
                            # section_type 컬럼에 'Choice', 'Select', 'Ground', 'Trimmings' 저장
                            clean_name = section.replace(' Cuts', '').replace('Beef ', '')
                            for item in results:
                                item['grade'] = clean_name # grade 또는 category 컬럼으로 활용
                            
                            new_data.extend(results)
                else:
                    time.sleep(0.2)
                    
            except Exception:
                pass
            
            # API 호출 간격 조절 (너무 빠르면 차단될 수 있음)
            # time.sleep(0.05)

    # 3. 데이터 저장
    if new_data:
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
            # Ground Beef/Trimmings는 item_description이 없을 수도 있음 (보통 report_title이나 다른 걸로 구분)
            # 안전하게 전체 중복 제거 시도
            subset_cols = None

        if subset_cols:
             df_final.drop_duplicates(subset=subset_cols, inplace=True, keep='last')
        else:
             df_final.drop_duplicates(inplace=True)
        
        # 정렬 (날짜 -> 등급 -> 품목명)
        df_final['temp_dt'] = pd.to_datetime(df_final['report_date'])
        
        # 정렬 기준 컬럼이 있는지 확인 후 정렬
        sort_cols = ['temp_dt', 'grade']
        if 'item_description' in df_final.columns:
            sort_cols.append('item_description')
            
        df_final = df_final.sort_values(by=sort_cols, ascending=[False, True, True])
        df_final = df_final.drop(columns=['temp_dt'])
        
        df_final.to_csv(save_path, index=False, encoding='utf-8-sig')
        print(f"\n\n💾 업데이트 완료! {len(new_data)}건 추가됨 (총 {len(df_final)}건)")
        
        # [검증용 출력]
        print("\n🔎 [수집된 섹션별 건수]")
        print(df_new['grade'].value_counts())
        
    else:
        print("\n⚠️ 요청한 기간에 데이터가 없습니다.")

if __name__ == "__main__":
    fetch_and_append()