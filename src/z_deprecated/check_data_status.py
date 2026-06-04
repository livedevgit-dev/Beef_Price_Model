import pandas as pd
import os

# [파일 정의서]
# - 파일명: check_data_status.py (in z_archive)
# - 역할: 분석 (임시 데이터 정합성 확인)
# - 대상: 수입육 (master_price_data.csv)
# - 주요 기능: 경로 자동 추적 및 데이터 상태 진단

def analyze_master_data():
    # 1. 경로 설정 (z_archive -> src -> project_root 로 이동)
    current_file_path = os.path.abspath(__file__)
    z_archive_dir = os.path.dirname(current_file_path)
    src_dir = os.path.dirname(z_archive_dir)
    project_root = os.path.dirname(src_dir) # src의 상위인 프로젝트 루트로 이동
    
    # 2. 데이터 파일 경로 조립
    file_path = os.path.join(project_root, "data", "1_processed", "master_price_data.csv")

    print(f"[경로 확인] 탐색 중인 파일: {file_path}")

    if not os.path.exists(file_path):
        print(f"[에러] 파일을 찾을 수 없습니다. 경로를 다시 확인해주세요.")
        return

    # 데이터 로드
    df = pd.read_csv(file_path)
    
    print("-" * 50)
    print("1. 데이터 기본 정보")
    print(df.info())
    
    print("\n2. 품목/원산지별 데이터 개수 (상위 10개)")
    print(df.groupby(['country', 'part_name']).size().sort_values(ascending=False).head(10))

    print("\n3. 브랜드 분포 (다양성 확인)")
    # brand 컬럼이 있는지 확인 후 출력
    if 'brand' in df.columns:
        print(df['brand'].value_counts().head(10))
    
    print("-" * 50)

if __name__ == "__main__":
    analyze_master_data()