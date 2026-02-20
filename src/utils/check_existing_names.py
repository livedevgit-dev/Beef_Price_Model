import pandas as pd
import os

# [파일 정의서]
# - 파일명: src/utils/check_existing_names.py
# - 역할: Master 데이터 확인
# - 목적: 'master_price_data.csv'에 저장된 표준 품목명(Standard Names)을 추출
#         이 이름을 기준으로 USDA 영문명을 매핑할 예정입니다.

def check_master_file():
    # 1. 파일 경로 설정 (data/1_processed 폴더 가정)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    file_path = os.path.join(base_dir, 'data', '1_processed', 'master_price_data.csv')
    
    print(f"📂 파일 읽기 시도: {file_path}")
    
    if not os.path.exists(file_path):
        print("❌ 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        # 혹시 data/0_raw 에 있는지 한 번 더 체크
        file_path_raw = os.path.join(base_dir, 'data', '0_raw', 'master_price_data.csv')
        if os.path.exists(file_path_raw):
            file_path = file_path_raw
            print(f"🔄 경로 수정: {file_path} (Raw 폴더에서 발견)")
        else:
            return

    try:
        # 2. 데이터 로드
        df = pd.read_csv(file_path)
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