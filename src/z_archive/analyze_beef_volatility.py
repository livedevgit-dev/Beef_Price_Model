# [파일 정의서]
# - 파일명: visualize_stock_and_clean_data.py
# - 역할: 분석 및 시각화
# - 대상: 수입육 (재고/수입)
# - 데이터 소스: beef_stock_data.xlsx, master_import_volume.csv
# - 주요 기능: 부위별 재고 추이 시각화 및 수입량 데이터 안전 추출

import pandas as pd
import os
import plotly.express as px

def process_and_visualize():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    path_stock = os.path.join(project_root, "data", "0_raw", "beef_stock_data.xlsx")
    path_volume = os.path.join(project_root, "data", "0_raw", "master_import_volume.csv")
    output_dir = os.path.join(project_root, "data", "2_analyzed")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 재고 데이터 시각화
    try:
        df_stock = pd.read_excel(path_stock)
        # '합계' 데이터 제외하고 부위별로만 보기
        df_stock_filtered = df_stock[~df_stock['부위별 부위별'].str.contains('합계', na=False)]
        
        # 선 그래프 생성
        fig = px.line(df_stock_filtered, 
                      x='기준년월', 
                      y='조사재고량 조사재고량', 
                      color='부위별 부위별',
                      title='부위별 수입 소고기 재고 추이',
                      labels={'조사재고량 조사재고량': '재고량(톤)', '기준년월': '날짜'})
        
        # 시각화 파일 저장 (웹브라우저로 열림)
        viz_path = os.path.join(output_dir, "beef_stock_trend.html")
        fig.write_html(viz_path)
        print(f"✅ 재고 시각화 완료: {viz_path}")
    except Exception as e:
        print(f"[오류] 재고 분석 실패: {e}")

    # 2. 수입량 데이터 안전 추출 (가장 단순한 방식으로)
    try:
        df_vol = pd.read_csv(path_volume)
        # 컬럼명에 있는 보이지 않는 공백 제거
        df_vol.columns = df_vol.columns.str.strip()
        
        vol_report_path = os.path.join(output_dir, "beef_import_raw_check.xlsx")
        
        # 가로형 그대로 일단 저장하여 데이터가 있는지 확인
        with pd.ExcelWriter(vol_report_path, engine='openpyxl') as writer:
            df_vol.to_excel(writer, sheet_name='수입량_원본확인', index=False)
        
        print(f"✅ 수입량 원본 확인용 파일 생성: {vol_report_path}")
    except Exception as e:
        print(f"[오류] 수입량 추출 실패: {e}")

if __name__ == "__main__":
    process_and_visualize()