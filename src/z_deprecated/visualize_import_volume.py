# [파일 정의서]
# - 파일명: visualize_import_volume.py
# - 역할: 시각화
# - 대상: 수입육
# - 데이터 소스: beef_import_raw_check.xlsx (또는 master_import_volume.csv)
# - 수집/가공 주기: 수시
# - 주요 기능: 가로형 수입량 데이터를 변환하여 부위별 추이 그래프(HTML) 생성

import pandas as pd
import plotly.express as px
import os

def visualize_import():
    # 1. 파일 경로 설정
    # 업로드하신 파일명을 기준으로 하며, 실제 환경에 맞춰 수정 가능합니다.
    file_path = 'beef_import_raw_check.xlsx' 
    
    # 엑셀 파일 로드 (첫 번째 시트)
    try:
        df = pd.read_excel(file_path)
    except:
        # 엑셀 읽기 실패 시 CSV 로드 시도
        df = pd.read_csv('beef_import_raw_check.xlsx - 수입량_원본확인.csv')

    # 2. 데이터 재구조화 (Wide to Long)
    # '부위별_XXX_합계' 형태의 컬럼들을 수집합니다.
    vol_cols = [c for c in df.columns if '부위별' in c and '계' not in c]
    id_vars = ['std_date', '구분']

    df_long = df.melt(id_vars=id_vars, value_vars=vol_cols, 
                      var_name='raw_part', value_name='volume')

    # 3. 데이터 정제
    # 컬럼명에서 '부위별_', '_합계' 문구를 제거하여 깔끔하게 만듭니다.
    df_long['part_name'] = df_long['raw_part'].str.extract(r'부위별_(.*)_합계')
    
    # 날짜 정렬을 위해 datetime 형식으로 임시 변환 후 정렬
    df_long['date_dt'] = pd.to_datetime(df_long['std_date'], format='%Y-%m')
    df_long = df_long.sort_values('date_dt')
    
    # 결측치(NaN)는 0으로 처리
    df_long['volume'] = df_long['volume'].fillna(0)

    # 4. 시각화 - 국가별 + 부위별 상세 추이
    df_long['category'] = df_long['구분'] + "_" + df_long['part_name']
    
    fig = px.line(df_long, 
                  x='std_date', 
                  y='volume', 
                  color='category',
                  title='국가별/부위별 수입량 추이',
                  labels={'volume': '수입량(톤)', 'std_date': '기준년월', 'category': '구분_부위'})

    # 5. 결과 저장 (HTML 파일)
    output_html = 'beef_import_trend.html'
    fig.write_html(output_html)
    
    print("="*60)
    print(f"[OK] 수입량 시각화 완료!")
    print(f"생성 파일: {output_html}")
    print("="*60)

if __name__ == "__main__":
    visualize_import()