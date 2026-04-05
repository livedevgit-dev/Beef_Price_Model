# [파일 정의서]
# - 파일명: train_pct_check.py (시계열 시즌성 및 과열 피로도 추가 통합본)
# - 역할: 분석 (허구적 상관관계 검증 + 임계값 도출 + 명절/피로도 분석)
# - 주요 기능: 
#   1. [갈비 특화] 명절(설/추석) 도매 수요 시계열 변수 추가
#   2. [과열 감지] 3개월 누적 상승률을 통한 '마지막 불꽃(상투)' 감지 로직 추가
#   3. 초기 급등(Buy)과 피로도 누적 후 급등(Crash)을 분리하여 리포팅

import os
import sys
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.tree import DecisionTreeRegressor

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from config import DATA_PROCESSED

def main():
    file_path = os.path.join(DATA_PROCESSED, "ml_features_rolling_rib.csv")
    if not os.path.exists(file_path):
        print("에러: 데이터 파일이 없습니다.")
        return

    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    df = df.copy()

    # ----------------------------------------------------
    # 1. [기획자 아이디어] 과열 피로도 및 연속 상승 감지
    # ----------------------------------------------------
    df['kr_price_mom'] = df['kr_price'].pct_change() * 100
    # 최근 3개월간 도매가가 누적으로 몇 %나 올랐는가? (시장의 피로도 측정)
    df['kr_price_3m_mom'] = df['kr_price'].pct_change(periods=3) * 100

    # ----------------------------------------------------
    # 2. [기획자 아이디어] 갈비 특화: 시계열(명절) 시즌성
    # ----------------------------------------------------
    # 주석: 갈비는 설날(1~2월)과 추석(9~10월)이 최대 성수기. 
    # 도매 시장에서는 세트 작업을 위해 보통 1개월~1.5개월 전에 물량을 매입함.
    # 따라서 도매 수요가 폭발하는 1월, 8월, 9월을 '명절 도매 성수기'로 지정.
    df['month'] = df.index.month
    df['is_holiday_peak'] = df['month'].isin([1, 8, 9]).astype(int)

    # 기존 변수들 (기간 버퍼 및 수급)
    df['import_vol_mom'] = df['import_vol'].pct_change() * 100
    df['stock_mom'] = df['stock'].pct_change() * 100
    
    df['us_price_ma_3'] = df['us_price'].rolling(window=3).mean()
    df['us_price_ma_6'] = df['us_price'].rolling(window=6).mean()
    df['exchange_rate_ma_3'] = df['exchange_rate'].rolling(window=3).mean()
    df['exchange_rate_ma_6'] = df['exchange_rate'].rolling(window=6).mean()

    df['us_price_ma_3_mom'] = df['us_price_ma_3'].pct_change() * 100
    df['us_price_ma_6_mom'] = df['us_price_ma_6'].pct_change() * 100
    df['exchange_rate_ma_3_mom'] = df['exchange_rate_ma_3'].pct_change() * 100
    df['exchange_rate_ma_6_mom'] = df['exchange_rate_ma_6'].pct_change() * 100

    df['import_vol_yoy'] = df['import_vol'].pct_change(12) * 100
    df['stock_yoy'] = df['stock'].pct_change(12) * 100

    # 타겟: 6개월 내 최대 상승률(%)
    df['target_max_return_6m'] = (df['kr_price_max_6m'] - df['kr_price']) / df['kr_price'] * 100

    df = df.dropna()
    target_col = 'target_max_return_6m'
    
    # 모델에 투입할 정예 11개 변수 (명절 변수 및 누적 피로도 추가)
    features_to_use = [
        'kr_price_mom', 
        'kr_price_3m_mom',       # [추가] 과열 피로도
        'is_holiday_peak',       # [추가] 시계열 (명절 효과)
        'us_price_ma_3_mom', 'us_price_ma_6_mom',
        'exchange_rate_ma_3_mom', 'exchange_rate_ma_6_mom',
        'import_vol_mom', 'import_vol_yoy', 
        'stock_mom', 'stock_yoy'
    ]
    
    X = df[features_to_use]
    y = df[target_col]

    print(f"\n==================================================")
    print(f"  [파트 1] 핵심 변수 중요도 분석 (시즌성/과열 포함)")
    print(f"==================================================\n")

    model = xgb.XGBRegressor(n_estimators=100, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X, y)

    predictions = model.predict(X)
    print("--- 모델 평가 결과 ---")
    print(f"설명력 (R-squared): {r2_score(y, predictions):.4f}")
    
    fi_df = pd.DataFrame({'Feature': features_to_use, 'Importance': model.feature_importances_})
    fi_df = fi_df.sort_values(by='Importance', ascending=False).reset_index(drop=True)
    print("\n--- 핵심 변수 중요도 (Top 5) ---")
    print(fi_df.head(5).to_string(index=False))

    print(f"\n==================================================")
    print(f"  [파트 2] 입체적 마지노선: 신호탄인가, 꼭대기(상투)인가?")
    print(f"==================================================\n")

    # 1단계: 월간 상승폭 마지노선 도출 (이전과 동일)
    X_tree1 = df[['kr_price_mom']]
    tree1 = DecisionTreeRegressor(max_depth=1, random_state=42).fit(X_tree1, y)
    thresh1 = tree1.tree_.threshold[0]
    
    print(f"[1단계: 모멘텀 감지] 이번 달 도매가가 {thresh1:.2f}% 이상 올랐는가?")
    
    # 2단계: 급등한 달(> thresh1)을 모아서, 3개월 누적 피로도에 따라 '진짜 상승'과 '폭락' 분리
    boom_df = df[df['kr_price_mom'] > thresh1].copy()
    
    if len(boom_df) > 5: # 데이터가 충분할 때만 2단계 분석 실행
        X_tree2 = boom_df[['kr_price_3m_mom']]
        y_tree2 = boom_df[target_col]
        tree2 = DecisionTreeRegressor(max_depth=1, random_state=42).fit(X_tree2, y_tree2)
        
        thresh2 = tree2.tree_.threshold[0]
        left_val = tree2.tree_.value[1][0][0]  # 피로도가 낮을 때 (초기 진입)
        right_val = tree2.tree_.value[2][0][0] # 피로도가 높을 때 (상투/과열)
        
        print(f"[2단계: 상투/폭락 감지] 만약 {thresh1:.2f}% 급등했다면, 최근 3개월 누적 상승률이 【 {thresh2:.2f}% 】를 넘었는가?")
        print(f"\n[최종 AI 판단 시나리오]")
        print(f"   시나리오 A (초기 폭발): 이번 달 급등했지만, 3개월 누적 상승률이 {thresh2:.2f}% 미만일 때")
        print(f"       -> 대세 상승장 시작! 향후 6개월간 평균 {left_val:.1f}% 추가 폭등 가능성 높음 (Buy & Hold)")
        print(f"\n   시나리오 B (과열 끝물/폭락 예고): 이번 달 급등했고, 3개월 누적 상승률도 {thresh2:.2f}% 이상일 때")
        print(f"       -> 시장 과열 및 상투(고점) 도달. 상승 여력 고갈로 향후 6개월 기대수익은 {right_val:.1f}%에 불과 (강력 매수 주의 및 매도 준비)")
    else:
        print("급등 데이터가 부족하여 2단계 과열 감지를 수행할 수 없습니다.")
        
    print("---------------------------------------------------\n")

if __name__ == "__main__":
    main()