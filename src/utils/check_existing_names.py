import pandas as pd
import os
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MASTER_PRICE_CSV, DATA_RAW

# [파일 정의서]
# - 파일명: src/utils/check_existing_names.py
# - 역할: Master 데이터 확인
# - 목적: 'master_price_data.csv'에 저장된 표준 품목명(Standard Names)을 추출
#         이 이름을 기준으로 USDA 영문명을 매핑할 예정입니다.

def check_master_file():
    # 1. 파일 경로 설정 (1_processed 우선, 없으면 0_raw)
    file_path = MASTER_PRICE_CSV
    if not file_path.exists():
        file_path = DATA_RAW / 'master_price_data.csv'
        if not file_path.exists():
            print("❌ 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
            return
        print(f"🔄 경로 수정: {file_path} (Raw 폴더에서 발견)")
    
    print(f"📂 파일 읽기 시도: {file_path}")

    try:
        # 2. 데이터 로드
        df = pd.read_csv(str(file_path))
        print("✅ 파일 로드 성공!")
        print("-" * 50)
        
        # 3. 컬럼 목록 출력 (어떤 컬럼이 '품목명'인지 확인용)
        print(f"📋 전체 컬럼 목록: {list(df.columns)}")
        print("-" * 50)
        
        # 4. 품목명으로 추정되는 컬럼의 내용 출력
        # 보통 '품목', 'item', 'name', 'part' 등이 들어갑니다.
        target_cols = [c for c in df.columns if any(k in c.lower() for k in ['품목', 'name', 'item', 'product', 'part'])]
        
        if target_cols:
            for col in target_cols:
                unique_vals = df[col].dropna().unique()
                print(f"📌 [{col}] 컬럼의 고유 값 ({len(unique_vals)}개):")
                # 보기 좋게 정렬해서 출력
                for val in sorted(unique_vals.astype(str)):
                    print(f"   • {val}")
                print("-" * 50)
        else:
            print("⚠️ 품목명 관련 컬럼을 자동으로 찾지 못했습니다. 위 컬럼 목록을 보고 알려주세요.")
            print(df.head(3))

    except Exception as e:
        print(f"⛔ 에러 발생: {e}")

if __name__ == "__main__":
    check_master_file()