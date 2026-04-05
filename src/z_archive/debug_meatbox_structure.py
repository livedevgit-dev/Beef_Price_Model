import time
import os
import urllib3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ------------------------------------------------------------------
# [진단 도구] HTML 구조 및 링크 패턴 확인
# ------------------------------------------------------------------

# SSL 경고 무시 설정
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['WDM_SSL_VERIFY'] = '0' 

def analyze_structure():
    url = "https://www.meatbox.co.kr/fo/sise/siseListPage.do"
    
    # 저장 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    save_dir = os.path.join(project_root, 'data', '0_raw')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    debug_file = os.path.join(save_dir, "debug_page_source.html")

    print("[진단 시작] 브라우저를 실행하고 페이지 구조를 분석합니다...")
    
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # 화면을 보면서 확인하기 위해 주석 처리
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        time.sleep(5) # 로딩 대기 시간을 5초로 넉넉히 줍니다.

        # 1. Iframe 존재 여부 확인
        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        print(f"\n======== [1] Iframe 확인 ========")
        print(f"발견된 iframe 개수: {len(iframes)}")
        if len(iframes) > 0:
            for idx, frame in enumerate(iframes):
                print(f" - Iframe {idx}: ID='{frame.get_attribute('id')}', Name='{frame.get_attribute('name')}'")

        # 2. 페이지 소스 저장
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print(f"\n======== [2] 페이지 소스 저장 ========")
        print(f"현재 페이지의 HTML을 저장했습니다: {debug_file}")

        # 3. 링크(a 태그) 패턴 샘플링
        links = driver.find_elements(By.TAG_NAME, 'a')
        print(f"\n======== [3] 링크(a 태그) 패턴 분석 (총 {len(links)}개 중 상위 20개) ========")
        
        count = 0
        for link in links:
            href = link.get_attribute('href')
            text = link.text.strip()
            
            # 의미 있는 링크만 출력 (javascript나 http가 포함된 것)
            if href and ('javascript' in href or 'http' in href) and count < 20:
                print(f"[{count+1}] 텍스트: '{text}' || 링크: {href}")
                count += 1
                
        # 4. 버튼(button 태그) 패턴 샘플링 (혹시 a태그가 아니라 button일 경우)
        buttons = driver.find_elements(By.TAG_NAME, 'button')
        print(f"\n======== [4] 버튼(button 태그) 패턴 분석 (상위 10개) ========")
        count = 0
        for btn in buttons:
            onclick = btn.get_attribute('onclick')
            text = btn.text.strip()
            if onclick and count < 10:
                print(f"[{count+1}] 텍스트: '{text}' || 클릭이벤트: {onclick}")
                count += 1

    except Exception as e:
        print(f"[ERROR] 에러 발생: {e}")
    finally:
        driver.quit()
        print("\n[진단 종료]")

if __name__ == "__main__":
    analyze_structure()