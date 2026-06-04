"""
[파일 정의서]
- 파일명: check_latest_real.py
- 역할: 유틸리티 (데이터 진단)
- 목적: '진짜' 일별 데이터인 beef_price_raw_latest.xlsx의 구조 파악
"""
import pandas as pd
import os

def inspect_latest_file():
    # 프로젝트 루트 기준 절대 경로
    base_dir = r"D:\Beef_Price_Model\data\0_raw"
    file_name = "beef_price_raw_latest.xlsx"
    file_path = os.path.join(base_dir, file_name)
    
    print(f">> [진단 시작] 파일: {file_name}")

    if not os.path.exists(file_path):
        print(f"   [!] 파일을 찾을 수 없습니다: {file_path}")
        return

    try:
        df = pd.read_excel(file_path)
        
        print("\n1. 데이터 크기:")
        print(f"   {df.shape}")

        print("\n2. 컬럼 목록 (이것을 알려주세요):")
        print(list(df.columns))
        
        print("\n3. 데이터 예시 (상위 2행):")
        print(df.head(2).to_string())
        
    except Exception as e:
        print(f"   [Error] 파일 읽기 실패: {e}")

if __name__ == "__main__":
    inspect_latest_file()