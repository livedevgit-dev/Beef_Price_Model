import pandas as pd
import os
import warnings

# [파일 정의서]
# - 파일명: check_korean_schema.py
# - 역할: 분석 (EDA)
# - 주요 기능: 대시보드용으로 가공된 한국 미트박스 데이터의 스키마와 부위명(part) 고유값을 출력하여 매핑 기준을 확인.

warnings.filterwarnings("ignore")

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(src_dir)

KOR_FILE_PATH = os.path.join(project_root, "data", "2_dashboard", "dashboard_ready_data.csv")

def check_korean_data():
    if not os.path.exists(KOR_FILE_PATH):
        print(f"[에러] 한국 데이터 파일을 찾을 수 없습니다: {KOR_FILE_PATH}")
        return

    print("=" * 60)
    print("[진단 시작] 한국 미트박스 대시보드 데이터 구조 분석")
    print("=" * 60)

    # 데이터 불러오기
    df = pd.read_csv(KOR_FILE_PATH)

    print(f"\n1. 총 컬럼 개수: {len(df.columns)}개")
    print("\n2. 전체 컬럼 목록 및 샘플 데이터:")
    
    # 각 컬럼의 첫 번째 값을 샘플로 보여줌
    for col in df.columns:
        sample_value = df[col].iloc[0] if not pd.isna(df[col].iloc[0]) else "결측치(NaN)"
        print(f" - [{col}] | 타입: {df[col].dtype} | 샘플: {sample_value}")

    print("\n3. '부위(part/part_clean)' 관련 컬럼 고유값 확인:")
    # 이전 개발일지를 참고하여 'part_clean' 또는 'part' 컬럼을 찾음
    part_col = 'part_clean' if 'part_clean' in df.columns else ('part' if 'part' in df.columns else None)
    
    if part_col:
        unique_parts = df[part_col].dropna().unique().tolist()
        print(f" - 발견된 부위 컬럼 '{part_col}'의 고유 부위명 목록:")
        print(f"   {unique_parts}")
        
        # '삼겹양지'나 '우삼겹'이 포함되어 있는지 특별 확인
        belly_keywords = [p for p in unique_parts if '삼겹' in p or '양지' in p or '우삼' in p]
        print(f"\n [!] 삼겹양지 관련 한국 표기명 검색 결과: {belly_keywords}")
    else:
        print(" - [경고] 부위를 나타내는 'part' 또는 'part_clean' 컬럼을 찾을 수 없습니다.")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_korean_data()