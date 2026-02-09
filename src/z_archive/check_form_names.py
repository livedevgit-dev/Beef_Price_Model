import requests
from bs4 import BeautifulSoup
import urllib3

# [파일 정의서]
# - 파일명: src/check_form_names.py (일회성 도구)
# - 역할: 분석
# - 목적: 웹사이트의 조회 조건(Form Data) 변수명 추출
# - 주요 기능: HTML을 분석하여 <select> 및 <input> 태그의 name 속성 확인

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://www.kmta.or.kr/kr/data/stats_import_beef_parts2.php"

print(f"--- [분석 시작] 웹사이트 양식(Form) 분석 ---")
print(f"대상: {URL}")

try:
    # 1. 웹페이지 접속
    response = requests.get(URL, verify=False)
    
    # 2. HTML 파싱 (BeautifulSoup 활용)
    # pandas 설치 시 보통 같이 설치되지만, 없다면 'pip install beautifulsoup4' 필요
    soup = BeautifulSoup(response.text, 'html.parser')
    
    print("\n[1] <form> 태그 확인 (데이터 전송 방식)")
    forms = soup.find_all('form')
    for i, form in enumerate(forms):
        method = form.get('method', 'N/A')
        action = form.get('action', 'N/A')
        print(f" - Form #{i+1}: method={method}, action={action}")

    print("\n[2] <select> 태그 확인 (연도/월 선택 박스 추정)")
    # 보통 날짜 선택은 dropdown(<select>) 방식입니다.
    selects = soup.find_all('select')
    if not selects:
        print(" - <select> 태그를 찾지 못했습니다.")
    for sel in selects:
        name = sel.get('name')
        chk_id = sel.get('id')
        # 옵션 값 일부 미리보기
        options = sel.find_all('option')
        first_opt = options[0].text.strip() if options else "없음"
        last_opt = options[-1].text.strip() if options else "없음"
        
        print(f" ★ 발견! Name: '{name}' (ID: {chk_id})")
        print(f"   ㄴ 예시값: {first_opt} ~ {last_opt}")

    print("\n[3] <input> 태그 확인 (히든 필드 등)")
    inputs = soup.find_all('input')
    for inp in inputs:
        inp_type = inp.get('type')
        if inp_type in ['hidden', 'text', 'radio', 'checkbox']:
            name = inp.get('name')
            value = inp.get('value', '')
            print(f" - Input: Type={inp_type}, Name='{name}', Value='{value}'")

except Exception as e:
    print(f"\n[오류] 분석 중 에러 발생: {e}")
    print("혹시 'bs4' 모듈이 없다는 에러라면: pip install beautifulsoup4 명령어로 설치해주세요.")

print("\n--- [분석 종료] ---")