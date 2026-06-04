"""
[파일 정의서]
- 파일명: check_history_xlsx.py
- 역할: 유틸리티 (데이터 진단)
- 목적: history_batch 폴더 내 '엑셀(.xlsx)' 파일의 컬럼명 확인
"""
import pandas as pd
import os
import glob

def check_xlsx_structure():
    # 1. 과거 데이터 폴더 경로 (절대 경로)
    base_dir = r"D:\Beef_Price_Model\data\0_raw\history_batch"
    
    print(f">> [경로 확인] {base_dir}")

    # 2. .xlsx 파일 찾기 (여기가 수정되었습니다!)
    xlsx_files = glob.glob(os.path.join(base_dir, "*.xlsx"))
    
    if not xlsx_files:
        print("   [!] 여전히 파일이 안 보입니다. 폴더가 비어있는지 확인해주세요.")
        return

    # 3. 첫 번째 파일 읽기
    target_file = xlsx_files[0]
    file_name = os.path.basename(target_file)
    print(f">> [분석 대상] {file_name}")
    
    try:
        # 엑셀 읽기
        df = pd.read_excel(target_file)
            
        print("\n1. 컬럼 목록 (이 부분을 복사해주세요):")
        print(list(df.columns))
        
        print("\n2. 데이터 예시 (상위 2행):")
        print(df.head(2).to_string())
        
    except Exception as e:
        print(f"   [Error] 엑셀 읽기 실패: {e}")

if __name__ == "__main__":
    check_xlsx_structure()