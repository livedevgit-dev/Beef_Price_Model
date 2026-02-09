import pandas as pd
import os
import glob

# [파일 정의서]
# - 파일명: src/anal_price_drop_rank.py
# - 역할: 분석
# - 대상: 공통
# - 데이터 소스: data/0_raw/history_batch/ 폴더 내의 개별 엑셀 파일들
# - 주요 기능: 'marketPrice' 기준 [현재가/최고가/최저가] 3단 비교 및 하락률 랭킹 산출

# ==========================================
# 1. 환경 설정
# ==========================================
BASE_DIR = "D:/Beef_Price_Model"
INPUT_DIR = os.path.join(BASE_DIR, "data/0_raw/history_batch/")
OUTPUT_DIR = os.path.join(BASE_DIR, "data/2_analyzed/")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"[알림] 분석 결과 폴더 생성: {OUTPUT_DIR}")

# ==========================================
# 2. 데이터 로드 및 분석 루프
# ==========================================
all_files = glob.glob(os.path.join(INPUT_DIR, "*.xlsx"))
total_files = len(all_files)

print(f"[시작] 총 {total_files}개의 시세 파일 분석을 시작합니다. (기준: marketPrice)")

result_list = []

for idx, file_path in enumerate(all_files):
    try:
        df = pd.read_excel(file_path)
        
        if len(df) == 0:
            continue
            
        if 'marketPrice' not in df.columns:
            continue

        # -------------------------------------------------------
        # [핵심 로직] 3단 가격 비교 (Current / Max / Min)
        # -------------------------------------------------------
        
        # 1. 날짜 기준 내림차순 정렬 (최신이 위로)
        df = df.sort_values(by='기준일자', ascending=False)
        
        # 2. 가격 지표 산출
        # (1) 현재가: 가장 최신 날짜의 시세
        current_price = df.iloc[0]['marketPrice']
        current_date = df.iloc[0]['기준일자']
        
        # (2) 최고가: 전체 기간 중 가장 비쌌던 가격
        max_price = df['marketPrice'].max()
        
        # (3) [추가] 최저가: 전체 기간 중 가장 쌌던 가격
        min_price = df['marketPrice'].min()
        
        # 3. 품목 정보
        item_name = df.iloc[0].get('품목명', 'Unknown')
        origin = df.iloc[0].get('원산지', '-')
        brand = df.iloc[0].get('브랜드', '-')
        sise_seq = df.iloc[0].get('siseSeq', '-')

        # 4. 하락률 계산 (최고가 대비 현재가 괴리율)
        if max_price > 0:
            drop_amount = max_price - current_price
            drop_rate = (drop_amount / max_price) * 100
        else:
            drop_amount = 0
            drop_rate = 0.0

        # 결과 리스트 추가
        result_list.append({
            '품목명': item_name,
            '원산지': origin,
            '브랜드': brand,
            '현재가': current_price,
            '최고가': max_price,
            '최저가': min_price,   # 추가된 항목
            '하락률(%)': round(drop_rate, 2),
            '기준일자': current_date,
            'siseSeq': sise_seq
        })

    except Exception as e:
        print(f"[에러] 파일 처리 중 오류: {os.path.basename(file_path)} / {e}")

# ==========================================
# 3. 결과 집계 및 저장
# ==========================================
if len(result_list) > 0:
    df_result = pd.DataFrame(result_list)
    
    # [정렬] 하락률 높은 순
    df_result = df_result.sort_values(by='하락률(%)', ascending=False)
    
    # 랭킹 부여
    df_result.reset_index(drop=True, inplace=True)
    df_result.index = df_result.index + 1
    df_result.index.name = '순위'
    
    # [컬럼 순서 정리] 보기 좋게 가격 관련 컬럼을 앞으로 배치
    cols = ['품목명', '원산지', '브랜드', '현재가', '최고가', '최저가', '하락률(%)', '기준일자', 'siseSeq']
    # 혹시 컬럼명이 다를 경우를 대비한 방어 코드
    final_cols = [c for c in cols if c in df_result.columns]
    df_result = df_result[final_cols]
    
    # 저장
    save_path = os.path.join(OUTPUT_DIR, "price_drop_ranking.xlsx")
    df_result.to_excel(save_path)
    
    print("-" * 60)
    print(f"[완료] 분석 결과 저장됨: {save_path}")
    print("-" * 60)
    
    # 미리보기 출력 (최저가 포함)
    print("[Top 10 하락 품목 미리보기]")
    print(df_result[['품목명', '현재가', '최고가', '최저가', '하락률(%)']].head(10))
    print("-" * 60)

else:
    print("[경고] 분석 가능한 데이터가 없습니다.")