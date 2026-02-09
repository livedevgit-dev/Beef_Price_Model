"""
[파일 정의서]
- 파일명: proc_clean_price.py
- 역할: 가공 (Preprocessing)
- 대상: 공통 (시세 데이터)
- 데이터 소스: beef_price_raw_FULL.xlsx
- 주요 기능: 
    1. 경로 에러 방지를 위해 '절대 경로' 사용
    2. 17,580 원 -> 17580 변환
    3. 품목/국가/브랜드 분리 및 저장
"""

import pandas as pd
import os
import re

def clean_price_data():
    # =========================================================
    # [수정] 프로젝트의 루트 경로를 명시적으로 지정합니다.
    # 이제 코드가 어디서 실행되든 데이터는 무조건 이 경로로 갑니다.
    # =========================================================
    PROJECT_ROOT = r"D:\Beef_Price_Model"
    
    # 읽어올 파일 경로
    input_file_path = os.path.join(PROJECT_ROOT, "data", "0_raw", "beef_price_raw_FULL.xlsx")
    
    # 저장할 폴더 경로 (data/1_processed)
    save_dir = os.path.join(PROJECT_ROOT, "data", "1_processed")

    print(f">> [전처리 시작] 파일 읽기: {input_file_path}")

    # 1. 파일 읽기
    if not os.path.exists(input_file_path):
        print(f"Error: 파일을 찾을 수 없습니다. 경로를 확인해주세요: {input_file_path}")
        return
    
    df = pd.read_excel(input_file_path)

    # 2. 데이터 전처리 로직 (이전과 동일)
    def parse_price(x):
        if str(x).strip() == '-': return None
        clean_str = re.sub(r'[^0-9]', '', str(x))
        if not clean_str: return None
        return int(clean_str)

    df['wholesale_price'] = df['도매시세 (kg당 가격)'].apply(parse_price)

    def parse_item_info(row):
        text = str(row.get('품목 △', '')) 
        part = "Unknown"
        country = "Unknown"
        brand = row.get('미트박스 상품', '-')

        if '|' in text:
            left, right = text.split('|', 1)
            brand = right.strip()
            if '-' in left:
                part_segment = left.split('-')
                part = part_segment[0].strip()
                if len(part_segment) > 1:
                    country = part_segment[1].strip()
            else:
                part = left.strip()
        else:
            if '-' in text:
                part_segment = text.split('-')
                part = part_segment[0].strip()
                if len(part_segment) > 1:
                    country = part_segment[1].strip()
            else:
                part = text.strip()

        return pd.Series([part, country, brand])

    df[['part_name', 'country', 'brand']] = df.apply(parse_item_info, axis=1)
    df['date'] = pd.to_datetime(df['기준일자_수집'])

    clean_df = df[['date', 'part_name', 'country', 'brand', 'wholesale_price']]
    clean_df = clean_df.dropna(subset=['wholesale_price'])

    # 3. 저장 (올바른 경로에 저장)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    save_path = os.path.join(save_dir, "clean_price_data.csv")
    clean_df.to_csv(save_path, index=False, encoding='utf-8-sig')

    print(f">> [전처리 완료] 정상 저장 위치: {save_path}")
    print(f"   - 유효 데이터 수: {len(clean_df)}행")

if __name__ == "__main__":
    clean_price_data()