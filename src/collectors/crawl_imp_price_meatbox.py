from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import time
import os
import re
import shutil
from datetime import datetime
from io import StringIO

# [파일 정의서]
# - 파일명: crawl_imp_price_meatbox.py
# - 역할: 수집 및 데이터 경량화
# - 대상: 수입육 (미트박스)
# - 방식: 로컬 드라이버 사용 (방화벽 우회)

URL = "https://www.meatbox.co.kr/fo/sise/siseListPage.do"

def get_price_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    
    # [핵심] 사내망 방화벽 우회를 위해 로컬 chromedriver.exe 강제 사용
    driver_path = os.path.join(src_dir, "chromedriver.exe")
    
    project_root = os.path.dirname(src_dir)
    processed_dir = os.path.join(project_root, "data", "1_processed")
    
    master_file = os.path.join(processed_dir, "master_price_data.csv")
    backup_file = os.path.join(processed_dir, "master_price_data_backup_full.csv")
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    target_cols = ['date', 'part_name', 'country', 'wholesale_price', 'brand']

    print("="*60)
    print(f"[시스템] 미트박스 시세 수집 (로컬 드라이버 모드)")
    print("="*60)

    # 1. 파일 최적화 (기존 유지)
    if os.path.exists(master_file):
        try:
            shutil.copy(master_file, backup_file)
            df_master = pd.read_csv(master_file)
            for col in target_cols:
                if col not in df_master.columns:
                    df_master[col] = '-' if col == 'brand' else ""
            df_master = df_master[target_cols] 
            cond_empty = df_master['part_name'].isna() | (df_master['part_name'] == '')
            cond_today = df_master['date'] == today_date
            df_master = df_master[~(cond_empty | cond_today)]
            print(f"[파일 정리] 기존 파일 최적화 완료 (잔여 {len(df_master)}행)")
        except Exception as e:
            df_master = pd.DataFrame(columns=target_cols) 
    else:
        df_master = pd.DataFrame(columns=target_cols)

    # 2. 크롤링
    chrome_options = Options()
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    
    if os.path.exists(driver_path):
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        print("\n[에러] src 폴더에 chromedriver.exe 파일이 없습니다. 버전에 맞춰 다운로드 해주세요.")
        return

    driver.maximize_window()
    driver.implicitly_wait(10)
    driver.get(URL)
    
    raw_dfs = []
    current_page = 1 
    
    try:
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))

        while True:
            print(f"[수집] {current_page}페이지... ", end="")
            html = driver.page_source
            try:
                dfs = pd.read_html(StringIO(html))
                candidates = [df for df in dfs if len(df) > 1 and ("품목" in " ".join([str(c) for c in df.columns]) or "보관" in " ".join([str(c) for c in df.columns]))]
                if candidates:
                    target_df = max(candidates, key=len)
                    raw_dfs.append(target_df)
                    print(f"OK ({len(target_df)}건)")
                else:
                    print("Skip")
            except Exception:
                print("Err")

            time.sleep(1.5) 
            next_page = current_page + 1
            moved = False
            
            for attempt in range(3):
                try:
                    target_btn = driver.find_element(By.XPATH, f"//a[normalize-space()='{next_page}']")
                except:
                    try: target_btn = driver.find_element(By.XPATH, "//a[contains(@class, 'next')]")
                    except: target_btn = None
                
                if target_btn:
                    driver.execute_script("arguments[0].click();", target_btn)
                    moved = True
                    break
                time.sleep(1)
            
            if moved:
                current_page += 1
                time.sleep(1)
            else:
                break
            
    except Exception as e:
        print(f"\n[에러] 크롤링 중단: {e}")
    finally:
        driver.quit()
        
    # 3. 데이터 저장 (기존 유지)
    if raw_dfs:
        full_df = pd.concat(raw_dfs, ignore_index=True)
        try:
            clean_df = full_df.iloc[:, [1, 3, 4]].copy()
            clean_df.columns = ['품목명', '보관', '도매시세_raw']
            clean_df['품목명'] = clean_df['품목명'].astype(str).str.replace('관심상품 등록하기', '', regex=False).str.strip()
            clean_df = clean_df[clean_df['보관'].astype(str).str.contains("냉동")]
            clean_df['원산지'] = clean_df['품목명'].apply(lambda x: '미국' if '미국' in str(x) else ('호주' if '호주' in str(x) else '기타'))
            clean_df = clean_df[clean_df['원산지'] != '기타']
            
            def extract_price(text):
                digits = re.sub(r'[^0-9]', '', str(text).split('원')[0])
                return int(digits) if digits else 0
            
            clean_df['도매시세'] = clean_df['도매시세_raw'].apply(extract_price)
            clean_df = clean_df[clean_df['도매시세'] > 0].reset_index(drop=True)

            final_df = pd.DataFrame({
                'date': [today_date] * len(clean_df),
                'part_name': clean_df['품목명'].tolist(),
                'country': clean_df['원산지'].tolist(),
                'wholesale_price': clean_df['도매시세'].tolist(),
                'brand': ['-'] * len(clean_df)
            })
            
            new_master_df = pd.concat([df_master, final_df], ignore_index=True).sort_values(by=['date', 'country', 'part_name'])
            new_master_df.to_csv(master_file, index=False, encoding='utf-8-sig')
            
            print(f"\n[성공] 데이터 저장 완료! (오늘 수집: {len(final_df)}건)")

        except Exception as e:
            print(f"[오류] 데이터 저장 실패: {e}")

if __name__ == "__main__":
    get_price_data()