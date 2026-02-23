import os
import time
import pandas as pd
import pyperclip
import pyautogui
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# 셀레니움 관련
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
# src/chromedriver.exe 통일 사용 (버전업 시 src 폴더만 교체)

# [핵심 변경] 수집 범위 확대 (2019년 ~ 2024년 11월)
START_DATE = "2019-01-01"  
END_DATE = "2024-11-30"    

TARGET_URL = "https://impfood.mfds.go.kr/ifs/websquare/websquare.html?w2xPath=/ifs/ui/index.xml"

# 안정적인 수집을 위한 대기 시간 (35초)
WAIT_TIME_RENDER = 35  
USA_DOWN_COUNT = 75
ZOOM_LEVELS = 7
MAX_RETRIES_PER_MONTH = 3

def get_driver():
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    driver_path_abs = os.path.join(src_dir, "chromedriver.exe")
    service = Service(driver_path_abs)
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def ensure_iframe_context(driver):
    try:
        driver.switch_to.default_content()
        time.sleep(0.5)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if len(iframes) > 0:
            driver.switch_to.frame(0)
    except:
        pass

# =========================================================
# 순정 복사 함수 (가장 안정적)
# =========================================================
def simple_copy():
    # Ctrl+A -> 대기 -> Ctrl+C -> 대기 (단순하지만 확실함)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(2.0)
    pyautogui.hotkey('ctrl', 'c')
    time.sleep(1.0)
    pyautogui.hotkey('ctrl', 'c') # 확인 사살
    time.sleep(2.0)
    return pyperclip.paste()

def zoom_browser(direction="out", times=1):
    if direction == "reset":
        pyautogui.hotkey('ctrl', '0')
        time.sleep(1.0)
        return
    key = '-' if direction == "out" else '+'
    for _ in range(times):
        pyautogui.hotkey('ctrl', key)
        time.sleep(0.1)
    time.sleep(2.0)

# =========================================================
# 데이터 파싱 (당월 누계 = 뒤에서 2번째 열)
# =========================================================
def parse_data(full_text, year_month):
    if not full_text: return []
    lines = full_text.split('\n')
    data_list = []
    
    for line in lines:
        if "소고기" in line and "미국" in line and "냉동" in line:
            parts = line.split()
            if len(parts) >= 8:
                if "합계" in line: continue
                try:
                    # [검증 완료] 뒤에서 2번째 열이 '당월 누계'임
                    target_val_str = parts[-2]
                    
                    row = {
                        '년월': year_month,
                        '부위': parts[2],
                        '중량': float(target_val_str.replace(',', ''))
                    }
                    data_list.append(row)
                except:
                    continue
    return data_list

# =========================================================
# 1달 수집 프로세스 (브라우저 재실행 방식)
# =========================================================
def collect_one_month(target_ym, start_str, end_str):
    driver = None
    try:
        driver = get_driver()
        driver.get(TARGET_URL)
        time.sleep(5)
        
        # 메뉴 이동
        wait = WebDriverWait(driver, 20)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='수입식품']"))).click()
        time.sleep(1)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[text()='일반현황']"))).click()
        time.sleep(1)
        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '냉장/냉동-부위-국가 검사실적')]"))).click()
        time.sleep(8) 

        ensure_iframe_context(driver)

        # 입력 필드 이동
        actions = ActionChains(driver)
        for _ in range(5): actions.send_keys(Keys.TAB)
        actions.perform()
        
        # 날짜 입력
        actions = ActionChains(driver)
        actions.send_keys(start_str).perform()
        time.sleep(0.5)
        
        actions = ActionChains(driver)
        actions.send_keys(Keys.TAB).send_keys(Keys.TAB).send_keys(end_str).perform()
        time.sleep(0.5)
        
        ActionChains(driver).send_keys(Keys.TAB).send_keys(Keys.TAB).send_keys(Keys.TAB).perform()
        
        # 구분: 냉동
        actions = ActionChains(driver)
        actions.send_keys(Keys.ARROW_DOWN).send_keys(Keys.ARROW_DOWN).perform()
        time.sleep(0.5)
        
        # 국가: 미국
        ActionChains(driver).send_keys(Keys.TAB).perform()
        actions = ActionChains(driver)
        for _ in range(USA_DOWN_COUNT):
            actions.send_keys(Keys.ARROW_DOWN)
        actions.perform()
        
        ActionChains(driver).send_keys(Keys.SPACE).perform()
        time.sleep(1.0) 
        
        # 조회 (Enter)
        # 브라우저가 매번 새로 열리므로 Enter 키가 확실하게 작동합니다.
        print(f"   [실행] Enter 입력! ({WAIT_TIME_RENDER}초 대기)")
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(WAIT_TIME_RENDER) 
        
        # 수집
        ensure_iframe_context(driver)
        zoom_browser("out", ZOOM_LEVELS)
        text = simple_copy()
        zoom_browser("reset")
        
        driver.quit()
        time.sleep(2) # 프로세스 정리 시간
        
        return parse_data(text, target_ym)

    except Exception as e:
        print(f"   [오류] {e}")
        if driver: 
            try: driver.quit()
            except: pass
        return []

