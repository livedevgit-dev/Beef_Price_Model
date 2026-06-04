import pandas as pd
import os
import warnings

# [파일 정의서]
# - 파일명: check_all_items.py
# - 역할: 분석
# - 대상: 수입육
# - 데이터 소스: 미국 USDA 가공 데이터 (processed_usda_cost.csv)
# - 수집/가공 주기: 일회성 (QA용)
# - 주요 기능: USDA 도매가 데이터에 존재하는 모든 고유 품목(item_description) 리스트를 전체 추출하여 삼겹양지(우삼겹) 매핑 대상을 기획자가 직접 탐색할 수 있도록 제공함.

# ======================================================
# [설정] 기본 환경 설정 및 경로 지정
# ======================================================
warnings.filterwarnings("ignore")

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)

US_DATA_PATH = os.path.join(project_root, "data", "1_processed", "processed_usda_cost.csv")

# ======================================================
# [핵심 로직] 전체 품목 리스트 추출
# ======================================================
def check_all_items():
    if not os.path.exists(US_DATA_PATH):
        print("[에러] 가공된 미국 데이터가 없습니다. 경로를 확인해주세요.")
        return

    print("=" * 60)
    print("[진단] USDA 데이터 내 전체 품목(Item) 리스트")
    print("=" * 60)

    df_us = pd.read_csv(US_DATA_PATH)
    
    # 1. 결측치 제거
    df_us_valid = df_us.dropna(subset=['item_description'])
    
    # 2. 모든 고유 품목 추출 후 알파벳 순 정렬
    unique_items = sorted(df_us_valid['item_description'].unique().tolist())

    if not unique_items:
        print("[결과] 품목 데이터가 비어 있습니다.")
        return

    # 3. 결과 출력
    for i, item in enumerate(unique_items, 1):
        print(f"{i:3d}. {item}")
        
    print("=" * 60)
    print(f"총 {len(unique_items)}개의 품목이 존재합니다.")
    print("이 중에서 '삼겹양지(Beef Belly, Navel, Short Plate 등)'에 해당하는 항목을 찾아주세요.")
    print("=" * 60)

if __name__ == "__main__":
    check_all_items()