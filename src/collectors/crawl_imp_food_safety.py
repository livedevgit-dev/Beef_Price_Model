# [파일 정의서]
# - 파일명: crawl_imp_food_safety.py
# - 역할: 수집 (식약처 수입축산물 검역실적)
# - 대상: 수입 소고기 (미국/호주, 냉동 기준)
# - 데이터 소스: 식품안전나라(수입식품정보마루)
# - 주요 기능: 대기 로직(WebDriverWait)을 올바르게 적용하여 안정적인 메뉴 이동 및 데이터 수집
# - 출력: master_import_volume.csv 에 KMTA 미게시 월만 잠정치로 추가 (data_source=MFDS, 단위 톤=kg/1000)
#         KMTA 확정치가 있는 월은 덮어쓰지 않음. KMTA 게시 후 crawl_imp_volume_monthly.py 가 KMTA 로 교체.
# - 실패 처리: 월 조회 3회 실패·국가 선택 실패·기타 예외·기존 파일 읽기 실패 → exit 1 (조용한 [성공] 금지)

import time
import os
import re
import pandas as pd
import urllib3
import sys
import warnings
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
pd.options.mode.chained_assignment = None 

# =========================================================
# 1. 설정 및 경로
# =========================================================
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, MASTER_IMPORT_VOLUME_CSV, ensure_dirs
from utils.selenium_chrome import build_chrome_driver
from utils.io_safe import atomic_to_csv

ensure_dirs()
MASTER_FILE = MASTER_IMPORT_VOLUME_CSV

# =========================================================
# 2. 날짜 계산
# =========================================================
def get_next_month_from_master():
    if not MASTER_FILE.exists():
        print("[정보] 기존 파일이 없습니다. 2019-01-01부터 수집을 시작합니다.")
        return "2019-01-01"

    # 읽기 실패 시 2019-01 부터 재수집하면 KMTA 확정치를 식약처 잠정치로 덮어쓰게 됨 → 예외로 중단
    df = pd.read_csv(str(MASTER_FILE))
    if 'std_date' not in df.columns:
        raise ValueError(f"{MASTER_FILE.name} 에 std_date 컬럼이 없습니다: {list(df.columns)}")
    dt = pd.to_datetime(df['std_date'].astype(str), format='%Y-%m', errors='coerce')
    if dt.isnull().all():
        raise ValueError(f"{MASTER_FILE.name} 의 std_date 를 해석할 수 없습니다 (예: {df['std_date'].iloc[0]})")

    last_date_obj = dt.max()
    print(f"[정보] 기존 데이터 마지막 시점: {last_date_obj.strftime('%Y-%m')}")
    return (last_date_obj + relativedelta(months=1)).strftime("%Y-%m-%d")

# =========================================================
# 3. 드라이버 설정
# =========================================================
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    return build_chrome_driver(chrome_options)

def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def close_any_popup(driver):
    try:
        for btn in driver.find_elements(By.XPATH, "//button[contains(text(), '닫기')]"):
            if btn.is_displayed(): js_click(driver, btn)
    except: pass

def wait_for_loading_bar(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.ID, "___processbar2"))
        )
    except: pass

# =========================================================
# 4. 메뉴 이동 및 옵션 설정
# =========================================================
def move_to_target_menu_robust(driver):
    print("\n[진행] 메뉴 이동: 수입식품 > 일반현황 > 검사실적")
    wait = WebDriverWait(driver, 30)
    
    # [수정] wait.until을 사용하여 요소가 화면에 완전히 렌더링될 때까지 기다림
    menu1 = wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_1")))
    js_click(driver, menu1)
    time.sleep(1)
    
    menu2 = wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_2")))
    js_click(driver, menu2)
    time.sleep(1)
    
    menu3 = wait.until(EC.presence_of_element_located((By.ID, "mf_trv_LeftMenu_label_17")))
    js_click(driver, menu3)
    time.sleep(3)

