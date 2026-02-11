"""
[파일 정의서]
- 파일명: main_runner.py
- 역할: 전체 프로세스 제어 (Controller)
- 주요 기능: 매일 오전 11:30에 실행되어 날짜에 맞는 수집/가공 스크립트 호출
"""

import datetime
import subprocess  # 다른 파이썬 파일을 실행하기 위한 도구
import os

def get_first_business_monday(year, month):
    # 해당 월의 1일 찾기
    first_day = datetime.date(year, month, 1)
    # 첫 번째 월요일 찾기 (기획자님의 로직 준수)
    days_to_monday = (0 - first_day.weekday() + 7) % 7
    first_monday = first_day + datetime.timedelta(days=days_to_monday)
    return first_monday

def run_script(script_name):
    """지정한 파이썬 파일을 실행하는 함수 (인코딩 에러 방지 버전)"""
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    print(f"--- {script_name} 실행 시도 ---")
    
    # env 환경 변수를 추가하여 파이썬의 출력 인코딩을 UTF-8로 강제합니다.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # errors='ignore'를 추가하여 이모지 등으로 인한 에러를 무시합니다.
    result = subprocess.run(
        ['python', script_path], 
        capture_output=True, 
        text=True, 
        encoding='utf-8', # 인코딩 명시
        errors='ignore',   # 인코딩할 수 없는 문자는 무시
        env=env
    )
    
    if result.returncode == 0:
        print(f"[완료] {script_name} 완료")
        # 실제 프로그램의 출력 내용을 보고 싶다면 아래 주석을 해제하세요
        # print(result.stdout) 
    else:
        print(f"[실패] {script_name} 실패")
        print(f"에러 내용: {result.stderr}")

if __name__ == "__main__":
    today = datetime.date.today()
    # 1. 매일 실행되는 '일 단위' 수집기 목록 (image_5cbe69.png 기준)
    daily_scripts = [
        "crawl_imp_price_meatbox.py",
        "crawl_com_usd_krw.py",
        "crawl_han_auction_api.py"
    ]
    
    # 2. 1주차 월요일에만 실행되는 '월 단위' 수집기 목록
    monthly_scripts = [
        "crawl_imp_volume_monthly.py",
        "crawl_imp_stock_monthly.py",
        "proc_merge_master_data.py"  # 마스터 데이터 업데이트도 이때 수행
    ]

    print(f"[정보] 오늘 날짜: {today}")

    # 일 단위 스크립트 무조건 실행
    for script in daily_scripts:
        run_script(script)

    # 오늘이 1주차 월요일인지 체크하여 월 단위 스크립트 실행
    target_monday = get_first_business_monday(today.year, today.month)
    if today == target_monday:
        print("[정보] 오늘은 월간 데이터 수집일입니다.")
        for script in monthly_scripts:
            run_script(script)
    else:
        print(f"[정보] 다음 월간 수집 예정일: {target_monday}")