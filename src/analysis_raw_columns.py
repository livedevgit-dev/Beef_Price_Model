import pandas as pd
import os

# [파일 정의서]
# - 파일명: analysis_raw_columns.py
# - 역할: 데이터 분석 (매핑 테이블 생성을 위한 기초 조사)
# - 대상: Master Data(시세) vs Raw Data(수입/재고)

# 1. 파일 경로 설정
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # 프로젝트 루트
raw_dir = os.path.join(base_dir, "data", "0_raw")
processed_dir = os.path.join(base_dir, "data", "1_processed")

# 분석할 파일명 (실제 파일명이 다르면 여기서 수정해주세요)
file_import = "import_volume.xlsx"     # 수입량 파일
file_stock = "stock_volume.xlsx"       # 재고량 파일
file_price = "master_price_data.csv"   # 방금 완성한 시세 파일

def inspect_file(folder, filename, label):
    filepath = os.path.join(folder, filename)
    print("-" * 50)
    print(f"[분석 대상] {label}: {filename}")
    
    if not os.path.exists(filepath):
        print(f" -> [주의] 파일을 찾을 수 없습니다. 경로: {filepath}")
        return

    try:
        # 파일 읽기
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        print(f"1. 데이터 크기: {df.shape}")
        print(f"2. 컬럼 목록: {list(df.columns)}")
        
        # 품목명으로 추정되는 컬럼 찾기 (자동 감지 시도)
        candidate_cols = [c for c in df.columns if any(k in str(c) for k in ['품목', 'ITEM', 'part_name', '부위'])]
        
        if candidate_cols:
            target_col = candidate_cols[0] # 첫 번째 후보 선택
            unique_items = df[target_col].unique()
            print(f"3. 품목 컬럼(추정): '{target_col}'")
            print(f"4. 품목 리스트 (앞부분 10개만):")
            print(unique_items[:10])
            print(f"   -> 총 품목 수: {len(unique_items)}개")
        else:
            print("3. 품목 관련 컬럼을 자동으로 찾지 못했습니다. 컬럼 목록을 확인해주세요.")
            
        print("\n[상위 3행 미리보기]")
        print(df.head(3))
        
    except Exception as e:
        print(f" -> 파일 읽기 실패: {e}")

# 실행
print("=" * 60)
print("데이터 컬럼 및 품목명 분석 시작")
print("=" * 60)

inspect_file(raw_dir, file_import, "수입량 데이터(X1)")
inspect_file(raw_dir, file_stock, "재고량 데이터(X2)")
inspect_file(processed_dir, file_price, "시세 데이터(Y - Master)")