def set_search_options(driver):
    wait = WebDriverWait(driver, 30)
    wait_for_loading_bar(driver)
    print("[진행] 옵션 설정: 냉동 / 미국, 호주")
    
    # [수정] 옵션 버튼 클릭 전에도 대기 로직 적용
    btn1 = wait.until(EC.presence_of_element_located((By.ID, "mf_win_main_subWindow0_wframe_sbx_prodSssnm_button")))
    js_click(driver, btn1)
    time.sleep(0.5)
    driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_sbx_prodSssnm_itemTable_2").click()
    time.sleep(0.5)

    btn2 = wait.until(EC.presence_of_element_located((By.ID, "mf_win_main_subWindow0_wframe_ccb_SearchNtncd_button")))
    js_click(driver, btn2)
    time.sleep(1)
    try:
        driver.find_element(By.XPATH, "//*[contains(@id, 'itemTable_73')]").click()
        time.sleep(0.2)
        driver.find_element(By.XPATH, "//*[contains(@id, 'itemTable_243')]").click()
    except Exception as e:
        # 국가 미선택 상태로 조회하면 전체 국가가 섞여 건수·스크롤 수집이 틀어짐 → 실패로 처리
        raise RuntimeError(f"국가(미국/호주) 선택 실패: {e}") from e
    js_click(driver, btn2)

# =========================================================
# 5. 스크래핑 로직
# =========================================================
def scrape_with_zoom_logic(driver, total_count):
    data_set = set()
    data_list = []
    rows_locator = (By.CSS_SELECTOR, "#mf_win_main_subWindow0_wframe_grd_gridBox_body_tbody > tr")
    scroll_div = driver.find_element(By.CSS_SELECTOR, "#mf_win_main_subWindow0_wframe_grd_gridBox_scrollY_div")
    
    driver.execute_script("document.body.style.zoom='25%'")
    time.sleep(0.5)
    driver.execute_script("window.dispatchEvent(new Event('resize'));")
    time.sleep(2)

    for i in range(20):
        rows = driver.find_elements(*rows_locator)
        for row in rows:
            try:
                col_data_elements = row.find_elements(By.CSS_SELECTOR, "td > nobr")
                data = tuple(col.text.strip() for col in col_data_elements)
                if data and len(data) > 5 and data not in data_set:
                    data_set.add(data)
                    data_list.append(list(data))
            except: continue
        
        if len(data_set) >= total_count: break
        try:
            scroll_div.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.5)
        except: break

    driver.execute_script("document.body.style.zoom='100%'")
    return data_list

# =========================================================
# 6. 월별 조회 함수
# =========================================================
def crawl_monthly_data(driver, year, month):
    start_dt = f"{year}-{month:02d}-01"
    if month == 12: end_dt = f"{year}-12-31"
    else: end_dt = (datetime(year, month + 1, 1) - relativedelta(days=1)).strftime("%Y-%m-%d")

    for attempt in range(1, 4):
        print(f"\n[조회 시도 {attempt}/3] {start_dt} ~ {end_dt}")
        try:
            wait_for_loading_bar(driver)
            
            inputs = driver.find_elements(By.XPATH, "//*[contains(text(),'처리일자')]/following::input")
            if len(inputs) >= 2:
                inputs[0].clear()
                inputs[0].send_keys(start_dt)
                inputs[1].clear()
                inputs[1].send_keys(end_dt)

            prod_inp = driver.find_element(By.XPATH, "//*[contains(text(),'품명')]/following::input[1]")
            prod_inp.click()
            prod_inp.clear()
            prod_inp.send_keys("소고기")
            driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

            search_btn = driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_btn_search")
            js_click(driver, search_btn)
            
            print(f"[진행] 로딩 중 (최대 40초)... ", end="")
            total_count = 0
            max_wait = 40
            
            for s in range(max_wait):
                try:
                    if driver.find_elements(By.ID, "___processbar2"):
                        if driver.find_element(By.ID, "___processbar2").is_displayed():
                            time.sleep(1)
                            sys.stdout.write(f"{max_wait-s}..")
                            sys.stdout.flush()
                            continue
                    
                    count_el = driver.find_element(By.ID, "mf_win_main_subWindow0_wframe_tbx_listCount")
                    count_text = count_el.text
                    numbers = re.findall(r"\d+", count_text)
                    current_count = int(numbers[0]) if numbers else 0
                    
                    if current_count > 0:
                        total_count = current_count
                        print(f" 완료 (발견: {total_count}건)")
                        break
                    
                    time.sleep(1)
                    sys.stdout.write(f"{max_wait-s}..")
                    sys.stdout.flush()
                except: time.sleep(1)

            if total_count > 0:
                print(f"[진행] 수집 시작...")
                rows = scrape_with_zoom_logic(driver, total_count)
                if len(rows) >= total_count:
                    return pd.DataFrame(rows)
                # 스크롤 수집이 일부만 된 경우 → 부분 데이터로 저장하지 않고 재시도
                print(f"[경고] 일부만 수집됨 ({len(rows)}/{total_count}건)")
                if attempt < 3:
                    driver.refresh()
                    time.sleep(5)
                    move_to_target_menu_robust(driver)
                    set_search_options(driver)
                continue
            else:
                print(f"\n[경고] 데이터 0건 (혹은 로딩 실패)")
                if attempt < 3:
                    print("[진행] 새로고침 후 재시도...")
                    driver.refresh()
                    time.sleep(5)
                    move_to_target_menu_robust(driver)
                    set_search_options(driver)
                continue

        except Exception as e:
            print(f"\n[오류] {str(e)[:50]}...")
            if attempt < 3:
                driver.refresh()
                time.sleep(5)
                move_to_target_menu_robust(driver)
                set_search_options(driver)
    return None

