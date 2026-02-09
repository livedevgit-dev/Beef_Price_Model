import time
import pandas as pd
import os
import re
import urllib3
import random
from datetime import datetime
from io import StringIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException

# [파일 정의서]
# - 파일명: crawl_imp_meatbox_id_list.py
# - 역할: 수집 (ID 리스트 확보 및 마스터 데이터 생성)
# - 대상: 미트박스 웹사이트 전체 리스트
# - 출력 포맷: beef_price_history.xlsx와 동일한 구조 + siseSeq(ID)
# - 주요 기능: 
#   1. 전체 페이지 무차별 수집 (Vacuum Mode)
#   2. 데일리 수집기와 동일한 파싱 로직 적용 (포맷 통일)
#   3. 이모지 제거 및 안전한 텍스트 처리

# 보안 설정
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['WDM_SSL_VERIFY'] = '0' 

def get_meatbox_id_formatted():
    # ------------------------------------------------------------------
    # [1] 설정 및 경로 준비
    # ------------------------------------------------------------------
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    save_dir = os.path.join(project_root, 'data', '0_raw')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    # 중간 저장 (백업용)
    raw_excel_path = os.path.join(save_dir, "meatbox_raw_full_rows.xlsx")
    # 최종 결과 (ID 리스트)
    final_file_path = os.path.join(save_dir, "meatbox_id_list.xlsx")

    target_url = "https://www.meatbox.co.kr/fo/sise/siseListPage.do"
    today_date = datetime.now().strftime("%Y-%m-%d")

    print("[시작] 미트박스 ID 수집기 (Beef Price 포맷 일치화 모드)")
    
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') 
    
    # ------------------------------------------------------------------
    # [2] 1단계: 웹 데이터 수집 (Scraping Phase)
    # ------------------------------------------------------------------
    all_raw_htmls = [] # HTML 소스만 모음
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.maximize_window()
        driver.get(target_url)
        
        print("\n" + "="*60)
        print("[대기] 20초간 팝업을 닫아주세요. (봇 대기 중...)")
        print("="*60 + "\n")
        time.sleep(20) 

        current_page = 1
        
        while True:
            print(f"[페이지 {current_page}] 데이터 수집 중...", end=" ")
            
            rows = []
            for attempt in range(5):
                temp_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                if len(temp_rows) > 5:
                    rows = temp_rows
                    break
                time.sleep(1)
            
            if not rows:
                print(f"[경고] 데이터를 찾지 못했습니다.")
            else:
                count = 0
                for row in rows:
                    try:
                        # 나중에 정밀 파싱을 위해 HTML을 통째로 저장
                        html_data = row.get_attribute('outerHTML')
                        all_raw_htmls.append(html_data)
                        count += 1
                    except:
                        continue
                print(f"-> {count}개 행 확보 (누적 {len(all_raw_htmls)}개)")

            # 다음 페이지 이동
            next_page = current_page + 1
            moved = False
            try:
                target_btn = driver.find_element(By.XPATH, f"//a[contains(text(), '{next_page}')]")
                driver.execute_script("arguments[0].click();", target_btn)
                moved = True
            except NoSuchElementException:
                try:
                    target_btn = driver.find_element(By.XPATH, "//a[contains(@class, 'next')]")
                    driver.execute_script("arguments[0].click();", target_btn)
                    moved = True
                except:
                    moved = False

            if moved:
                current_page += 1
                time.sleep(3.5) 
            else:
                print("\n[수집 종료] 페이지 순회 완료.")
                break

    except Exception as e:
        print(f"[에러] 수집 중 중단: {e}")
    finally:
        driver.quit()

    # ------------------------------------------------------------------
    # [3] 2단계: 데이터 정제 및 포맷팅 (Processing Phase)
    # ------------------------------------------------------------------
    if not all_raw_htmls:
        print("[실패] 수집된 데이터가 없습니다.")
        return

    print("\n[가공] 수집된 데이터를 'Beef Price' 포맷으로 변환합니다...")

    formatted_results = []

    for html in all_raw_htmls:
        try:
            # 1. HTML을 테이블 형태로 감싸서 판다스로 파싱 (데일리 수집기와 동일 방식)
            table_html = f"<table>{html}</table>"
            dfs = pd.read_html(StringIO(table_html))
            if not dfs: continue
            
            row_df = dfs[0]
            
            # 컬럼 인덱스로 데이터 추출 (crawl_imp_price_meatbox.py 로직 참조)
            # 보통 [체크박스, 품목, 등급, 보관, 도매시세, 버튼] 순서 (0, 1, 2, 3, 4, 5)
            # 안전하게 컬럼 개수 확인
            if len(row_df.columns) < 5: continue
            
            item_name = str(row_df.iloc[0, 1]) # 품목명
            storage = str(row_df.iloc[0, 3])   # 보관
            price_raw = str(row_df.iloc[0, 4]) # 도매시세
            
            # 2. ID (siseSeq) 추출
            found_ids = re.findall(r'(\d{8})', html)
            sise_seq = None
            for num in found_ids:
                if not num.startswith("202"):
                    sise_seq = num
                    break
            if not sise_seq:
                match = re.search(r"['\"](\d{7,10})['\"]", html)
                if match: sise_seq = match.group(1)
            
            if not sise_seq: continue

            # 3. 데이터 정제 (데일리 수집기와 동일 로직)
            # 가격 숫자만 추출
            digits = re.sub(r'[^0-9]', '', price_raw.split('원')[0])
            price = int(digits) if digits else 0
            
            # 원산지 추출
            origin = '미국' if '미국' in item_name else ('호주' if '호주' in item_name else '기타')
            
            # 필터링 (냉동 + 미국/호주)
            if '냉동' not in storage: continue
            if origin == '기타': continue

            # 결과 담기 (포맷 통일)
            formatted_results.append({
                '기준일자': today_date,
                '품목명': item_name,
                '원산지': origin,
                '보관': storage,
                '도매시세': price,
                'siseSeq': sise_seq  # [핵심] ID 추가
            })

        except Exception:
            continue

    # ------------------------------------------------------------------
    # [4] 최종 저장
    # ------------------------------------------------------------------
    if formatted_results:
        df_final = pd.DataFrame(formatted_results)
        
        # 컬럼 순서 지정 (보기 좋게)
        cols = ['기준일자', '품목명', '원산지', '보관', '도매시세', 'siseSeq']
        df_final = df_final[cols]
        
        # 중복 제거 (ID 기준)
        df_final = df_final.drop_duplicates(subset=['siseSeq'])
        
        df_final.to_excel(final_file_path, index=False)
        
        print("=" * 60)
        print(f"[최종 완료] 총 {len(df_final)}개의 품목을 포맷팅하여 저장했습니다.")
        print(f"[파일 저장] {final_file_path}")
        print("=" * 60)
        print(df_final.head())
        print("-" * 60)
        print("이제 beef_price_history.xlsx 파일과 직접 비교(VLOOKUP 등)가 가능합니다.")
    else:
        print("[실패] 조건에 맞는 데이터가 없습니다.")

if __name__ == "__main__":
    get_meatbox_id_formatted()