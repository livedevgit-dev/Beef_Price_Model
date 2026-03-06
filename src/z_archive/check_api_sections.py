import requests
import urllib3
import json

# [파일 정의서]
# - 파일명: check_api_sections.py
# - 역할: 분석 (가공 없는 원본 API 응답 확인)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_raw_api():
    url = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453"
    
    print("=" * 60)
    print("USDA API 서버에 2453 리포트의 목차를 요청합니다...")
    
    try:
        response = requests.get(url, timeout=10, verify=False)
        print(f"응답 상태 코드: {response.status_code}\n")
        
        # 날것 그대로의 JSON 텍스트를 예쁘게 출력
        raw_data = response.json()
        print(json.dumps(raw_data, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"오류 발생: {e}")
        
    print("=" * 60)

if __name__ == "__main__":
    check_raw_api()