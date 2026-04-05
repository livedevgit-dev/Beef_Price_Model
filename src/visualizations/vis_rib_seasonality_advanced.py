# [파일 정의서]
# - 파일명: vis_rib_seasonality_advanced.py
# - 역할: 분석 및 시각화
# - 대상: 수입육
# - 데이터 소스: 수동 입력 한국 가격 데이터 (MANUAL_KOR_PRICE_CSV)
# - 주요 기능: 1년 단위 연도별 최고/최저가 추이 분석 및 EMA(지수이동평균)를 적용한 최근 트렌드 기반 최적 매수/매도 시점 산출 (Y축 및 색상 시각성 개선)

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 프로젝트 config 경로 변수 임포트
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MANUAL_KOR_PRICE_CSV, DATA_PROCESSED

# 한글 폰트 및 마이너스 깨짐 방지 설정
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False

def main():
    # 1. 데이터 로드 및 전처리
    df = pd.read_csv(MANUAL_KOR_PRICE_CSV)
    df['날짜'] = pd.to_datetime(df['날짜'], format='%b-%y')
    df['Year'] = df['날짜'].dt.year
    df['Month'] = df['날짜'].dt.month
    
    target_col = '갈비_냉동_미국산'
    
    # ==========================================================
    # 로직 1: 1년 단위 최고가, 최저가 시점 추적
    # ==========================================================
    yearly_minmax = []
    years = sorted(df['Year'].unique())
    
    for year in years:
        year_data = df[df['Year'] == year].copy()
        year_data = year_data.dropna(subset=[target_col])
        if year_data.empty:
            continue
            
        min_idx = year_data[target_col].idxmin()
        max_idx = year_data[target_col].idxmax()
        
        yearly_minmax.append({
            '연도': year,
            '최저가_월(비수기)': int(year_data.loc[min_idx, 'Month']),
            '최저가_금액': year_data.loc[min_idx, target_col],
            '최고가_월(성수기)': int(year_data.loc[max_idx, 'Month']),
            '최고가_금액': year_data.loc[max_idx, target_col],
            '최대_스프레드': year_data.loc[max_idx, target_col] - year_data.loc[min_idx, target_col]
        })
        
    df_yearly_summary = pd.DataFrame(yearly_minmax)
    
    print("\n==================================================")
    print("[로직 1] 연도별 갈비(냉동) 최고/최저가 시점 추적")
    print("==================================================")
    print(df_yearly_summary.to_string(index=False))
    print("--------------------------------------------------")
    print("* 인사이트: 매년 성수기(최고가)와 비수기(최저가) 달이 어떻게 이동하는지 확인합니다.")
    print("==================================================\n")

    # ==========================================================
    # 로직 2: EMA (지수이동평균) 기반 최근 트렌드 가중치 적용
    # ==========================================================
    pivot_df = df.pivot(index='Month', columns='Year', values=target_col)
    pivot_df = pivot_df.ffill(axis=1)
    
    # EMA 계산 (최근 트렌드 가중치)
    ema_seasonality = pivot_df.ewm(span=4, axis=1).mean().iloc[:, -1]
    ema_seasonality.name = 'EMA_Weighted_Price'
    
    # 단순 8년 평균 계산
    simple_seasonality = pivot_df.mean(axis=1)
    
    # ==========================================================
    # 로직 3: 시각화 (Y축 3,000 이상, 색상 개별 부여)
    # ==========================================================
    plt.figure(figsize=(12, 7))
    
    # 구분이 명확한 컬러 팔레트 사용
    cmap = plt.get_cmap('tab10')
    
    # 개별 연도 선 그리기 (모든 연도에 고유 색상 부여)
    for i, year in enumerate(years):
        plt.plot(pivot_df.index, pivot_df[year], marker='o', linewidth=1.5, 
                 color=cmap(i % 10), alpha=0.6, label=f'{year}년')
            
    # 단순 평균선과 EMA 평균선을 가장 돋보이게 굵고 강렬한 색상으로 배치
    plt.plot(simple_seasonality.index, simple_seasonality.values, 
             linestyle='--', color='black', linewidth=3, label='단순 8년 평균 (과거포함)')
             
    plt.plot(ema_seasonality.index, ema_seasonality.values, 
             marker='s', markersize=8, color='red', linewidth=4, label='EMA 최근 트렌드 (핵심)')

    # 차트 꾸미기 및 Y축 제한 설정
    plt.title('미국산 냉동 갈비 월별 계절성 분석 (최근 변동성 강조)', fontsize=16, fontweight='bold')
    plt.xlabel('월 (Month)', fontsize=12)
    plt.ylabel('가격 (100g 당 원)', fontsize=12)
    plt.xticks(range(1, 13), [f'{i}월' for i in range(1, 13)])
    
    # 기획자 요청사항: Y축 3,000원 이하 절삭을 통해 변동폭(스프레드) 극대화
    plt.ylim(bottom=3000)
    
    plt.grid(True, linestyle='-', alpha=0.3)
    plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0.)
    plt.tight_layout()
    
    os.makedirs(DATA_PROCESSED, exist_ok=True)
    save_path = os.path.join(str(DATA_PROCESSED), 'rib_seasonality_advanced.png')
    plt.savefig(save_path, dpi=300)
    
    plt.show()

    # ==========================================================
    # 로직 4: EMA 트렌드 기반 차익 거래 ROI 시뮬레이션
    # ==========================================================
    min_month = ema_seasonality.idxmin()
    max_month = ema_seasonality.idxmax()
    min_price = ema_seasonality.min()
    max_price = ema_seasonality.max()
    
    spread = max_price - min_price
    roi_raw = (spread / min_price) * 100
    
    print("\n==================================================")
    print("[로직 2] EMA 최근 트렌드 기반 차익(Arbitrage) 산출")
    print("==================================================")
    print(f"1. 최적 매수 달 (최근 트렌드 기준): {int(min_month)}월 (가중평균 {min_price:,.0f}원)")
    print(f"2. 최적 매도 달 (최근 트렌드 기준): {int(max_month)}월 (가중평균 {max_price:,.0f}원)")
    print(f"3. 기대 스프레드(마진): {spread:,.0f}원")
    print(f"4. 기대 총수익률(ROI): {roi_raw:.1f}%")
    print("==================================================")

if __name__ == "__main__":
    main()