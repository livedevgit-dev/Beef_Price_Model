# [파일 정의서]
# - 파일명: collect_cafe_b2b.py
# - 역할: 수집
# - 대상: 공통
# - 데이터 소스: 미트피플 다음 카페 (구매/판매 게시판)
# - 수집/가공 주기: 일단위
# - 주요 기능: 완전 수동 로그인 후, 가상 물리 마우스(ActionChains)와 사람의 스크롤/지연시간을 모사하여 봇 탐지를 우회하며 전일자 게시글을 수집

import os
import time
import random
from datetime import datetime, timedelta
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup

# 프로젝트 config 경로 변수 임포트
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_RAW, RAW_CAFE_CRAWLING_CSV

# 타겟 게시판 URL
BOARDS = {
    "구매": "https://cafe.daum.net/meetpeople/HoTs",
    "판매": "https://cafe.daum.net/meetpeople/HoUW"
}

def init_driver():
    """크롬 드라이버 초기화 및 봇 탐지 우회 옵션 설정"""
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled") 
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    driver_path = os.path.join(os.path.dirname(current_dir), "chromedriver.exe") 
    
    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def human_delay(min_sec=3.0, max_sec=6.0):
    """사람처럼 랜덤하게 멍 때리는 시간 부여"""
    time.sleep(random.uniform(min_sec, max_sec))

def smooth_scroll(driver):
    """사람처럼 부드럽게 스크롤 내리기"""
    try:
        total_height = int(driver.execute_script("return document.body.scrollHeight"))
        for i in range(1, total_height, random.randint(100, 300)):
            driver.execute_script(f"window.scrollTo(0, {i});")
            time.sleep(random.uniform(0.05, 0.15))
        # 다시 살짝 위로 올리기 (사람의 자연스러운 행동)
        driver.execute_script(f"window.scrollTo(0, {total_height - 300});")
        time.sleep(1)
    except:
        pass

def wait_for_manual_login(driver):
    """안전한 수동 로그인 무한 대기"""
    print("==========================================================")
    print("🚨 [1단계] 열린 브라우저에서 직접 카카오 계정으로 로그인해 주세요.")
    print("🚨 [2단계] 로그인이 완전히 끝나고 다음(Daum) 화면으로 넘어가면,")
    print("🚨 [3단계] 이 터미널 창으로 돌아와서 [Enter] 키를 누르세요.")
    print("==========================================================")
    
    # 유저가 제공한 확실한 카카오 로그인 URL로 바로 이동
    login_url = "https://accounts.kakao.com/login/?continue=https%3A%2F%2Fkauth.kakao.com%2Foauth%2Fauthorize%3Fclient_id%3D53e566aa17534bc816eb1b5d8f7415ee%26prompt%3Dselect_account%26state%3D3663e927-ade7-4367-920b-5da71f522551%26redirect_uri%3Dhttps%253A%252F%252Flogins.daum.net%252Faccounts%252Foauth%252Fkakao%252Fcallback%26response_type%3Dcode%26auth_tran_id%3DVmewe4eoS04tioj4sTsByIm3yFmuOZisZCzxwlryuzuCo0mRE~Suth8n78iz%26ka%3Dsdk%252F2.7.6%2520os%252Fjavascript%2520sdk_type%252Fjavascript%2520lang%252Fko-KR%2520device%252FWin32%2520origin%252Fhttps%25253A%25252F%25252Flogins.daum.net%2520app_key%252F53e566aa17534bc816eb1b5d8f7415ee%26is_popup%3Dfalse%26through_account%3Dtrue#login"
    driver.get(login_url)
    
    input("로그인 완료 후 화면이 넘어가면 Enter를 눌러주세요...")
    print("\n✅ 확인되었습니다. 사람의 속도로 천천히 수집을 시작합니다. 브라우저를 끄지 마세요.")

def get_yesterday_string():
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%y.%m.%d")