# =========================================================
# 7. KMTA 양식 통합
# =========================================================
def integrate_to_master(new_safety_df):
    """반환: 저장한 월 목록. 실패는 예외로 올린다."""
    if new_safety_df.empty: return []

    new_safety_df = new_safety_df.copy()

    # '전체(국가별)' 행은 부위 칸에 국가명이 들어간 국가 합계 → 부위로 피벗되면 계가 2배가 됨(2026-02~09 실제 발생)
    new_safety_df = new_safety_df[~new_safety_df['구분'].astype(str).str.contains('국가별')]
    new_safety_df = new_safety_df.drop_duplicates(subset=['std_ym', '국가', '부위'], keep='first')
    new_safety_df['당월_소계'] = new_safety_df['당월_소계'].astype(str).str.replace(',', '')
    new_safety_df['당월_소계'] = pd.to_numeric(new_safety_df['당월_소계'], errors='coerce').fillna(0)
    new_safety_df['당월_소계'] = (new_safety_df['당월_소계'] / 1000).round(1)

    pivoted = new_safety_df.pivot_table(
        index=['std_ym', '국가'], 
        columns='부위', 
        values='당월_소계', 
        aggfunc='sum'
    ).reset_index()

    pivoted.rename(columns={'std_ym': 'std_date', '국가': '구분'}, inplace=True)
    
    new_cols_map = {}
    for col in pivoted.columns:
        if col not in ['std_date', '구분']:
            new_cols_map[col] = f"부위별_{col.replace(' ', '')}_합계"
    pivoted.rename(columns=new_cols_map, inplace=True)

    part_cols = [c for c in pivoted.columns if c.startswith('부위별_') and '계_합계' not in c]
    pivoted['부위별_계_합계'] = pivoted[part_cols].sum(axis=1)

    pivoted['data_source'] = 'MFDS'

    if MASTER_FILE.exists():
        master_df = pd.read_csv(str(MASTER_FILE))   # 읽기 실패 시 예외 → 덮어쓰기 안 함
        
        if '구분' not in master_df.columns:
            possible_cols = [c for c in master_df.columns if '구분' in c]
            if possible_cols:
                print(f"[수정] 잘못된 컬럼명 감지 및 수정: {possible_cols[0]} -> 구분")
                master_df.rename(columns={possible_cols[0]: '구분'}, inplace=True)

        if 'data_source' not in master_df.columns:
            raise ValueError("마스터에 data_source 컬럼이 없습니다 — crawl_imp_volume_monthly.py 를 먼저 실행해 백필하세요.")
        master_columns = master_df.columns.tolist()
        pivoted_aligned = pivoted.reindex(columns=master_columns)
        # 계는 마스터에 실제 저장되는 부위 컬럼만으로 재계산 (저장 안 되는 미지 컬럼이 합계에 섞이지 않게)
        master_parts = [c for c in master_columns if c.startswith('부위별_') and c != '부위별_계_합계']
        # 조회는 성공했는데 해당 국가·부위 검역 실적 행이 없는 경우 = 수입 0 (KMTA 도 0 으로 게시) → 0 으로 통일
        pivoted_aligned[master_parts] = pivoted_aligned[master_parts].fillna(0)
        pivoted_aligned['부위별_계_합계'] = pivoted_aligned[master_parts].sum(axis=1).round(1)

        # KMTA 확정치가 이미 있는 월은 잠정치로 덮어쓰지 않음
        kmta_months = set(master_df.loc[master_df['data_source'] == 'KMTA', 'std_date'].astype(str))
        skip = sorted(set(pivoted_aligned['std_date'].astype(str)) & kmta_months)
        if skip:
            print(f"[정보] KMTA 확정치가 있는 월은 건너뜀: {skip}")
            pivoted_aligned = pivoted_aligned[~pivoted_aligned['std_date'].astype(str).isin(skip)]
        if pivoted_aligned.empty:
            return []

        target_dates = pivoted_aligned['std_date'].unique()
        master_df = master_df[~master_df['std_date'].isin(target_dates)]
        
        final_df = pd.concat([master_df, pivoted_aligned], axis=0, ignore_index=True)
    else:
        final_df = pivoted

    try:
        final_df = final_df.sort_values(by=['std_date', '구분'], ascending=[False, True])
    except KeyError:
        print("[경고] 정렬 기준 컬럼('구분')을 찾을 수 없어 날짜로만 정렬합니다.")
        final_df = final_df.sort_values(by=['std_date'], ascending=False)

    atomic_to_csv(final_df, str(MASTER_FILE), index=False, encoding='utf-8-sig')
    saved = sorted(final_df.loc[final_df['data_source'] == 'MFDS', 'std_date'].astype(str).unique())
    saved = [m for m in saved if m in set(pivoted['std_date'].astype(str))]
    print(f"[완료] 통합 저장 완료 (합계 컬럼 재계산됨, data_source=MFDS): {saved}")
    return saved

