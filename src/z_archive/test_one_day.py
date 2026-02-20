import os
import requests
import urllib3
import json
from dotenv import load_dotenv

# [파일 정의서]
# - 파일명: src/collectors/debug_api_syntax.py
# - 역할: API 쿼리 문법(Syntax) 테스트
# - 목적: 'Choice Cuts' 섹션에서 날짜 검색이 성공하는 정확한 패턴(따옴표 유무 등)을 찾음

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

def find_correct_syntax():
    api_key = os.getenv("USDA_API_KEY")
    base_url = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/Choice Cuts"
    
    print("🔍 [1단계] 최신 데이터 1건을 조회하여 '확실히 존재하는 날짜'를 확보합니다...")
    
    # 1. 쿼리 없이 요청 (Default: 최신 데이터)
    try:
        response = requests.get(base_url, auth=(api_key, ''), verify=False, timeout=10)
        data = response.json()
        
        if not data.get('results'):
            print("❌ 최신 데이터 조회 실패. API 상태를 점검해주세요.")
            return

        # 확실히 존재하는 날짜 추출
        valid_date = data['results'][0]['report_date']
        print(f"✅ 확보된 유효 날짜: {valid_date}")
        print("-" * 60)
        
    except Exception as e:
        print(f"⛔ 1단계 에러: {e}")
        return

    # 2. 다양한 문법으로 테스트 시도
    # Case A: 따옴표 포함 (report_date='MM/DD/YYYY') -> 기존 방식
    # Case B: 따옴표 제거 (report_date=MM/DD/YYYY)
    # Case C: 슬래시 대신 대시 사용 (report_date='MM-DD-YYYY')
    
    test_cases = [
        (f"report_date='{valid_date}'", "따옴표 포함 (Case A)"),
        (f"report_date={valid_date}",   "따옴표 제거 (Case B)"),
        (f"report_date='{valid_date.replace('/', '-')}'", "대시(-) 사용 (Case C)")
    ]
    
    print(f"🔍 [2단계] '{valid_date}' 날짜로 검색 문법 테스트를 시작합니다...\n")
    
    for query, desc in test_cases:
        print(f"🧪 테스트: {desc}")
        print(f"   Query: {query}")
        
        try:
            res = requests.get(
                base_url, 
                auth=(api_key, ''), 
                params={'q': query}, 
                verify=False, 
                timeout=10
            )
            
            # 결과 확인
            if "No Results Found" in res.text:
                print("   👉 결과: ❌ 실패 (No Results)")
            elif res.status_code == 200:
                try:
                    json_data = res.json()
                    count = len(json_data.get('results', []))
                    if count > 0:
                        print(f"   👉 결과: 🎉 성공! ({count}건 수집됨)")
                        print(f"\n✅ 정답 문법은 [{desc}] 입니다!")
                        return # 성공하면 종료
                    else:
                        print("   👉 결과: ❓ 빈 리스트 (JSON은 왔으나 데이터 없음)")
                except:
                    print(f"   👉 결과: ⚠️ JSON 파싱 실패 ({res.text[:20]})")
            else:
                print(f"   👉 결과: ❌ 에러 코드 {res.status_code}")
                
        except Exception as e:
            print(f"   ⛔ 에러: {e}")
            
        print("-" * 40)

if __name__ == "__main__":
    find_correct_syntax()