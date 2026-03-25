# Beef Price Model — 프로젝트 가이드

> **최종 갱신일**: 2026-03-25
> **목적**: 폴더 구조, 모듈 역할, 실행 방법, 네이밍 규칙을 한 곳에서 관리

---

## 1. 폴더 구조

```
Beef_Price_Model/
├── README.md                        # 프로젝트 소개 (Quick Start)
├── requirements.txt                 # 의존성 패키지
├── setup_project.py                 # 초기 폴더 스캐폴드
├── .env                             # API 키 (USDA_API_KEY 등)
│
├── src/
│   ├── config.py                    # 경로·설정 일원화 (모든 모듈이 참조)
│   ├── Home.py                      # Streamlit 메인 진입점
│   ├── run_daily_update.py          # 일일 파이프라인 (수집 → 전처리 → 스키마 갱신)
│   │
│   ├── collectors/                  # 데이터 수집 모듈 (10개)
│   │   ├── crawl_imp_price_meatbox.py
│   │   ├── crawl_imp_price_history.py
│   │   ├── crawl_imp_volume_monthly.py
│   │   ├── crawl_imp_stock_monthly.py
│   │   ├── crawl_imp_food_safety.py
│   │   ├── crawl_com_usd_krw.py
│   │   ├── crawl_han_auction_api.py
│   │   ├── api_us_beef_collect_usda.py
│   │   ├── collect_usda_primal.py
│   │   └── collect_cafe_b2b.py
│   │
│   ├── utils/                       # 전처리·피처 엔지니어링 (9개)
│   │   ├── preprocess_meat_data.py
│   │   ├── process_usda_data.py
│   │   ├── preprocess_primal.py
│   │   ├── feature_engineering.py
│   │   ├── feature_engineering_rolling.py
│   │   ├── init_manual_data.py
│   │   ├── validate_mapping.py
│   │   ├── check_existing_names.py
│   │   └── extract_data_schema.py
│   │
│   ├── pages/                       # Streamlit 대시보드 페이지 (4개)
│   │   ├── 01_Price_Dashboard.py
│   │   ├── 02_Import_Analysis.py
│   │   ├── 03_Inventory_Management.py
│   │   └── 04_Backtesting_Analysis.py
│   │
│   ├── Models/                      # 예측 모델 학습 (3개)
│   │   ├── train_baseline.py
│   │   ├── train_rolling_horizon.py
│   │   └── train_pct_check.py
│   │
│   ├── visualizations/              # 분석·시각화 스크립트 (4개)
│   │   ├── vis_rib_seasonality_advanced.py
│   │   ├── analyze_rib_multivar.py
│   │   ├── analyze_shortplate_multivar.py
│   │   └── analyze_shortplate_lag.py
│   │
│   └── z_archive/                   # 레거시·디버그 스크립트 (~23개)
│
├── data/
│   ├── 0_raw/                       # 원시 데이터
│   ├── 1_processed/                 # 가공 데이터
│   └── 2_dashboard/                 # 대시보드 표출용 최종 데이터
│
└── docs/
    ├── PROJECT_GUIDE.md             # 본 문서
    ├── DATA_DICTIONARY.md           # 데이터 파일 사전 + 자동생성 스키마
    ├── PROJECT_STRUCTURE_PROPOSAL.md  # 리팩토링 계획·진행 상태
    └── Project_History.xlsx         # 프로젝트 이력
```

---

## 2. 실행 방법

### 2.1 대시보드 실행

```bash
streamlit run src/Home.py
```

### 2.2 일일 데이터 업데이트

```bash
python src/run_daily_update.py
```

파이프라인 수행 순서:

1. **수집** — `collectors/crawl_imp_price_meatbox.py` 실행 → `data/1_processed/master_price_data.csv` 갱신
2. **전처리** — `utils/preprocess_meat_data.py` 실행 → `data/2_dashboard/dashboard_ready_data.csv` 갱신
3. **문서 갱신** — `utils/extract_data_schema.py` 실행 → `docs/DATA_DICTIONARY.md` 자동생성 스키마 갱신

### 2.3 개별 크롤러 실행

```bash
python src/collectors/crawl_imp_price_meatbox.py      # 미트박스 시세
python src/collectors/crawl_imp_volume_monthly.py      # KMTA 월별 수입량
python src/collectors/crawl_imp_stock_monthly.py       # KMTA 재고
python src/collectors/crawl_imp_food_safety.py         # 식약처 검역
python src/collectors/crawl_com_usd_krw.py             # 환율
python src/collectors/crawl_han_auction_api.py         # 축평원 경락가격
python src/collectors/api_us_beef_collect_usda.py      # USDA 시세
python src/collectors/collect_usda_primal.py           # USDA 프라이멀
python src/collectors/collect_cafe_b2b.py              # 미트미플 카페 B2B
```

---

## 3. 모듈 상세

### 3.1 Collectors — 데이터 수집

| 모듈 | 데이터 소스 | 수집 주기 | 출력 위치 |
|------|------------|----------|----------|
| `crawl_imp_price_meatbox` | 미트박스 B2B 도매시세 | 일별 | `1_processed/master_price_data.csv` |
| `crawl_imp_price_history` | 미트박스 API 과거 시세 | 비정기 | `0_raw/` |
| `crawl_imp_volume_monthly` | KMTA 월별 부위별 수입량 | 월별 | `0_raw/master_import_volume.csv` |
| `crawl_imp_stock_monthly` | KMTA 월별 재고 현황 | 월별 | `0_raw/beef_stock_data.xlsx` |
| `crawl_imp_food_safety` | 식약처 수입 검역 실적 | 월별 | `0_raw/raw_food_safety_data.csv` |
| `crawl_com_usd_krw` | 네이버 금융 USD/KRW 환율 | 일별 | `0_raw/exchange_rate_data.xlsx` |
| `crawl_han_auction_api` | 축산물품질평가원 경락가격 | 일별 | `0_raw/` |
| `api_us_beef_collect_usda` | USDA LM_XB403 부위별 시세 | 일별 | `0_raw/usda_beef_history.csv` |
| `collect_usda_primal` | USDA LM_XB403 프라이멀 시세 | 일별 | `0_raw/usda_primal_history.csv` |
| `collect_cafe_b2b` | 미트미플 카페 B2B 크롤링 | 수시 | `0_raw/raw_cafe_b2b_crawling.csv` |

