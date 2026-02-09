import pandas as pd
import os
import re

# [파일 정의서]
# - 파일명: preprocess_meat_data.py
# - 역할: 가공 (Data Processing)
# - 대상: 공통
# - 데이터 소스: data/1_processed/master_price_data.csv
# - 수집/가공 주기: 일단위
# - 주요 기능: 
#   1. 부위/브랜드 텍스트 정제
#   2. 기술적 지표(이동평균) 산출
#   3. 3대 패커(IBP, Excel, Swift) 취급 부위 기준 필터링 (Option B)

def load_and_enrich_data():
    """
    master_price_data.csv를 로드하여 브랜드/부위를 분리하고
    이동평균(MA) 등 보조 지표를 추가합니다.
    """
    # 1. 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    input_path = os.path.join(project_root, "data", "1_processed", "master_price_data.csv")

    if not os.path.exists(input_path):
        print(f"[Error] File not found: {input_path}")
        return None

    # 2. 데이터 로드
    df = pd.read_csv(input_path, encoding='utf-8-sig')
    df['date'] = pd.to_datetime(df['date'])
    
    # 3. 부위명 및 브랜드 분리 로직
    # '갈비본살-미국 | IBP(245)' 형태 처리
    def split_part_brand(row):
        full_name = str(row['part_name'])
        if '|' in full_name:
            parts = full_name.split('|')
            # '갈비본살-미국' -> '갈비본살' (국가명 제거)
            part_clean = parts[0].split('-')[0].strip()
            brand_clean = parts[1].strip()
            return part_clean, brand_clean
        return row['part_name'], row['brand'] # 예외 처리

    # apply 적용
    df[['part', 'brand']] = df.apply(
        lambda x: pd.Series(split_part_brand(x)), axis=1
    )
    
    # category 컬럼 생성 (Origin)
    df['category'] = df['country']

    # 4. 품목별/날짜별 정렬
    df = df.sort_values(by=['country', 'part', 'brand', 'date'])

    # 5. 핵심 지표 계산 (이동평균)
    grouped = df.groupby(['country', 'part', 'brand'])

    # 7일, 30일 이동평균
    df['ma7'] = grouped['wholesale_price'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
    df['ma30'] = grouped['wholesale_price'].transform(lambda x: x.rolling(window=30, min_periods=1).mean())

    # 전체 기간 최고/최저 (참고용)
    df['min_total'] = grouped['wholesale_price'].transform('min')
    df['max_total'] = grouped['wholesale_price'].transform('max')

    print(f"Data Loaded & Enriched: {len(df)} rows")
    return df

def save_dashboard_ready_data(df):
    """
    3대 패커(IBP, Excel, Swift)가 취급하지 않는 마이너 부위를 제거하고
    대시보드 전용 데이터로 저장합니다.
    """
    if df is None:
        return

    print("Filtering logic started (Option B)...")

    # 1. 3대 패커 키워드 정의
    major_keywords = ['IBP', 'Excel', 'Swift', '엑셀', '스위프트']
    pattern = '|'.join(major_keywords) # Regex pattern

    # 2. 3대 패커가 취급하는 '유효 부위(Valid Parts)' 식별
    # 브랜드명에 키워드가 포함된 행 찾기
    is_major_packer = df['brand'].str.contains(pattern, case=False, na=False)
    
    # 해당 행들에 존재하는 부위(Part) 목록 추출
    valid_parts = df.loc[is_major_packer, 'part'].unique()
    
    print(f"- Major Packer Keywords: {major_keywords}")
    print(f"- Total parts in raw data: {df['part'].nunique()}")
    print(f"- Valid parts (traded by Majors): {len(valid_parts)}")

    # 3. 데이터 필터링 (유효 부위에 해당하는 모든 브랜드 데이터 유지)
    df_ready = df[df['part'].isin(valid_parts)].copy()

    print(f"- Filtering Result: {len(df)} rows -> {len(df_ready)} rows")

    # 4. 저장 (data/2_dashboard/dashboard_ready_data.csv)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    output_dir = os.path.join(project_root, "data", "2_dashboard")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_path = os.path.join(output_dir, "dashboard_ready_data.csv")
    
    # 필요한 컬럼만 깔끔하게 저장
    cols_to_save = [
        'date', 'category', 'part', 'brand', 
        'wholesale_price', 'ma7', 'ma30', 
        'min_total', 'max_total'
    ]
    # 만약 컬럼이 없으면 전체 저장 (안전장치)
    final_cols = [c for c in cols_to_save if c in df_ready.columns]
    
    df_ready[final_cols].to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"Successfully saved to: {output_path}")

# 메인 실행 블록
if __name__ == "__main__":
    # 1. 데이터 로드 및 기초 가공
    df_enriched = load_and_enrich_data()
    
    # 2. 필터링 및 최종 저장
    save_dashboard_ready_data(df_enriched)