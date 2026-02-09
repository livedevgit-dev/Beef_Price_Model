import requests
import pandas as pd
import time
import os
import urllib3
from datetime import datetime

# [설정] SSL 보안 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# [설정] 수집 기간 (2019년 ~ 현재)
START_YEAR = 2019
START_MONTH = 1
CURRENT_YEAR = datetime.now().year
CURRENT_MONTH = datetime.now().month

def get_last_collected_date(file_path):
    """기존 파일에서 마지막 수집 날짜를 확인"""
    if not os.path.exists(file_path):
        return START_YEAR, START_MONTH
    
    try:
        existing_df = pd.read_excel(file_path)
        if existing_df.empty or '기준년월' not in existing_df.columns:
            return START_YEAR, START_MONTH
        
        # 마지막 날짜 추출 (예: "2026-01")
        last_date = existing_df['기준년월'].max()
        year, month = map(int, last_date.split('-'))
        
        # 다음 달부터 수집하도록 설정
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

    # 시작 날짜 설정 (파라미터로 받거나 기본값 사용)
    collect_start_year = start_year if start_year else START_YEAR
    collect_start_month = start_month if start_month else START_MONTH

    all_data = []
    
    # 기존 데이터 확인 메시지
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
                
                # 표 추출
                dfs = pd.read_html(response.text)
                if not dfs:
                    print(" [경고] 표 없음")
                    continue
                
                df = dfs[0]

                # [핵심 수정] 다중 헤더(MultiIndex)를 단일 헤더로 변환
                if isinstance(df.columns, pd.MultiIndex):
                    new_cols = []
                    for col in df.columns:
                        # 튜플로 된 컬럼명을 문자열로 합치되, 'Unnamed' 같은 불필요한 텍스트 제거
                        clean_col = " ".join([str(c) for c in col if "Unnamed" not in str(c)]).strip()
                        new_cols.append(clean_col)
                    df.columns = new_cols

                # 데이터 정리
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

# --- 실행부 ---
if __name__ == "__main__":
    # 저장 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    save_dir = os.path.join(project_root, "data", "0_raw")
    
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    filename = "beef_stock_data.xlsx"
    save_path = os.path.join(save_dir, filename)
    
    # 기존 데이터 확인 및 시작 날짜 결정
    last_year, last_month = get_last_collected_date(save_path)
    
    # 기존 데이터 로드
    existing_df = None
    if os.path.exists(save_path):
        try:
            existing_df = pd.read_excel(save_path)
            print(f"[확인] 기존 파일 발견: 마지막 수집 날짜 = {last_year-1 if last_month == 1 else last_year}-{12 if last_month == 1 else last_month-1:02d}")
        except:
            existing_df = None
    
    # 이미 최신 상태인지 확인
    if last_year > CURRENT_YEAR or (last_year == CURRENT_YEAR and last_month > CURRENT_MONTH):
        print("\n" + "="*40)
        print("[정보] 이미 최신 데이터입니다. 수집할 데이터가 없습니다.")
        print(f"[경로] 기존 파일: {save_path}")
        print("="*40)
    else:
        # 신규 데이터 수집
        new_data_list = get_stock_data(last_year, last_month, existing_df)
        
        # 데이터 병합
        if new_data_list:
            new_data_df = pd.concat(new_data_list, ignore_index=True)
            
            if existing_df is not None and not existing_df.empty:
                # 기존 데이터 + 신규 데이터 병합
                final_df = pd.concat([existing_df, new_data_df], ignore_index=True)
                # 중복 제거 (혹시 모를 중복 방지)
                final_df = final_df.drop_duplicates(subset=['기준년월'], keep='last')
                print(f"\n[병합] 기존 {len(existing_df)}건 + 신규 {len(new_data_df)}건 = 총 {len(final_df)}건")
            else:
                final_df = new_data_df
            
            # 엑셀 저장
            final_df.to_excel(save_path, index=False)
            
            print("\n" + "="*40)
            print(f"[완료] 재고 데이터 수집 및 저장 성공!")
            print(f"[신규] {len(new_data_df)}건 추가")
            print(f"[전체] 총 {len(final_df)}건")
            print(f"[경로] {save_path}")
            print("="*40)
        elif existing_df is not None and not existing_df.empty:
            print("\n" + "="*40)
            print("[정보] 신규 데이터가 없습니다 (아직 업데이트 안 됨)")
            print(f"[전체] 기존 {len(existing_df)}건 유지")
            print(f"[경로] {save_path}")
            print("="*40)
        else:
            print("\n[경고] 수집된 데이터가 없습니다.")