### 3.2 Utils — 전처리·피처 엔지니어링

| 모듈 | 역할 | 파이프라인 포함 |
|------|------|----------------|
| `preprocess_meat_data` | master → dashboard_ready 변환 (이동평균, 부위/브랜드 분리) | **자동** (일일) |
| `extract_data_schema` | 데이터 파일 스키마 분석 → DATA_DICTIONARY.md 갱신 | **자동** (일일) |
| `process_usda_data` | USDA 시세 + 환율 → KRW 원가 산출 | 수동 (주 1회 권장) |
| `preprocess_primal` | Primal 시세 → plate USD/kg 변환 | 수동 (USDA와 연계) |
| `feature_engineering` | 월별 ML 피처 생성 (lag, YoY, MoM 등) | 수동 |
| `feature_engineering_rolling` | 롤링 윈도우 기반 ML 피처 생성 | 수동 |
| `init_manual_data` | 수동 가격 입력 템플릿 생성 | 수동 (초기 1회) |
| `validate_mapping` | USDA 코드 ↔ 한글명 매핑 검증 | 수동 |
| `check_existing_names` | 마스터 표준명 추출·확인 | 수동 |

### 3.3 Pages — Streamlit 대시보드

| 페이지 | 기능 |
|--------|------|
| `01_Price_Dashboard` | 가격 추세 및 비교 분석 |
| `02_Import_Analysis` | 수입량 분석 및 시각화 |
| `03_Inventory_Management` | 재고 현황 모니터링 |
| `04_Backtesting_Analysis` | 예측 모델 백테스팅 결과 시각화 |

### 3.4 Models — 예측 모델 학습

| 모듈 | 역할 |
|------|------|
| `train_baseline` | 기본 예측 모델 학습 |
| `train_rolling_horizon` | 롤링 호라이즌 방식 모델 학습·평가 |
| `train_pct_check` | 변동률 기반 모델 검증 |

### 3.5 Visualizations — 분석·시각화

| 모듈 | 역할 |
|------|------|
| `vis_rib_seasonality_advanced` | 리브(갈비) 계절성 심화 분석 |
| `analyze_rib_multivar` | 리브 다변량 분석 |
| `analyze_shortplate_multivar` | 숏플레이트(양지) 다변량 분석 |
| `analyze_shortplate_lag` | 숏플레이트 시차(lag) 분석 |

---

## 4. 데이터 흐름

```
[외부 소스]                [Collectors]               [Utils]                  [Dashboard]
─────────────────────────────────────────────────────────────────────────────────────────
미트박스                → 0_raw / 1_processed  ─→  preprocess_meat_data  ─→  2_dashboard
KMTA (수입량·재고)     → 0_raw                                               ↓
식약처                  → 0_raw                                          Pages (시각화)
네이버 금융 (환율)      → 0_raw                ─→  process_usda_data    ─→  1_processed
USDA API               → 0_raw                ─→  preprocess_primal    ─→  1_processed
축평원 API             → 0_raw
수동 입력               → 0_raw
```

---

## 5. 경로 관리

모든 모듈은 `src/config.py`를 import하여 경로를 참조합니다:

```python
from config import DATA_RAW, DATA_PROCESSED, MASTER_PRICE_CSV
```

`config.py`에서 `Path(__file__)`을 기준으로 프로젝트 루트를 자동 산출하므로, 실행 위치에 무관하게 동작합니다.

---

## 6. 파일 명명 규칙 (Naming Convention)

### Prefix (역할)

| Prefix | 의미 | 예시 |
|--------|------|------|
| `crawl` | 외부 데이터 수집 (크롤링, API) | `crawl_imp_price_meatbox.py` |
| `proc` | 데이터 전처리 및 마스터 생성 | `preprocess_meat_data.py` |
| `anal` | 분석 및 모델 학습 | `analyze_rib_multivar.py` |
| `viz` / `vis` | 시각화 및 대시보드 | `vis_rib_seasonality_advanced.py` |
| `api` | 외부 API 연동 수집 | `api_us_beef_collect_usda.py` |
| `collect` | 데이터 수집 (API 기반) | `collect_usda_primal.py` |
| `train` | 모델 학습 | `train_baseline.py` |

### Category (대상)

| Category | 의미 |
|----------|------|
| `imp` | 수입 소고기 (Imported) |
| `han` | 한우 (Hanwoo) |
| `com` | 공통 지표 (환율, 금리 등) |
| `us` / `usda` | 미국 USDA 데이터 |

---

## 7. 주의사항

1. **chromedriver.exe** — Selenium 크롤러는 `src/chromedriver.exe` 필요
2. **API Key** — `crawl_han_auction_api.py`는 축평원 API 키 필요 (`.env` 관리)
3. **USDA API Key** — `api_us_beef_collect_usda.py`는 USDA API 키 필요 (`.env` 관리)
4. **네트워크** — 모든 크롤러는 인터넷 연결 필요
5. **Import 오류** — 프로젝트 루트에서 실행하거나 `PYTHONPATH`에 `src/` 추가

```bash
# Windows
set PYTHONPATH=%PYTHONPATH%;%cd%\src

# Linux / Mac
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```
