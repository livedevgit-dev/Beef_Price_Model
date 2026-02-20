import pandas as pd
import os

# [파일 정의서]
# - 파일명: check_duplicates.py
# - 역할: 분석/검증
# - 대상: 공통
# - 주요 기능: master_price_data.csv 내의 중복 수집 데이터 확인

def check_duplicate_data():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    project_root = os.path.dirname(src_dir)
    
    file_path = os.path.join(project_root, "data", "1_processed", "master_price_data.csv")
    
    if not os.path.exists(file_path):
        print("파일을 찾을 수 없습니다.")
        return
        
    df = pd.read_csv(file_path, encoding='utf-8-sig')
    
    # 날짜, 국가, 부위, 브랜드가 완전히 동일한 행(중복된 모든 행)을 찾습니다.
    duplicates = df[df.duplicated(subset=['date', 'country', 'part_name', 'brand'], keep=False)]
    
    if duplicates.empty:
        print("중복된 데이터가 없습니다. 다른 원인의 에러일 수 있습니다.")
    else:
        print(f"총 {len(duplicates)}건의 중복 데이터가 발견되었습니다.")
        print("-" * 60)
        # 보기 쉽게 정렬해서 출력
        duplicates_sorted = duplicates.sort_values(by=['date', 'part_name', 'brand'])
        print(duplicates_sorted[['date', 'part_name', 'brand', 'wholesale_price']])
        print("-" * 60)

if __name__ == "__main__":
    check_duplicate_data()