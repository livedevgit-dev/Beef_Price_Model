import pandas as pd
import requests
import time
import random
import os
import urllib3
from datetime import datetime

# [파일 정의서]
# - 파일명: src/crawl_imp_history_batch.py
# - 역할: 수집
# - 대상: 수입육
# - 데이터 소스: 미트박스 (API: getSiseChartInfoList.json)
# - 수집/가공 주기: 월단위 (과거 12개월 데이터 일괄 수집용)
# - 주요 기능: ID 리스트를 읽어 API를 통해 최근 1년치 시세 히스토리를 조회하고, 개별 엑셀 파일로 저장

# ==========================================
# 0. SSL 인증서 경고 무시 설정
# ==========================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. 환경 설정 및 파일 경로 정의
# ==========================================
BASE_DIR = "D:/Beef_Price_Model"
INPUT_FILE = os.path.join(BASE_DIR, "data/0_raw/meatbox_id_list.xlsx")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/0_raw/history_batch/")

# [수정 포인트] API URL 변경 (pa -> fo)
# 404 에러 해결: 일반 사용자용 경로인 'fo'(Front Office)로 변경
API_URL = "https://www.meatbox.co.kr/fo/sise/getSiseChartInfoList.json"

# 저장 폴더가 없으면 생성
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"[알림] 폴더 생성 완료: {OUTPUT_DIR}")

# ==========================================
# 2. ID 리스트 불러오기
# ==========================================
print(f"[시작] 파일 읽기: {INPUT_FILE}")

try:
    df_id_list = pd.read_excel(INPUT_FILE)
    
    if 'siseSeq' not in df_id_list.columns:
        raise ValueError("엑셀 파일에 'siseSeq' 컬럼이 존재하지 않습니다.")
    
    total_count = len(df_id_list)
    print(f"[정보] 총 {total_count}개의 품목에 대해 수집을 시작합니다.")
    
except Exception as e:
    print(f"[에러] 초기 파일 로드 실패: {e}")
    exit()

# ==========================================
# 3. 데이터 수집 및 저장 루프 (Batch)
# ==========================================

success_cnt = 0
fail_cnt = 0

# 헤더 설정 (Referer 주소도 fo로 맞춰서 보강)
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.meatbox.co.kr/fo/sise/siseMain.do', # 시세 메인 페이지 주소로 위장
    'Origin': 'https://www.meatbox.co.kr',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' # 폼 데이터 전송 명시
}

for index, row in df_id_list.iterrows():
    sise_seq = row.get('siseSeq')
    product_name = row.get('품목명', 'Unknown')
    
    print(f"[{index + 1}/{total_count}] 수집 중... ID: {sise_seq} ({product_name})")
    
    if pd.isna(sise_seq):
        print(" -> [스킵] siseSeq가 비어있음")
        fail_cnt += 1
        continue

    try:
        # API 요청 파라미터 설정
        params = {
            'siseSeq': str(sise_seq),
            'term': '12' 
        }

        # API 호출 (POST 방식, SSL 검증 off)
        response = requests.post(API_URL, data=params, headers=headers, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            
            # 데이터가 리스트 형태이고 내용이 있는지 확인
            if isinstance(data, list) and len(data) > 0:
                
                df_history = pd.DataFrame(data)
                
                # 컬럼명 매핑
                df_history.rename(columns={
                    'baseDate': '기준일자',
                    'date': '기준일자',
                    'price': '도매시세',
                    'sise': '도매시세'
                }, inplace=True)
                
                # 메타 데이터 추가
                for col in df_id_list.columns:
                    if col not in df_history.columns:
                        df_history[col] = row[col]
                
                # 컬럼 정렬
                cols = ['기준일자'] + [c for c in df_history.columns if c != '기준일자']
                df_history = df_history[cols]
                
                # 저장
                save_filename = f"sise_{sise_seq}.xlsx"
                save_path = os.path.join(OUTPUT_DIR, save_filename)
                df_history.to_excel(save_path, index=False)
                
                print(f" -> [성공] 저장 완료: {save_filename} (데이터 {len(df_history)}건)")
                success_cnt += 1
                
            else:
                # 200 OK는 떨어졌는데 내용이 비어있는 경우
                print(f" -> [경고] 데이터 없음 (API 응답은 정상이나 내용이 비어있음)")
                fail_cnt += 1
        else:
            print(f" -> [실패] HTTP 상태 코드: {response.status_code} (URL 확인 필요)")
            fail_cnt += 1

    except Exception as e:
        print(f" -> [에러] 처리 중 예외 발생: {e}")
        fail_cnt += 1

    time.sleep(random.uniform(1, 3))

# ==========================================
# 4. 종료 리포트
# ==========================================
print("-" * 50)
print(f"[완료] 작업 종료")
print(f"총 대상: {total_count}개")
print(f"성공: {success_cnt}개")
print(f"실패: {fail_cnt}개")
print(f"저장 경로: {OUTPUT_DIR}")
print("-" * 50)