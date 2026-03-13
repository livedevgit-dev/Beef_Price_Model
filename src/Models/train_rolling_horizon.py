# [파일 정의서]
# - 파일명: train_rolling_horizon.py
# - 역할: 분석 (중장기 버퍼 예측)
# - 주요 기능: 향후 6개월 내 '최대 상승폭'을 결정짓는 핵심 변수(Feature Importance) 추출

import os
import sys
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from config import DATA_PROCESSED

def main():
    # 롤링 윈도우 전용 데이터 로드
    file_path = os.path.join(DATA_PROCESSED, "ml_features_rolling_rib.csv")
    if not os.path.exists(file_path):
        print("에러: 파일을 찾을 수 없습니다. feature_engineering_rolling.py를 먼저 실행하세요.")
        return

    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    
    # 타겟: 향후 6개월 내 최대 상승폭
    target_col = 'target_max_diff_6m'
    
    # 정답 유출 방지: 1~6개월 미래 가격 정보 모두 제거
    leak_cols = [f'kr_price_lead_{i}' for i in range(1, 7)] + ['kr_price_max_6m', 'target_max_diff_6m']
    X = df.drop(columns=leak_cols)
    y = df[target_col]

    # 기획자 로직: 전체 패턴 학습 (In-sample 분석)
    X_train = X
    y_train = y
    
    print(f"==================================================")
    print(f"  [6개월 버퍼 모델] 통합 학습 및 중요도 분석")
    print(f"==================================================\n")

    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42
    )
    
    model.fit(X_train, y_train)

    predictions = model.predict(X_train)
    mae = mean_absolute_error(y_train, predictions)
    r2 = r2_score(y_train, predictions)
    
    print("--- [6개월 버퍼] 모델 평가 결과 ---")
    print(f"평균 절대 오차 (MAE): {mae:.2f} 원 (최대 상승폭 오차)")
    print(f"설명력 (R-squared): {r2:.4f} (In-sample)")
    print("-----------------------------------\n")

    # 변수 중요도 추출
    importance = model.feature_importances_
    feature_names = X.columns
    
    fi_df = pd.DataFrame({
        'Feature': feature_names,
        'Importance': importance
    }).sort_values(by='Importance', ascending=False).reset_index(drop=True)

    print("--- 핵심 변수 중요도 (Top 5) ---")
    print(fi_df.head(5).to_string(index=False))
    print("--------------------------------")

if __name__ == "__main__":
    main()