import pandas as pd
import os

def create_monthly_master():
    # ---------------------------------------------------------
    # [경로 설정]
    # ---------------------------------------------------------
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    raw_dir = os.path.join(project_root, 'data', '0_raw')
    
    print("[시작] 월별 데이터 통합(Monthly Aggregation)을 시작합니다...")

    try:
        # ---------------------------------------------------------
        # 1. 데이터 로드
        # ---------------------------------------------------------
        # (1) 미트박스 시세
        meatbox_path = os.path.join(raw_dir, 'meatbox_sise_43084139.xlsx') 
        df_meatbox = pd.read_excel(meatbox_path)

        # (2) 환율 데이터
        exchange_path = os.path.join(raw_dir, 'exchange_rate_data.xlsx')
        df_exchange = pd.read_excel(exchange_path)

        # (3) 수입량 데이터
        import_path = os.path.join(raw_dir, 'beef_import_data_fast.xlsx')
        df_import = pd.read_excel(import_path)

        # (4) 재고 데이터
        stock_path = os.path.join(raw_dir, 'beef_stock_data.xlsx')
        df_stock = pd.read_excel(stock_path)

    except Exception as e:
        print(f"[에러] 파일 로드 실패: {e}")
        return

    # ---------------------------------------------------------
    # 2. 데이터 전처리 (월평균 변환 & 이름 통일) - 중요!
    # ---------------------------------------------------------
    
    # 공통 함수: 날짜 컬럼을 'date'로 통일하고 월평균 내기
    def preprocess_monthly(df, date_col_name, val_col_name, new_val_name):
        # 복사본 생성
        temp_df = df.copy()
        
        # 날짜 컬럼 이름을 강제로 'date'로 변경
        temp_df = temp_df.rename(columns={date_col_name: 'date'})
        
        # 날짜 형식 변환
        temp_df['date'] = pd.to_datetime(temp_df['date'])
        
        # 월평균 계산 (Resampling)
        temp_df = temp_df.set_index('date')
        # 월별 평균을 구하고 인덱스 리셋 (매월 1일로 설정)
        monthly_df = temp_df[[val_col_name]].resample('MS').mean().reset_index()
        
        # 값 컬럼 이름 변경
        monthly_df = monthly_df.rename(columns={val_col_name: new_val_name})
        return monthly_df

    # (1) 미트박스 처리
    # 가격 컬럼 찾기 (marketPrice 혹은 마지막 숫자 컬럼)
    price_col = 'marketPrice'
    if price_col not in df_meatbox.columns:
        # 없으면 숫자형 컬럼 중 마지막 것을 선택
        numeric_cols = df_meatbox.select_dtypes(include='number').columns
        price_col = numeric_cols[-1]
    
    # 변환 실행 (siseDate -> date, marketPrice -> avg_price)
    df_meatbox_m = preprocess_monthly(df_meatbox, 'siseDate', price_col, 'avg_price')


    # (2) 환율 처리
    # 첫번째 컬럼이 날짜, 두번째가 환율이라고 가정
    ex_date_col = df_exchange.columns[0]
    ex_val_col = df_exchange.columns[1]
    
    # 변환 실행 (원래날짜이름 -> date, 원래환율이름 -> avg_exchange)
    df_exchange_m = preprocess_monthly(df_exchange, ex_date_col, ex_val_col, 'avg_exchange')


    # (3) 수입량 처리 (이미 월별이지만 날짜 통일 필요)
    # 첫번째 컬럼(날짜), 두번째 컬럼(값)만 가져옴
    df_import_clean = df_import.iloc[:, [0, 1]].copy()
    df_import_clean.columns = ['date', 'import_vol'] # 강제 이름 변경
    df_import_clean['date'] = pd.to_datetime(df_import_clean['date']).dt.to_period('M').dt.to_timestamp()

    # (4) 재고량 처리
    df_stock_clean = df_stock.iloc[:, [0, 1]].copy()
    df_stock_clean.columns = ['date', 'stock_vol'] # 강제 이름 변경
    df_stock_clean['date'] = pd.to_datetime(df_stock_clean['date']).dt.to_period('M').dt.to_timestamp()

    # ---------------------------------------------------------
    # 3. 데이터 병합 (Merge) - 이제 모든 컬럼명이 'date'로 통일됨
    # ---------------------------------------------------------
    
    # 기준: 미트박스 데이터
    master_df = df_meatbox_m

    # 환율 붙이기 (on='date')
    master_df = pd.merge(master_df, df_exchange_m, on='date', how='left')
    
    # 수입량 붙이기
    master_df = pd.merge(master_df, df_import_clean, on='date', how='left')
    
    # 재고량 붙이기
    master_df = pd.merge(master_df, df_stock_clean, on='date', how='left')

    # ---------------------------------------------------------
    # 4. 마무리 및 저장
    # ---------------------------------------------------------
    
    # 결측치 채우기 (앞뒤 값으로)
    master_df = master_df.fillna(method='ffill').fillna(method='bfill')

    # 상관관계 출력
    print("\n[분석] [월별 상관관계 분석]")
    corr = master_df.corr(numeric_only=True)
    if 'avg_price' in corr.columns:
        print(corr['avg_price'].sort_values(ascending=False))

    # 엑셀 저장
    processed_dir = os.path.join(project_root, 'data', '1_processed')
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
        
    save_path = os.path.join(processed_dir, 'monthly_master_data.xlsx')
    master_df.to_excel(save_path, index=False)
    
    print(f"\n[완료] 월별 통합 완료! 저장 위치: {save_path}")
    print(master_df.head())

if __name__ == "__main__":
    create_monthly_master()