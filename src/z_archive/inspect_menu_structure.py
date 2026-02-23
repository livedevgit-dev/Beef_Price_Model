import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# [파일 정의서]
# - 파일명: src/find_real_id_deep.py
# - 목적: WebSquare 내부의 모든 iframe을 순회하며 실제 데이터가 들어있는 DataList ID 추출
# - 기능: 
#   1. 메인 프레임 탐색
#   2. 모든 iframe 내부 진입 및 탐색
#   3. 행(Row) 개수가 0보다 큰 DataList 발견 시 출력

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    # src/chromedriver.exe 통일 사용 (버전업 시 src 폴더만 교체)
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    driver_path = os.path.join(src_dir, "chromedriver.exe")
    service = Service(executable_path=driver_path)
    return webdriver.Chrome(service=service, options=chrome_options)

def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def find_datalist_in_context(driver, context_name="Main"):
    """현재 프레임에서 데이터가 있는 DataList 찾기"""
    script = """
        var results = [];
        try {
            if (typeof WebSquare !== 'undefined' && WebSquare.ModelUtil) {
                var allDl = WebSquare.ModelUtil.getAllDataList();
                allDl.forEach(function(dl) {
                    if (dl.getRowCount() > 0) {
                        results.push({
                            id: dl.getID(),
                            count: dl.getRowCount(),
                            sample: dl.getRowJSON(0)
                        });
                    }
                });
            }
        } catch(e) {}
        return results;
    """
    try:
        data_lists = driver.execute_script(script)
        if data_lists:
            print(f"\n🔎 [{context_name}] 탐색 결과:")
            for dl in data_lists:
                print(f"   🔹 ID: {dl['id']}")
                print(f"   📦 개수: {dl['count']}")
                print(f"   👀 샘플: {str(dl['sample'])[:60]}...")
                print("-" * 40)
            return True
    except:
        pass
    return False

def main():
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

    try:
        print("--- [심층 구조 분석 시작] ---")
        driver.get("https://impfood.mfds.go.kr/ifs/websquare/websquare.html?w2xPath=/ifs/ui/index.xml")
        time.sleep(10)

        # 1. 팝업 닫기
        try:
            for btn in driver.find_elements(By.XPATH, "//button[contains(text(), '닫기')]"):
                if btn.is_displayed(): js_click(driver, btn)
        except: pass

        # 2. 메뉴 이동
        print("1. 메뉴 이동...")
        js_click(driver, wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_1"))))
        time.sleep(1)
        js_click(driver, wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_2"))))
        time.sleep(1)
        js_click(driver, wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_17"))))
        time.sleep(3)

        # 3. 조회 조건 (데이터 있는 2025-12)
        print("2. 조회 실행 (2025-12)...")
        driver.find_element(By.XPATH, "//*[contains(text(),'처리일자')]/following::input[1]").send_keys("2025-12-01")
        driver.find_element(By.XPATH, "//*[contains(text(),'처리일자')]/following::input[2]").send_keys("2025-12-31")
        
        prod_inp = driver.find_element(By.XPATH, "//*[contains(text(),'품명')]/following::input[1]")
        prod_inp.click()
        prod_inp.clear()
        prod_inp.send_keys("소고기")
        driver.find_element(By.TAG_NAME, "body").click()

        js_click(driver, driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_btn_search"))
        
        print("   ⏳ 데이터 로딩 대기 (40초)...")
        time.sleep(40)

        # 4. [핵심] 메인 프레임 + 모든 Iframe 순회 탐색
        print("\n3. 🕵️‍♂️ 모든 프레임(Iframe) 정밀 수색 중...")
        
        # (1) 메인 프레임 탐색
        find_datalist_in_context(driver, "메인 프레임")

        # (2) Iframe 탐색
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"   👉 발견된 Iframe 개수: {len(iframes)}개")

        for i, frame in enumerate(iframes):
            try:
                driver.switch_to.frame(frame)
                found = find_datalist_in_context(driver, f"Iframe #{i}")
                driver.switch_to.default_content() # 복귀
            except:
                driver.switch_to.default_content()

        print("\n" + "="*60)
        print("💡 위 결과에서 '소고기' 데이터가 보이는 ID를 알려주세요.")
        print("   (예: dlt_impList, dlt_grdResult, list1 등)")
        print("="*60)

    except Exception as e:
        print(f"\n❌ [오류] {e}")

if __name__ == "__main__":
    main()