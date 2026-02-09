import os
import time
import pandas as pd
import pyperclip  # 클립보드 제어
import pyautogui  # 물리적 키보드 제어
from datetime import datetime, timedelta

# 셀레니움 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# 1. 설정 변수
# ==========================================
DRIVER_PATH = "chromedriver.exe" 
OUTPUT_FILENAME = "us_beef_parts_import_daily.csv"
TARGET_URL = "https://impfood.mfds.go.kr/ifs/websquare/websquare.html?w2xPath=/ifs/ui/index.xml"

MAX_RETRIES = 3 
WAIT_TIME_SECONDS = 20
USA_DOWN_COUNT = 75    # '미국' 찾기 위한 화살표 연타 횟수
ZOOM_LEVELS = 7        # 줌아웃 반복 횟수

# ==========================================
# 2. 날짜 계산
# ==========================================
yesterday = datetime.now() - timedelta(days=1)
SEARCH_DATE_STR = yesterday.strftime("%Y-%m-%d")

def get_driver():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    driver_path_abs = os.path.join(current_dir, DRIVER_PATH)
    service = Service(driver_path_abs)
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True) 
    options.add_argument("--start-maximized") 
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def wait_and_click(driver, xpath, desc):
    try:
        element = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        element.click()
        print(f"   [이동] '{desc}' 클릭 성공")
        time.sleep(1)
    except Exception as e:
        print(f"   [에러] '{desc}' 클릭 실패: {e}")
        raise

def ensure_iframe_context(driver):
    try:
        driver.switch_to.default_content() 
        time.sleep(0.5)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if len(iframes) > 0:
            driver.switch_to.frame(0)
            return True
    except:
        return False

def parse_clipboard_data(full_text):
    if not full_text: return []
    lines = full_text.split('\n')
    data_list = []
    for line in lines:
        if "소고기" in line and "미국" in line and "냉동" in line:
            parts = line.split() 
            if len(parts) >= 4:
                if "합계" in line: continue
                
                # [수정] 데이터 맨 앞에 '기준일자' 추가
                # parts 리스트: [품명, 구분, 부위, 국가, 중량...]
                # 결과: [날짜, 품명, 구분, 부위, 국가, 중량...]
                parts.insert(0, SEARCH_DATE_STR)
                
                data_list.append(parts)
    return data_list

def perform_copy_physical():
    """물리적 복사 (Ctrl+A -> Ctrl+C)"""
    pyperclip.copy("") 
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(1.0) 
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(1.0) 
    return pyperclip.paste()

def zoom_browser(direction="out", times=1):
    if direction == "reset":
        print("   [화면] 줌 초기화 (100%)")
        pyautogui.hotkey('ctrl', '0')
        time.sleep(1)
        return

    key = '-' if direction == "out" else '+'
    print(f"   [화면] 줌 아웃 {times}단계 실행 중...")
    for _ in range(times):
        pyautogui.hotkey('ctrl', key)
        time.sleep(0.2)
    time.sleep(2) 