def crawl_cafe_board(driver, board_type, url):
    target_date = get_yesterday_string()
    print(f"\n[{board_type} 게시판] 진입 중... (타겟 날짜: {target_date})")
    
    # 물리적 클릭을 모사하여 URL 이동
    driver.get(url)
    human_delay(4.0, 7.0) # 페이지 완전 로딩 대기
    
    # iframe 진입 전 부드러운 스크롤로 사람인 척 하기
    smooth_scroll(driver)
    
    # iframe 명확히 찾아서 진입
    try:
        iframe = driver.find_element(By.ID, "down")
        driver.switch_to.frame(iframe)
    except Exception as e:
        print(f"iframe 진입 실패: {e}")
        return []
    
    collected_data = []
    page_num = 1
    stop_crawling = False
    
    while not stop_crawling:
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # DOM 파싱 범위 확대 (tbody가 없거나 tr 클래스가 다를 경우 대비)
        rows = soup.select('table.board-list tr')
        if not rows:
            print("  -> 🚨 [경고] 게시글 목록을 찾을 수 없습니다. (테이블 구조가 변경되었거나 봇 차단됨)")
            break
            
        print(f"  -> {page_num}페이지 파싱 중... (현재 프레임 내 게시글 {len(rows)}개 발견)")
        
        for row in rows:
            # 공지사항 필터링 강화
            if row.select_one('.icon_notice') or row.select_one('img[src*="notice"]'):
                continue
                
            date_td = row.select_one('td.td_date') or row.select_one('td.num')
            if not date_td:
                continue
            
            post_date = date_td.text.strip()
            
            # 디버깅용: 읽어들인 날짜 콘솔 출력 (너무 많으면 주석 처리 하세요)
            # print(f"읽은 날짜: {post_date}") 
            
            # 오늘 글 (시간 표기)
            if ":" in post_date:
                continue
                
            # 타겟보다 과거 글이면 스탑
            if post_date < target_date:
                print(f"  -> 과거 날짜({post_date}) 도달. 더 이상 탐색하지 않습니다.")
                stop_crawling = True
                break
                
            # 타겟 날짜 일치 시 데이터 수집
            if post_date == target_date:
                title_a = row.select_one('td.td_title a.link_txt') or row.select_one('a.link_txt')
                author_td = row.select_one('td.td_writer a') or row.select_one('td.writer a')
                
                if title_a:
                    post_title = title_a.text.strip()
                    post_link = "https://cafe.daum.net" + title_a['href']
                    post_author = author_td.text.strip() if author_td else "Unknown"
                    
                    collected_data.append({
                        "board_type": board_type,
                        "date": post_date,
                        "author": post_author,
                        "title": post_title,
                        "link": post_link
                    })
        
        if stop_crawling:
            break
            
        # 다음 페이지 이동 (ActionChains를 활용한 물리적 마우스 이동 후 클릭)
        page_num += 1
        try:
            next_page_btn = driver.find_element(By.XPATH, f"//div[@id='pagingArea']//a[text()='{page_num}']")
            # 물리적 스크롤 후 요소로 마우스 이동하여 클릭
            driver.execute_script("arguments[0].scrollIntoView(true);", next_page_btn)
            time.sleep(1)
            actions = ActionChains(driver)
            actions.move_to_element(next_page_btn).click().perform()
            print(f"  -> {page_num}페이지로 마우스 이동 및 클릭 완료.")
            human_delay(3.0, 6.0) # 클릭 후 화면 전환 대기
        except:
            print(f"  -> 다음 페이지({page_num}) 버튼을 찾을 수 없습니다. 탐색 종료.")
            break

    print(f"\n=> 수집된 {board_type} 게시글 링크 수: {len(collected_data)}개.")
    if len(collected_data) > 0:
        print("=> 본문 내용 추출을 위해 각 게시글로 천천히 진입합니다...")
    
    for idx, data in enumerate(collected_data):
        # 링크 이동
        driver.get(data['link'])
        human_delay(3.0, 5.0) # 사람처럼 읽는 시간 대기
        
        driver.switch_to.frame("down")
        try:
            content_div = driver.find_element(By.ID, "user_contents")
            data['content_raw'] = content_div.text.strip()
            print(f"    - ({idx+1}/{len(collected_data)}) '{data['title'][:15]}...' 본문 추출 성공")
        except:
            data['content_raw'] = "본문 추출 실패"
            print(f"    - ({idx+1}/{len(collected_data)}) 본문 추출 실패")
            
        driver.switch_to.default_content() # 프레임 초기화
        human_delay(1.0, 2.0)
        
    return collected_data

def main():
    driver = init_driver()
    try:
        wait_for_manual_login(driver)
        
        all_data = []
        for board_type, url in BOARDS.items():
            board_data = crawl_cafe_board(driver, board_type, url)
            all_data.extend(board_data)
            
        if all_data:
            df = pd.DataFrame(all_data)
            os.makedirs(DATA_RAW, exist_ok=True)
            df.to_csv(RAW_CAFE_CRAWLING_CSV, index=False, encoding='utf-8-sig')
            print(f"\n🎉 크롤링 완료! 총 {len(df)}건의 데이터가 저장되었습니다.")
            print(f"저장 경로: {RAW_CAFE_CRAWLING_CSV}")
        else:
            print("\n어제 날짜로 등록된 게시글이 없거나 수집에 실패했습니다.")
            
    except Exception as e:
        print(f"크롤링 중 에러 발생: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()