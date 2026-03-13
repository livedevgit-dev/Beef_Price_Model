# [파일 정의서]
# - 파일명: train_baseline.py
# - 역할: 분석
# - 대상: 수입육
# - 데이터 소스: ml_features_rib.csv
# - 주요 기능: 전체 69개월 데이터를 100% 학습하여 과거와 현재 패러다임을 모두 관통하는 핵심 변수 중요도(Feature Importance) 추출

import os
import sys
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

# 경로 설정: 상위 폴더(src)를 시스템 경로에 추가하여 config.py 인식
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from config import DATA_PROCESSED

def main():
    file_path = os.path.join(DATA_PROCESSED, "ml_features_rib.csv")
    if not os.path.exists(file_path):
        print("에러: 파일을 찾을 수 없습니다.")
        return

    # 데이터 로드
    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    
    # 타겟: 1개월 뒤 가격 증감액 (Delta)
    target_col = 'kr_price_diff_lead_1'
    
    # 정답 유출 방지
    drop_cols = ['kr_price_lead_1', 'kr_price_lead_2', 'kr_price_diff_lead_1', 'kr_price_diff_lead_2']
    X = df.drop(columns=drop_cols)
    y = df[target_col]

    # 기획자 요청 반영: 데이터를 분할하지 않고 '전체 기간'을 모두 학습 (100% Train)
    X_train = X
    y_train = y
    
    print(f"==================================================")
    print(f"  전체 기간({df.shape[0]}개월) 통합 학습 및 중요도 분석")
    print(f"==================================================\n")

    # 모델 정의
    # 전체 데이터를 학습하므로 과적합을 적절히 제어하면서도 충분히 학습하도록 설정
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42
    )
    
    # 모델 학습 (전체 69개월 데이터)
    model.fit(X_train, y_train)

    # 예측 및 평가 (자신이 학습한 전체 데이터에 대해 얼마나 잘 맞췄는지 평가 - In-sample)
    predictions = model.predict(X_train)
    mae = mean_absolute_error(y_train, predictions)
    r2 = r2_score(y_train, predictions)
    
    print("--- [전체 기간 학습] 모델 평가 결과 ---")
    print(f"평균 절대 오차 (MAE): {mae:.2f} 원 (변동폭 예측 오차)")
    print(f"설명력 (R-squared): {r2:.4f} (In-sample 이므로 높게 나옴)")
    print("---------------------------------------\n")

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