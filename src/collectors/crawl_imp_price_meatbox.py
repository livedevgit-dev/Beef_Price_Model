# [파일 정의서]
# - 파일명: crawl_imp_price_meatbox.py
# - 역할: 수집
# - 대상: 수입육
# - 데이터 소스: 미트박스
# - 주요 기능: StaleElement 에러를 방지하며 일일 B2B 도매가를 수집하는 로직

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import time
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from io import StringIO

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED
from utils.selenium_chrome import build_chrome_driver

URL = "https://www.meatbox.co.kr/fo/sise/siseListPage.do"


def dismiss_meatbox_overlays(driver, rounds: int = 3) -> None:
    """
    광고·프로모션(Braze 인앱), dim 레이어, bPopup 계열이 시세 테이블을 가리는 경우 제거/닫기.
    사이트 구조가 바뀌면 셀렉터를 보강해야 할 수 있음.
    """
    close_selectors = (
        "#btnCloseJoinBanner",
        "a.b-close",
        "button.banner_close",
        ".banner_close:not(script)",
        ".search_area .search_con .search_bottom .close",
        ".grade_confirm",
    )
    strip_overlay_js = """
        document.querySelectorAll(
            '.ab-iam-root, .ab-iam-root-v3, iframe[src*="braze"], iframe[src*="appboy"]'
        ).forEach(function(el) { el.remove(); });
        document.body.classList.remove('ab-pause-scrolling');
        document.documentElement.classList.remove('ab-pause-scrolling');
        document.querySelectorAll('.dim-layer').forEach(function(el) { el.remove(); });
    """
    for _ in range(rounds):
        try:
            driver.execute_script(strip_overlay_js)
        except Exception:
            pass
        for sel in close_selectors:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
            except Exception:
                continue
        try:
            driver.execute_script(
                "if (window.jQuery) { try { jQuery('.b-close:visible').first().click(); } catch(e) {} }"
            )
        except Exception:
            pass
        # 신규가입/프로모션 등 중앙 모달의 "닫기" (카피는 바뀌어도 버튼 문구가 유지되는 경우가 많음)
        for xpath in ("//*[self::button or self::a][normalize-space()='닫기']",):
            try:
                for el in driver.find_elements(By.XPATH, xpath):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
            except Exception:
                continue
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass
        time.sleep(0.25)


def get_price_data():
    master_file = DATA_PROCESSED / "master_price_data.csv"
    backup_file = DATA_PROCESSED / "master_price_data_backup_full.csv"
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    target_cols = ['date', 'part_name', 'country', 'wholesale_price', 'brand']

    print("="*60)
    print("[시스템] 미트박스 시세 수집")
    print("="*60)

    # 1. 파일 최적화
    if master_file.exists():
        try:
            shutil.copy(str(master_file), str(backup_file))
            df_master = pd.read_csv(str(master_file))
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

    driver = build_chrome_driver(chrome_options)

    driver.maximize_window()
    driver.implicitly_wait(10)
    driver.get(URL)
    time.sleep(1.5)
    dismiss_meatbox_overlays(driver)

    raw_dfs = []
    current_page = 1 
    
    try:
        wait = WebDriverWait(driver, 20)

        while True:
            dismiss_meatbox_overlays(driver)
            # [핵심 수정 1] 매 페이지마다 테이블 요소가 나타날 때까지 대기하도록 반복문 안으로 이동
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
            time.sleep(1) # 자바스크립트가 데이터를 화면에 완전히 그릴 수 있도록 약간의 여유 확보
            
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
            
            # [핵심 수정 2] 클릭 시 발생하는 StaleElement 방지 및 재시도 로직 강화
            for attempt in range(3):
                try:
                    target_btn = driver.find_element(By.XPATH, f"//a[normalize-space()='{next_page}']")
                except:
                    try: target_btn = driver.find_element(By.XPATH, "//a[contains(@class, 'next')]")
                    except: target_btn = None
                
                if target_btn:
                    try:
                        driver.execute_script("arguments[0].click();", target_btn)
                        moved = True
                        break
                    except StaleElementReferenceException:
                        # 클릭 순간에 DOM이 변경되어 에러가 나면 1초 대기 후 다시 요소를 찾음
                        time.sleep(1)
                        continue
                time.sleep(1)
            
            if moved:
                current_page += 1
            else:
                break
            
    except Exception as e:
        print(f"\n[에러] 크롤링 중단: {e}")
    finally:
        driver.quit()
        
    # 3. 데이터 저장
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
            new_master_df.to_csv(str(master_file), index=False, encoding='utf-8-sig')
            
            print(f"\n[성공] 데이터 저장 완료! (오늘 수집: {len(final_df)}건)")

        except Exception as e:
            print(f"[오류] 데이터 저장 실패: {e}")

if __name__ == "__main__":
    get_price_data()