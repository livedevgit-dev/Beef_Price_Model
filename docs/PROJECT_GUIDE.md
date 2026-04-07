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
# 기본 (미트박스 가격만)
python src/run_daily_update.py

# 미트박스 가격만 (명시적)
python src/run_daily_update.py --price-only

# 전체 수집 + 전처리 (USDA·환율·수입량·재고·식약처 포함)
python src/run_daily_update.py --full

# 성공 시 GitHub 반영: 커밋 후 원격 푸시
python src/run_daily_update.py --full --push
```

#### 성공 시 자동 Git 커밋

모든 단계가 성공(`실패 0`)이면 `data/0_raw`, `data/1_processed`, `data/2_dashboard`, `docs/DATA_DICTIONARY.md`만 스테이징하여 커밋합니다(소스 코드는 포함하지 않음).

| 옵션 / 환경변수 | 설명 |
|-----------------|------|
| (기본) | 성공 시 로컬 `git commit` |
| `--no-commit` | 커밋 생략 |
| `--push` 또는 `PIPELINE_GIT_PUSH=1` | 커밋 후 `git push` (GitHub 등 원격에 반영) |

원격 푸시는 자격 증명(SSH, 자격 증명 관리자 등)이 미리 설정되어 있어야 합니다.

#### `--price-only` (기본) 수행 순서:

1. **수집** — `collectors/crawl_imp_price_meatbox.py` 실행 → `data/1_processed/master_price_data.csv` 갱신
2. **전처리** — `utils/preprocess_meat_data.py` 실행 → `data/2_dashboard/dashboard_ready_data.csv` 갱신
3. **문서 갱신** — `utils/extract_data_schema.py` 실행 → `docs/DATA_DICTIONARY.md` 자동생성 스키마 갱신

#### `--full` 수행 순서:

1. **일별 수집** — 미트박스 시세, USDA 부위별/프라이멀 시세, USD/KRW 환율
2. **월별 수집** — KMTA 수입량, KMTA 재고, 식약처 검역
3. **USDA 전처리** — `process_usda_data.py` (환율 반영 원가), `preprocess_primal.py` (Plate USD/kg)
4. **미트박스 전처리** — `preprocess_meat_data.py` → `dashboard_ready_data.csv`
5. **문서 갱신** — `extract_data_schema.py` → `DATA_DICTIONARY.md`

> **참고**: `--full` 모드에서는 개별 수집기 실패가 전체 파이프라인을 중단하지 않습니다. 실패한 단계는 로그에 표시되며, 나머지 단계는 계속 진행됩니다.

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
| `preprocess_meat_data` | master → dashboard_ready 변환 (이동평균, 부위/브랜드 분리) | **자동** (일일 · `--full`) |
| `extract_data_schema` | 데이터 파일 스키마 분석 → DATA_DICTIONARY.md 갱신 | **자동** (일일 · `--full`) |
| `process_usda_data` | USDA 시세 + 환율 → KRW 원가 산출 | **자동** (`--full`) |
| `preprocess_primal` | Primal 시세 → plate USD/kg 변환 | **자동** (`--full`) |
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

1. **Chrome / ChromeDriver** — 기본적으로 Selenium 4 Manager가 설치된 Chrome 버전에 맞는 드라이버를 자동으로 받아 사용한다 (`utils/selenium_chrome.py`). 사내망 등에서 자동 다운로드가 막혀 있으면 환경변수 `USE_LOCAL_CHROMEDRIVER=1`을 설정하고, `src/chromedriver.exe`를 현재 Chrome 메이저 버전에 맞게 교체한다.
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

---

## 8. USDA 데이터 장기 미수집 시 복구 가이드

> 등록일: 2026-04-01 (3개월 공백 발생 시점 기준 작성)

USDA 수집기를 장기간 실행하지 않았을 경우 아래 사항에 유의한다.

### 8.1 수집기별 동작 방식

| 수집기 | 방식 | 장기 미수집 시 동작 |
|--------|------|---------------------|
| `api_us_beef_collect_usda.py` | **증분 수집** — 마지막 수집일 이후 영업일만 추가 요청 | 공백 기간만큼 자동 보충. 날짜별 4개 섹션 개별 API 호출 → 3개월 ≈ 63영업일 × 4 = ~252회 호출. 130일마다 중간 저장(checkpoint). |
| `collect_usda_primal.py` | **전체 재수집** — 2019년~현재까지 연도별 전체 요청 | 매 실행마다 전체 히스토리를 다시 수집하므로 공백 자체는 문제 없음. 단, 연도당 1회 API 호출로 대용량 응답 수신. |

### 8.2 장기 공백 복구 시 주의사항

1. **USDA API 속도 제한**: 단시간 대량 호출 시 일시 차단될 수 있음. `api_us_beef_collect_usda.py`는 내부에 `time.sleep`이 있으나, 공백이 6개월 이상이면 실행 시간이 상당히 길어질 수 있음
2. **실행 순서**: USDA beef → USDA primal → 환율 수집 완료 후, `process_usda_data.py` → `preprocess_primal.py` 순으로 전처리
3. **네트워크 중단 대비**: `api_us_beef_collect_usda.py`는 130일 단위 중간 저장을 하므로, 중단 후 재실행하면 마지막 저장 지점부터 이어서 수집
4. **`--full` 모드 활용**: `python src/run_daily_update.py --full` 실행 시 위 전체 과정이 순차 자동 실행됨