def attempt_crawling(attempt_num):
    driver = None
    try:
        print(f"\n--- [시도 {attempt_num}/{MAX_RETRIES}] 데이터 수집 시작 (v29 Append Mode) ---")
        driver = get_driver()
        driver.get(TARGET_URL)
        time.sleep(5) 

        # 네비게이션
        print("   [탐색] 메뉴 이동 중...")
        wait_and_click(driver, "//*[text()='수입식품']", "수입식품")
        wait_and_click(driver, "//*[text()='일반현황']", "일반현황")
        wait_and_click(driver, "//*[contains(text(), '냉장/냉동-부위-국가 검사실적')]", "타겟 메뉴")

        print("   [대기] 페이지 로딩 (5초)...")
        time.sleep(5) 
        ensure_iframe_context(driver)
        time.sleep(1)

        # 조건 입력
        print("   [입력] 검색 조건 설정 중...")
        actions = ActionChains(driver)
        for _ in range(5): actions.send_keys(Keys.TAB)
        actions.perform()
        time.sleep(0.5) 
        
        actions = ActionChains(driver)
        actions.send_keys(SEARCH_DATE_STR)
        actions.perform()
        time.sleep(0.5)

        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB).send_keys(Keys.TAB)
        actions.perform()
        time.sleep(0.5)
        
        actions = ActionChains(driver)
        actions.send_keys(SEARCH_DATE_STR)
        actions.perform()
        time.sleep(0.5)
        
        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB).send_keys(Keys.TAB).send_keys(Keys.TAB)
        actions.perform()
        time.sleep(0.5)
        
        actions = ActionChains(driver)
        actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ARROW_DOWN)
        actions.perform()
        print("      -> 구분 '냉동' 설정")
        time.sleep(1)

        print(f"      -> 국가 '미국' 선택 중 ({USA_DOWN_COUNT}회 다운)...")
        ActionChains(driver).send_keys(Keys.TAB).perform()
        time.sleep(0.5)
        
        actions = ActionChains(driver)
        for _ in range(USA_DOWN_COUNT):
            actions.send_keys(Keys.ARROW_DOWN)
        actions.perform()
        time.sleep(1) 
        ActionChains(driver).send_keys(Keys.SPACE).perform()
        print("      -> '미국' 선택 완료")
        time.sleep(1)

        print("   [실행] Enter 키 입력!")
        ActionChains(driver).send_keys(Keys.ENTER).perform()

        print(f"   [대기] 데이터 로딩 대기 ({WAIT_TIME_SECONDS}초)...")
        for i in range(WAIT_TIME_SECONDS // 5):
            time.sleep(5)
            print(f"        ... { (i+1)*5 }초 경과")

        # =================================================================
        # [수집] 줌아웃 전략
        # =================================================================
        print("   [초점] 표 영역 활성화를 위해 본문 클릭...")
        ensure_iframe_context(driver) 
        try:
            driver.find_element(By.TAG_NAME, "body").click()
        except:
            pass
        time.sleep(1)

        zoom_browser(direction="out", times=ZOOM_LEVELS)

        print("   [수집] 전체 데이터 복사 시도...")
        clipboard_text = perform_copy_physical()
        
        zoom_browser(direction="reset")

        # 데이터 파싱 (날짜 추가 로직 포함됨)
        all_collected_data = parse_clipboard_data(clipboard_text)

        # -------------------------------------------------
        # [저장] 이어쓰기(Append) 로직 적용
        # -------------------------------------------------
        if len(all_collected_data) > 0:
            print(f"   [성공] 수집된 데이터: {len(all_collected_data)}건")
            df = pd.DataFrame(all_collected_data)
            
            # 중복 제거 (현재 수집분 내에서)
            df_unique = df.drop_duplicates()
            
            # 컬럼명 생성 (A열: 기준일자)
            # col_0: 기준일자, col_1: 품명, col_2: 구분 ...
            cols = ['기준일자', '품명', '구분', '부위', '국가']
            # 나머지 숫자 컬럼들은 동적으로 이름 부여 (중량, 금액 등)
            remaining_cols = [f'데이터_{i}' for i in range(df_unique.shape[1] - 5)]
            df_unique.columns = cols + remaining_cols
            
            # 저장 경로 설정
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir) 
            output_dir_abs = os.path.join(project_root, "data", "0_raw")
            if not os.path.exists(output_dir_abs):
                os.makedirs(output_dir_abs)
            
            save_path = os.path.join(output_dir_abs, OUTPUT_FILENAME)
            
            # [핵심] 파일 존재 여부 확인 후 이어쓰기
            if not os.path.exists(save_path):
                # 파일이 없으면: 헤더 포함해서 새로 생성
                df_unique.to_csv(save_path, index=False, encoding='utf-8-sig', mode='w')
                print(f"\n[신규 생성] 파일이 새로 생성되었습니다.")
            else:
                # 파일이 있으면: 헤더 없이 데이터만 추가 (Append)
                df_unique.to_csv(save_path, index=False, encoding='utf-8-sig', mode='a', header=False)
                print(f"\n[업데이트] 기존 파일에 데이터가 추가되었습니다.")
            
            print(f"   경로: {save_path}")
            print(df_unique.head()) 
            driver.quit()
            return True 
        else:
            print(f"   [실패] 데이터가 수집되지 않았습니다.")
            driver.quit()
            return False 

    except Exception as e:
        print(f"   [오류] {e}")
        if driver:
            driver.quit()
        return False 

def main():
    print(f"=== 미국산 냉동 소고기 수입 데이터 수집 (v29 Append & Date) ===")
    print(f"기준 날짜: {SEARCH_DATE_STR}")
    for i in range(1, MAX_RETRIES + 1):
        success = attempt_crawling(i)
        if success:
            break
        else:
            print("   [재시도] 5초 후 다시 시작...")
            time.sleep(5)

if __name__ == "__main__":
    main()