import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# [파일 정의서]
# - 파일명: src/test_tab_count.py
# - 목적: 조회 버튼 클릭 후, 표까지 진입하는데 필요한 정확한 TAB 횟수 측정
# - 기능: 자동 로그인 및 조회 후 '일시정지' 상태 유지

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # src/chromedriver.exe 통일 사용 (버전업 시 src 폴더만 교체)
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    driver_path = os.path.join(src_dir, "chromedriver.exe")
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.maximize_window()
    return driver

def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def main():
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

    try:
        print("--- [테스트 모드] 브라우저 세팅 중 ---")
        driver.get("https://impfood.mfds.go.kr/ifs/websquare/websquare.html?w2xPath=/ifs/ui/index.xml")
        time.sleep(7)

        # 1. 팝업 닫기
        try:
            for btn in driver.find_elements(By.XPATH, "//button[contains(text(), '닫기')]"):
                if btn.is_displayed(): js_click(driver, btn)
        except: pass

        # 2. 메뉴 이동
        print("1. 메뉴 이동...")
        js_click(driver, wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_1")))) # 수입식품
        time.sleep(1)
        js_click(driver, wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_2")))) # 일반현황
        time.sleep(1)
        js_click(driver, wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_17")))) # 검사실적
        time.sleep(5) # 화면 로딩

        # 3. 옵션 설정 (냉동, 미국/호주)
        print("2. 옵션 설정 (냉동/미국,호주)...")
        # 냉동
        js_click(driver, driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_sbx_prodSssnm_button"))
        time.sleep(0.5)
        js_click(driver, driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_sbx_prodSssnm_itemTable_2"))
        time.sleep(0.5)
        
        # 국가
        js_click(driver, driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_ccb_SearchNtncd_button"))
        time.sleep(1)
        try:
            js_click(driver, driver.find_element(By.XPATH, "//*[contains(@id, 'itemTable_73')]")) # 미국
            js_click(driver, driver.find_element(By.XPATH, "//*[contains(@id, 'itemTable_243')]")) # 호주
        except: pass
        js_click(driver, driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_ccb_SearchNtncd_button")) # 닫기
        
        # 4. 조회값 입력
        print("3. 날짜 및 품명 입력...")
        start_inp = driver.find_element(By.XPATH, "//*[contains(text(),'처리일자')]/following::input[1]")
        start_inp.clear()
        start_inp.send_keys("2024-08-01")
        
        end_inp = driver.find_element(By.XPATH, "//*[contains(text(),'처리일자')]/following::input[2]")
        end_inp.clear()
        end_inp.send_keys("2024-08-31")

        prod_inp = driver.find_element(By.XPATH, "//*[contains(text(),'품명')]/following::input[1]")
        prod_inp.click()
        prod_inp.clear()
        prod_inp.send_keys("소고기")
        time.sleep(0.5)
        driver.find_element(By.TAG_NAME, "body").click() # Focus Out

        # 5. 조회 버튼 클릭 (물리적 클릭 시도)
        print("4. 조회 버튼 클릭 (포커스 위치)")
        search_btn = driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_btn_search")
        
        # 확실하게 마우스로 클릭해서 포커스를 버튼에 둠
        ActionChains(driver).move_to_element(search_btn).click().perform()
        
        print("\n" + "="*60)
        print("[테스트 시작] 이제 직접 키보드의 'Tab' 키를 눌러보세요.")
        print("   - 현재 포커스는 '조회' 버튼에 있습니다.")
        print("   - 탭을 한 번씩 누르면서, 표 안의 데이터(행)가 선택될 때까지 횟수를 세어주세요.")
        print("   - (보통 표가 선택되면 행 색깔이 바뀌거나 점선 테두리가 생깁니다.)")
        print("="*60)

        # 사용자가 테스트할 수 있도록 무한 대기 (Ctrl+C로 종료)
        while True:
            time.sleep(1)

    except Exception as e:
        print(f"\n[오류] {e}")

if __name__ == "__main__":
    main()