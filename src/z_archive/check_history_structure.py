"""
[파일 정의서]
- 파일명: check_history_structure.py
- 역할: 유틸리티 (데이터 진단)
- 대상: 수입육 (과거 데이터)
- 데이터 소스: data/0_raw/history_batch 폴더 내 CSV 파일
- 주요 기능: 
    1. history_batch 폴더 내의 첫 번째 CSV 파일을 찾음
    2. 해당 파일의 컬럼명과 데이터 예시를 출력하여 병합 기준 수립 지원
"""

import pandas as pd
import os
import glob # 파일 리스트를 가져오는 모듈

def inspect_history_file():
    # 1. 과거 데이터가 있는 폴더 경로 (절대 경로 사용 권장)
    base_dir = r"D:\Beef_Price_Model\data\0_raw\history_batch"
    
    print(f">> [폴더 진단] 위치: {base_dir}")

    # 2. 폴더 내의 모든 csv 파일 찾기
    csv_files = glob.glob(os.path.join(base_dir, "*.csv"))
    
    if not csv_files:
        print("   [!] 폴더 내에 CSV 파일이 없습니다. 경로를 확인해주세요.")
        return

    # 3. 샘플로 첫 번째 파일만 읽기
    sample_file = csv_files[0]
    file_name = os.path.basename(sample_file)
    
    print(f">> [샘플 파일 발견] {file_name} 파일을 분석합니다.")
    
    try:
        # 한글 포함 가능성 고려하여 인코딩 처리
        try:
            df = pd.read_csv(sample_file, encoding='utf-8')
        except:
            df = pd.read_csv(sample_file, encoding='cp949')

        print("\n1. 데이터 크기 (행, 열):")
        print(f"   {df.shape}")
        
        print("\n2. 컬럼 목록 (변수명 확인 필수):")
        print(f"   {list(df.columns)}")
        
        print("\n3. 데이터 예시 (상위 3행):")
        print(df.head(3).to_string())
        
    except Exception as e:
        print(f"   [Error] 파일 읽기 실패: {e}")

if __name__ == "__main__":
    inspect_history_file()