# =========================================================
# 8. 메인 실행
# =========================================================
def main():
    """반환: 종료 코드 (0=정상/수집할 월 없음, 1=한 달이라도 실패)"""
    print("="*60)
    print("[수집기] 식약처 데이터 (오류 수정 및 안정화 버전)")

    try:
        start_date_str = get_next_month_from_master()
    except Exception as e:
        print(f"[실패] 기존 마스터 파일을 읽을 수 없어 중단합니다 (덮어쓰기 방지): {e}")
        return 1

    today = datetime.now()
    last_day_prev_month = today.replace(day=1) - timedelta(days=1)
    end_date_str = last_day_prev_month.strftime("%Y-%m-%d")

    print(f"[설정] 목표 수집 구간: {start_date_str} ~ {end_date_str}")

    if start_date_str > end_date_str:
        print("[완료] 업데이트할 데이터가 없습니다.")
        return 0

    failed, saved = [], []
    driver = None
    try:
        driver = setup_driver()
        driver.get("https://impfood.mfds.go.kr/ifs/websquare/websquare.html?w2xPath=/ifs/ui/index.xml")
        time.sleep(5)

        close_any_popup(driver)
        move_to_target_menu_robust(driver)
        set_search_options(driver)

        date_range = pd.date_range(start=start_date_str, end=end_date_str, freq='MS')

        for target_date in date_range:
            ym = target_date.strftime("%Y-%m")
            result = crawl_monthly_data(driver, target_date.year, target_date.month)

            if not isinstance(result, pd.DataFrame) or result.empty:
                print(f"[실패] {ym} 조회 3회 모두 실패 — 저장하지 않음")
                failed.append(ym)
                continue

            col_names = [
                '품명', '구분', '부위', '국가',
                '전년도_누계', '전년도_12월_누계',
                '당월_상순', '당월_중순', '당월_하순', '당월_소계', '당해년도_누계'
            ]
            if result.shape[1] < len(col_names):
                print(f"[실패] {ym} 결과 열 {result.shape[1]}개 (기대 {len(col_names)}) — 표 구조 변경?")
                failed.append(ym)
                continue
            result = result.iloc[:, :len(col_names)]
            result.columns = col_names
            result.insert(0, 'std_ym', ym)

            mask = result['국가'].astype(str).str.contains('미국|호주')
            df_filtered = result[mask].copy()

            if df_filtered.empty:
                print(f"[실패] {ym} 미국/호주 데이터 없음 (국가 필터·조회 조건 확인)")
                failed.append(ym)
                continue
            saved += integrate_to_master(df_filtered)
            time.sleep(2)

    except Exception as e:
        print(f"\n[실패] 에러 발생: {e}")
        failed.append(f"예외: {str(e)[:80]}")
    finally:
        if driver: driver.quit()

    if failed:
        print(f"\n[실패] 식약처 수집 실패: {failed} / 저장된 월: {saved or '-'}")
        return 1
    print(f"\n[성공] 모든 업데이트 완료. 저장된 월: {saved or '-'}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
