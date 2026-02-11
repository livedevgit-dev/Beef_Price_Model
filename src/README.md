# Beef Price Model - Source Code Structure

## 📁 폴더 구조

```
src/
├── Home.py                      # 🏠 Streamlit 메인 실행 파일
├── run_daily_update.py          # 🔄 일일 데이터 업데이트 파이프라인
│
├── collectors/                  # 📥 데이터 수집 모듈
│   ├── __init__.py
│   ├── crawl_imp_price_meatbox.py      # 미트박스 시세 데이터
│   ├── crawl_imp_volume_monthly.py     # KMTA 월별 수입량
│   ├── crawl_imp_stock_monthly.py      # KMTA 재고 데이터
│   ├── crawl_imp_food_safety.py        # 식약처 검역 데이터
│   ├── crawl_imp_price_history.py      # 미트박스 과거 시세
│   ├── crawl_com_usd_krw.py            # 환율 데이터
│   └── crawl_han_auction_api.py        # 축평원 경락가격
│
├── utils/                       # 🛠️ 유틸리티 및 전처리 모듈
│   ├── __init__.py
│   └── preprocess_meat_data.py         # 데이터 전처리 및 가공
│
├── pages/                       # 📊 Streamlit 대시보드 페이지
│   ├── 01_Price_Dashboard.py           # 가격 분석 대시보드
│   ├── 02_Import_Analysis.py           # 수입량 분석 대시보드
│   └── 03_Inventory_Management.py      # 재고 관리 대시보드
│
└── z_archive/                   # 📦 사용하지 않는 레거시 파일
    └── (구버전 분석 및 처리 스크립트)
```

## 🚀 실행 방법

### 1. 대시보드 실행
```bash
streamlit run src/Home.py
```

### 2. 데이터 업데이트
```bash
python src/run_daily_update.py
```

이 명령은 다음 작업을 순차적으로 수행합니다:
1. 미트박스에서 최신 시세 데이터 수집 (`collectors/crawl_imp_price_meatbox.py`)
2. 수집된 데이터 전처리 및 대시보드용 데이터 생성 (`utils/preprocess_meat_data.py`)

### 3. 개별 크롤러 실행
각 크롤러를 독립적으로 실행할 수 있습니다:

```bash
# 미트박스 시세 수집
python src/collectors/crawl_imp_price_meatbox.py

# 월별 수입량 수집
python src/collectors/crawl_imp_volume_monthly.py

# 재고 데이터 수집
python src/collectors/crawl_imp_stock_monthly.py

# 식약처 검역 데이터 수집
python src/collectors/crawl_imp_food_safety.py

# 환율 데이터 수집
python src/collectors/crawl_com_usd_krw.py

# 축평원 경락가격 수집
python src/collectors/crawl_han_auction_api.py
```

## 📝 모듈 설명

### Collectors (수집기)
각 크롤러는 독립적으로 실행 가능하며, 데이터를 `data/0_raw/` 또는 `data/1_processed/` 폴더에 저장합니다.

- **crawl_imp_price_meatbox.py**: 미트박스 사이트에서 수입육 도매시세를 수집
- **crawl_imp_volume_monthly.py**: KMTA에서 월별 부위별 수입량 데이터 수집
- **crawl_imp_stock_monthly.py**: KMTA에서 월별 재고 현황 데이터 수집
- **crawl_imp_food_safety.py**: 식약처에서 수입 검역 실적 데이터 수집
- **crawl_imp_price_history.py**: 미트박스 API를 통한 과거 시세 데이터 수집
- **crawl_com_usd_krw.py**: 네이버 금융에서 USD/KRW 환율 데이터 수집
- **crawl_han_auction_api.py**: 축산물품질평가원 API로 한우 경락가격 수집

### Utils (유틸리티)
- **preprocess_meat_data.py**: 
  - 수집된 원시 데이터를 전처리
  - 부위/브랜드 정보 분리
  - 이동평균 등 기술적 지표 계산
  - 대시보드용 데이터셋 생성

### Pages (대시보드 페이지)
- **01_Price_Dashboard.py**: 가격 추세 및 비교 분석
- **02_Import_Analysis.py**: 수입량 분석 및 시각화
- **03_Inventory_Management.py**: 재고 현황 모니터링

## 🔧 데이터 경로 규칙

모든 스크립트는 실행 위치와 무관하게 프로젝트 루트를 기준으로 데이터 경로를 찾습니다:

```python
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)  # src 폴더
project_root = os.path.dirname(src_dir)  # 프로젝트 루트
data_dir = os.path.join(project_root, "data", "0_raw")
```

## 📊 데이터 흐름

```
[데이터 소스] 
    ↓
[Collectors] → data/0_raw/ (원시 데이터)
    ↓
[Collectors] → data/1_processed/ (1차 가공)
    ↓
[Utils] → data/2_dashboard/ (대시보드용 데이터)
    ↓
[Pages] → 시각화 및 분석
```

## 🎯 향후 확장 계획

### Collectors
- 미국 USDA 데이터 수집기 추가 예정
- 호주 MLA 데이터 수집기 추가 예정

### Utils
- 거시경제 지표 통합 모듈 추가 예정
- 예측 모델링 유틸리티 추가 예정

## ⚠️ 주의사항

1. **chromedriver.exe**: Selenium을 사용하는 크롤러들은 `src/chromedriver.exe`가 필요합니다.
2. **API Key**: `crawl_han_auction_api.py`는 축산물품질평가원 API 키가 필요합니다.
3. **실행 권한**: 일부 크롤러는 관리자 권한이 필요할 수 있습니다.
4. **네트워크**: 모든 크롤러는 인터넷 연결이 필요합니다.

## 📌 문제 해결

### Import 오류 발생 시
프로젝트 루트에서 실행하거나, PYTHONPATH를 설정하세요:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 경로 오류 발생 시
모든 스크립트는 절대 경로를 사용하므로 어디서든 실행 가능합니다.
문제가 발생하면 `data/` 폴더가 프로젝트 루트에 존재하는지 확인하세요.
