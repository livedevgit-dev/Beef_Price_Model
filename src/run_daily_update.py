import os
import subprocess
import sys

# [파일 정의서]
# - 파일명: run_daily_update.py
# - 역할: 분석 (전체 파이프라인 제어)
# - 대상: 수입육 (공통)
# - 주요 기능: 크롤링과 전처리를 순차적으로 실행하여 데이터 최신성 유지

def run_pipeline():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. 데이터 수집 실행 (crawl_imp_price_meatbox.py)
    print("="*60)
    print("[1/2] 데이터 수집(Crawl)을 시작합니다...")
    try:
        # 기존 수집 코드를 프로세스로 실행
        crawler_path = os.path.join(current_dir, "collectors", "crawl_imp_price_meatbox.py")
        subprocess.run([sys.executable, crawler_path], check=True)
        print("=> 수집 완료")
    except Exception as e:
        print(f"=> 수집 중 오류 발생: {e}")
        return

    # 2. 데이터 가공 실행 (preprocess_meat_data.py)
    print("\n[2/2] 데이터 가공(Preprocess) 및 지표 계산을 시작합니다...")
    try:
        # 전처리 코드를 프로세스로 실행
        preprocessor_path = os.path.join(current_dir, "utils", "preprocess_meat_data.py")
        subprocess.run([sys.executable, preprocessor_path], check=True)
        print("=> 가공 및 dashboard_ready_data.csv 갱신 완료")
    except Exception as e:
        print(f"=> 가공 중 오류 발생: {e}")
        return

    print("\n" + "="*60)
    print("✅ 모든 업데이트가 완료되었습니다. 이제 대시보드를 확인하세요!")
    print("="*60)

if __name__ == "__main__":
    run_pipeline()