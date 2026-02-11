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
# - 역할: 수집 및 데이터 경량화 (불필요 컬럼 제거)
# - 대상: 수입육 (미트박스)
# - 방식: 일반 브라우저 모드 (Headless X)

URL = "https://www.meatbox.co.kr/fo/sise/siseListPage.do"

def get_price_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 드라이버 경로 (src 폴더에 chromedriver.exe가 있음)
    src_dir = os.path.dirname(current_dir)
    driver_path = os.path.join(src_dir, "chromedriver.exe")
    
    # 경로 설정 (프로젝트 루트: src의 부모 디렉토리)
    project_root = os.path.dirname(src_dir)
    processed_dir = os.path.join(project_root, "data", "1_processed")
    
    master_file = os.path.join(processed_dir, "master_price_data.csv")
    backup_file = os.path.join(processed_dir, "master_price_data_backup_full.csv")
    
    today_date = datetime.now().strftime("%Y-%m-%d")

    # [핵심] 우리가 남길 최종 컬럼 정의
    target_cols = ['date', 'part_name', 'country', 'wholesale_price', 'brand']

    print("="*60)
    print(f"[시스템] 미트박스 시세 수집 (일반 브라우저 모드)")
    print(f"[설정] 저장 컬럼: {target_cols}")
    print("="*60)

    # 1. [사전 최적화] 기존 파일 로드 및 불필요 컬럼 제거
    if os.path.exists(master_file):
        try:
            # 혹시 모르니 전체 백업 한 번 생성
            shutil.copy(master_file, backup_file)
            
            # 로드
            df_master = pd.read_csv(master_file)
            
            # 기존 컬럼 정리
            for col in target_cols:
                if col not in df_master.columns:
                    df_master[col] = '-' if col == 'brand' else ""
            
            df_master = df_master[target_cols] 

            # 오늘 날짜 중복 및 빈 데이터 제거
            cond_empty = df_master['part_name'].isna() | (df_master['part_name'] == '')
            cond_today = df_master['date'] == today_date
            
            df_master = df_master[~(cond_empty | cond_today)]
            
            print(f"[파일 정리] 기존 파일 최적화 완료 (잔여 {len(df_master)}행)")
                
        except Exception as e:
            print(f"[경고] 파일 정리 중 오류 (진행함): {e}")
            df_master = pd.DataFrame(columns=target_cols) 
    else:
        df_master = pd.DataFrame(columns=target_cols)

    # ------------------------------------------------------------------
    # 2. [크롤링] 데이터 수집 (Headless 해제)
    # ------------------------------------------------------------------
    chrome_options = Options()
    
    # ★ Headless 모드 주석 처리 (창이 뜨도록 설정)
    # chrome_options.add_argument("--headless") 
    
    # [중요] 봇 탐지 회피를 위한 User-Agent 설정 (사람인 척하기)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--start-maximized") # 시작할 때 창 최대화

    # 불필요한 로그 숨기기
    chrome_options.add_argument("--log-level=3")
    
    if os.path.exists(driver_path):
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    # 창 최대화 (확실하게)
    driver.maximize_window()
    driver.implicitly_wait(10)
    
    print(f"\n[수집] 사이트 접속 중... (브라우저를 확인하세요)")
    driver.get(URL)
    
    raw_dfs = []
    current_page = 1 
    
    try:
        # 페이지 로딩 대기 (테이블이 뜰 때까지)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))

        while True:
            print(f"[수집] {current_page}페이지... ", end="")
            
            # 페이지 소스 가져오기
            html = driver.page_source
            
            try:
                # 테이블 파싱
                dfs = pd.read_html(StringIO(html))
                candidates = []
                for df in dfs:
                    cols_str = " ".join([str(c) for c in df.columns])
                    if "품목" in cols_str or "보관" in cols_str:
                        if len(df) > 1: candidates.append(df)
                
                if candidates:
                    target_df = max(candidates, key=len)
                    raw_dfs.append(target_df)
                    print(f"OK ({len(target_df)}건)")
                else:
                    print("Skip (테이블 없음)")

            except Exception as e:
                print(f"Err (파싱 실패)")

            # 다음 페이지 이동 로직
            time.sleep(1.5) # 사람이 누르는 것처럼 약간 대기

            next_page = current_page + 1
            moved = False
            
            # 페이지 버튼 클릭 시도 (3회 재시도)
            for attempt in range(3):
                try:
                    target_btn = None
                    try:
                        # 숫자 버튼 찾기
                        target_btn = driver.find_element(By.XPATH, f"//a[normalize-space()='{next_page}']")
                    except NoSuchElementException:
                        # 숫자 버튼 없으면 '다음(Next)' 화살표 찾기
                        target_btn = driver.find_element(By.XPATH, "//a[contains(@class, 'next')]")
                    
                    if target_btn:
                        driver.execute_script("arguments[0].click();", target_btn)
                        moved = True
                        break # 성공하면 재시도 종료
                except:
                    time.sleep(1)
            
            if moved:
                current_page += 1
                time.sleep(1) # 페이지 로딩 대기
            else:
                print("\n[수집] 더 이상 페이지가 없거나 마지막입니다.")
                break
            
    except Exception as e:
        print(f"\n[에러] 크롤링 중단: {e}")
    finally:
        driver.quit()
        print("[종료] 브라우저를 닫았습니다.")
        
    # 3. [데이터 병합] 필요한 5개 컬럼만 생성
    if raw_dfs:
        full_df = pd.concat(raw_dfs, ignore_index=True)
        
        try:
            # 전처리
            clean_df = full_df.iloc[:, [1, 3, 4]].copy()
            clean_df.columns = ['품목명', '보관', '도매시세_raw']
            
            # "관심상품 등록하기" 텍스트 제거
            clean_df['품목명'] = clean_df['품목명'].astype(str).str.replace('관심상품 등록하기', '', regex=False).str.strip()
            
            clean_df = clean_df[clean_df['보관'].astype(str).str.contains("냉동")]
            clean_df['원산지'] = clean_df['품목명'].apply(lambda x: '미국' if '미국' in str(x) else ('호주' if '호주' in str(x) else '기타'))
            clean_df = clean_df[clean_df['원산지'] != '기타']
            
            def extract_price(text):
                text = str(text)
                digits = re.sub(r'[^0-9]', '', text.split('원')[0])
                return int(digits) if digits else 0
            
            clean_df['도매시세'] = clean_df['도매시세_raw'].apply(extract_price)
            clean_df = clean_df[clean_df['도매시세'] > 0]
            
            clean_df = clean_df.reset_index(drop=True)

            # 데이터 딕셔너리 생성
            data_dict = {
                'date': [today_date] * len(clean_df),
                'part_name': clean_df['품목명'].tolist(),
                'country': clean_df['원산지'].tolist(),
                'wholesale_price': clean_df['도매시세'].tolist(),
                'brand': ['-'] * len(clean_df)
            }
            
            final_df = pd.DataFrame(data_dict)
            
            new_master_df = pd.concat([df_master, final_df], ignore_index=True)
            new_master_df = new_master_df.sort_values(by=['date', 'country', 'part_name'])
            
            new_master_df.to_csv(master_file, index=False, encoding='utf-8-sig')
            
            print("\n" + "="*60)
            print(f"✅ 수집 및 저장 완료!")
            print(f"📊 최종 데이터: {len(new_master_df)}행 (오늘 수집: {len(final_df)}건)")
            print("="*60)

        except Exception as e:
            print(f"[오류] 데이터 저장 실패: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n[경고] 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    get_price_data()