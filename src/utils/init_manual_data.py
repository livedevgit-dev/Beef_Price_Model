import pandas as pd
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MANUAL_KOR_PRICE_CSV, ensure_dirs

# [파일 정의서]
# - 파일명: init_manual_data.py
# - 역할: 가공 (초기화)
# - 대상: 한우/수입육 공통 (수기 관리 데이터)
# - 주요 기능: 기획자가 엑셀로 직접 관리할 수 있는 수기 가격 데이터(manual_kor_price.csv)의 초기 템플릿 및 과거 데이터를 생성함.

OUTPUT_FILE = MANUAL_KOR_PRICE_CSV

def create_manual_data():
    # 기획자님이 제공해주신 과거 삼겹양지 수기 데이터 (기준일: 매월 15일)
    manual_data = [
        {"date": "2024-03-15", "part": "삼겹양지", "wholesale_price": 9100},
        {"date": "2024-05-15", "part": "삼겹양지", "wholesale_price": 9920},
        {"date": "2024-06-15", "part": "삼겹양지", "wholesale_price": 9900},
        {"date": "2024-07-15", "part": "삼겹양지", "wholesale_price": 10000},
        {"date": "2024-08-15", "part": "삼겹양지", "wholesale_price": 9700},
        {"date": "2024-10-15", "part": "삼겹양지", "wholesale_price": 10200},
        {"date": "2024-11-15", "part": "삼겹양지", "wholesale_price": 9800}
    ]
    
    df_manual = pd.DataFrame(manual_data)
    
    ensure_dirs()
    df_manual.to_csv(str(OUTPUT_FILE), index=False, encoding='utf-8-sig')
    print(f"[완료] 수기 데이터 파일이 생성되었습니다. (저장 위치: {OUTPUT_FILE})")
    print(" - 향후 과거 데이터가 발굴되면 이 CSV 파일을 직접 열어서 행을 추가하시면 됩니다.")

if __name__ == "__main__":
    create_manual_data()