def main():
    print(f"=== 미국산 소고기 데이터 대규모 수집 (2019 ~ 2024) ===")
    
    # 저장 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    output_dir = os.path.join(project_root, "data", "0_raw")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_csv = os.path.join(output_dir, "미국산소고기_2019_2024_Total.csv")
    
    print(f"저장 위치: {output_csv}")
    print("[경고] 예상 소요시간: 약 70~80분")
    print("[경고] 실행 중 PC 사용 금지 (화면 보호기 해제 확인!)")
    
    if os.path.exists(output_csv):
        try: os.remove(output_csv)
        except: pass

    start_dt = datetime.strptime(START_DATE, "%Y-%m-%d")
    end_dt = datetime.strptime(END_DATE, "%Y-%m-%d")
    current_dt = start_dt
    
    total_months = (end_dt.year - start_dt.year) * 12 + end_dt.month - start_dt.month + 1
    processed_count = 0

    while current_dt <= end_dt:
        processed_count += 1
        month_str = current_dt.strftime("%Y-%m")
        m_start = current_dt.strftime("%Y-%m-%d")
        next_month = current_dt + relativedelta(months=1)
        m_end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"\n[{processed_count}/{total_months}] {month_str} 조회 중...")
        
        success = False
        for attempt in range(1, MAX_RETRIES_PER_MONTH + 1):
            if attempt > 1:
                print(f"   [재시도] {attempt}/{MAX_RETRIES_PER_MONTH}...")
                time.sleep(10)
            
            parsed_data = collect_one_month(month_str, m_start, m_end)
            
            if parsed_data and len(parsed_data) > 0:
                print(f"   [완료] 성공! {len(parsed_data)}건 저장")
                
                # 로그에 총 중량 찍어주기 (진행상황 모니터링용)
                total_w = sum([d['중량'] for d in parsed_data])
                print(f"      -> {month_str} 총량: {total_w:,.0f}kg")

                df_temp = pd.DataFrame(parsed_data)
                if not os.path.exists(output_csv):
                    df_temp.to_csv(output_csv, index=False, encoding='utf-8-sig', mode='w')
                else:
                    df_temp.to_csv(output_csv, index=False, encoding='utf-8-sig', mode='a', header=False)
                success = True
                break 
            else:
                print(f"   [실패] 실패 (데이터 없음)")
        
        if not success:
            print(f"   [실패] {month_str} 수집 최종 실패.")
        
        current_dt = next_month
        # 다음 브라우저 켜기 전 충분한 휴식
        time.sleep(3) 

    print(f"\n[완료] 전체 수집 완료! '미국산소고기_2019_2024_Total.csv' 확인")
    
    # 완료 알림음
    try:
        import winsound
        winsound.Beep(1000, 1000)
    except:
        pass

if __name__ == "__main__":
    main()