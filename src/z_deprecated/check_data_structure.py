"""
[파일 정의서]
- 파일명: check_data_structure.py
- 역할: 유틸리티 (데이터 진단용)
- 대상: 공통
- 데이터 소스: 로컬 파일 (엑셀/CSV)
- 주요 기능: 경로 에러 방지를 위해 '절대 경로'를 사용하여 데이터 구조 진단
"""

import pandas as pd
import os

def inspect_multiple_files():
    # =========================================================================
    # [수정된 부분] 상대 경로(./) 대신 절대 경로(D:/...)를 사용하여 에러를 원천 차단합니다.
    # 문자열 앞에 'r'을 붙이면 윈도우 경로의 역슬래시(\)를 안전하게 인식합니다.
    # =========================================================================
    base_dir = r"D:\Beef_Price_Model\data\0_raw"
    
    # 확인하고 싶은 파일 명단
    target_files = [
        "beef_price_raw_FULL.xlsx",        
        "beef_import_data_fast.xlsx",      
        "beef_stock_data.xlsx",             
        "exchange_rate_data.xlsx",          
        "미국산소고기_2019_2024_Total.csv"   
    ]

    print("==========================================")
    print("      [데이터 파일 구조 일괄 진단]      ")
    print("==========================================\n")

    for file_name in target_files:
        # 경로 결합 (D:\... + filename)
        file_path = os.path.join(base_dir, file_name)
        print(f">> 분석 대상: {file_name}")

        if not os.path.exists(file_path):
            print(f"   [!] 파일을 찾을 수 없습니다. 경로 확인 필요: {file_path}")
            print("-" * 50)
            continue

        try:
            # 확장자에 따라 읽기 방식 분기
            if file_name.endswith('.xlsx'):
                df = pd.read_excel(file_path)
            elif file_name.endswith('.csv'):
                try:
                    df = pd.read_csv(file_path, encoding='cp949')
                except:
                    df = pd.read_csv(file_path, encoding='utf-8')
            
            # 정보 출력
            print(f"   1. 크기: {df.shape} (행, 열)")
            print(f"   2. 컬럼 목록: {list(df.columns)}")
            print("   3. 데이터 예시 (상위 2행):")
            print(df.head(2).to_string())
            
        except Exception as e:
            print(f"   [Error] 파일 읽기 실패: {e}")
        
        print("\n" + "-" * 50 + "\n")

if __name__ == "__main__":
    inspect_multiple_files()