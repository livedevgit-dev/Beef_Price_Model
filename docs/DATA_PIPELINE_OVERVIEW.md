# 데이터 수집 파이프라인 전체 지도 (Overview)

> 이 프로젝트의 데이터가 **무엇을 / 어떤 주기로 / 어떻게 실행해서** 들어오는지 한눈에 정리한 문서.
>
> 상세 규칙: [DATA_COLLECTION_RULES.md](DATA_COLLECTION_RULES.md) · 한우/KAMIS: [KAMIS_HANDOFF.md](KAMIS_HANDOFF.md) · 거시: [MACRO_HANDOFF.md](MACRO_HANDOFF.md)

---

## 1. 핵심 개념 — "백필"은 별도 절차가 아니다

모든 수집기는 **증분형(incremental)** 으로, 같은 코드가 상황에 따라 두 역할을 한다:

| 실행 시점 | 동작 |
|---|---|
| **최초 실행** | 기존 데이터 없음 → 2019-01-01부터 **과거 전체 백필** |
| **이후 실행** | 마지막 저장일 이후만 **증분 수집** |

즉 "과거 수집 전용 스크립트"는 없다. 처음 돌리면 백필, 그 뒤로는 매번 증분이다.
예외적으로 **KAMIS만 1회 실행당 400일 한도**라, 초기에 따라잡을 때만 여러 번 반복 실행이 필요하다(이후엔 1일 증분).

> ⚠️ **동시 실행 금지**: 같은 수집기를 두 프로세스가 동시에 돌리면 API 중복요청으로 차단(throttling)될 수 있다. 백필 중에는 `run_daily_update`를 보류하고, 백필 완료 후 daily를 시작한다.

---

## 2. 추출 주기별 데이터

### 일(日) 단위
| 데이터 | 수집기 | 산출물 |
|---|---|---|
| 미트박스 B2B 도매시세(수입육) | `crawl_imp_price_meatbox.py` | `master_price_data.csv` |
| USDA 부위별 시세 | `api_us_beef_collect_usda.py` | `usda_beef_history.csv` |
| USDA 프라이멀 시세 | `collect_usda_primal.py` | `usda_primal_history.csv` |
| USD/KRW 환율 | `crawl_com_usd_krw.py` | `exchange_rate_data.xlsx` |
| 한우 경락가·도축두수(EKAPE) | `crawl_han_auction_api.py` | `han_auction_raw.csv` |
| 한우 부위 도/소매가(KAMIS) | `collect_kamis_hanwoo.py` | `kamis_hanwoo_raw.csv` |
| 거시-WTI 원유(FRED) | `collect_macro_fred.py` | `macro_indicators_raw.csv` |
| 거시-기온·강수(기상청) | `collect_macro_kma.py` | `macro_indicators_raw.csv` |

### 월(月) 단위
| 데이터 | 수집기 | 산출물 |
|---|---|---|
| KMTA 수입량 | `crawl_imp_volume_monthly.py` | `master_import_volume.csv` |
| KMTA 재고 | `crawl_imp_stock_monthly.py` | `beef_stock_data.xlsx` |
| 식약처 검역 실적(수입 보완) | `crawl_imp_food_safety.py` | `master_import_volume.csv` |
| 거시-옥수수·대두·대두박·Food PPI(FRED) | `collect_macro_fred.py` | `macro_indicators_raw.csv` |
| 거시-금리·CPI·PPI·심리지수(ECOS) | `collect_macro_ecos.py` | `macro_indicators_raw.csv` |

> FRED·ECOS·KMA는 한 수집기 안에 일/월 지표가 섞여 있다(예: FRED는 WTI=일, 옥수수=월). indicator별 주기는 `freq` 컬럼으로 구분.

---

## 3. 실행 방법 — `run_daily_update.py`로 들어오는 것 vs 수동 `.py`

### A. `run_daily_update.py` 모드별 포함 범위

| 모드 | 명령 | 포함 수집·전처리 |
|---|---|---|
| **기본(price-only)** | `python src/run_daily_update.py` | 미트박스(필수) + 한우(EKAPE+KAMIS) + 각 전처리 + 스키마 + GAP리포트 |
| **전체(full)** | `python src/run_daily_update.py --full` | [1]일별 6종 [2]월별 3종 [2-1]거시 3종(FRED/ECOS/KMA) → [3]USDA전처리 [4]미트박스전처리 [5]한우전처리 [5-1]거시전처리 [6]스키마 |
| **월별(monthly)** | `python src/run_daily_update.py --monthly` | KMTA 수입량(+`--with-stock` 시 재고) + 수입 공백 시 식약처 보완 + GAP |
| **검증만** | `python src/run_daily_update.py --gap-check` | 수집 없이 데이터 최신성 GAP 리포트만 |

- 모든 외부 수집(USDA·월별·거시)은 `critical=False` → **실패해도 미트박스 등 핵심은 보존**되고 파이프라인이 끝까지 진행됨.
- 성공 시 `data/` 산출물을 자동 git 커밋(`--no-commit`으로 끔, `--push`로 원격 반영).

### B. 권장 실행 스케줄

| 시점 | 명령 | 목적 |
|---|---|---|
| 매 평일 | `run_daily_update.py` | 미트박스+한우 일별 + GAP |
| 주 1회(월요일) | `run_daily_update.py --full` | 일별+월별+거시 전체 |
| 매월 10·20일 | `run_daily_update.py --monthly` | KMTA 수입·재고 재시도 |

### C. `run_daily_update`에 **포함되지 않는** 수동 실행 항목

| 항목 | 스크립트 | 실행 시점 |
|---|---|---|
| 미트미플 카페 B2B 크롤링 | `collect_cafe_b2b.py` | 수시(수동) |
| ML 피처 생성 | `feature_engineering.py`, `feature_engineering_rolling.py` | 모델링 전(수동) |
| 모델 학습 | `Models/train_*.py` | 수동 |
| 매핑 검증·수동 데이터 | `validate_mapping.py`, `init_manual_data.py` 등 | 필요 시 |

> 거시 전처리(`preprocess_macro.py`), 한우 전처리(`preprocess_hanwoo.py`)는 `--full`/기본 모드에 **포함**되어 있어 따로 돌릴 필요 없음(단독 실행도 가능).

---

## 4. 전처리(가공) 단계 — 수집 후 자동 실행

| 전처리 | 입력 → 출력 | 포함 모드 |
|---|---|---|
| `preprocess_meat_data.py` | master_price → `dashboard_ready_data.csv` | 기본·full |
| `preprocess_hanwoo.py` | EKAPE+KAMIS raw → `hanwoo_dashboard_ready.csv` | 기본·full |
| `process_usda_data.py`, `preprocess_primal.py` | USDA+환율 → 원가/plate | full |
| `preprocess_macro.py` | macro raw → `macro_indicators_daily.csv` + `macro_dashboard_ready.csv` | full |
| `extract_data_schema.py` | 전체 → `DATA_DICTIONARY.md` 갱신 | 기본·full |

---

## 5. 대시보드(Streamlit) — 산출물 소비

| 페이지 | 데이터 |
|---|---|
| 01 Price / 02 Import / 03 Inventory / 04 Backtesting / 05 USDA | 미트박스·수입·재고·USDA |
| 06 Hanwoo | `hanwoo_dashboard_ready.csv` (EKAPE 경락 + KAMIS 부위별 도/소매) |
| 07 Macro | `macro_indicators_daily.csv` (금리·물가·사료·유가·심리·기후) |

실행: `streamlit run src/Home.py`

---

## 6. 초기 셋업 vs 일상 운영 요약

**초기(1회): 과거 백필**
```powershell
# 각 수집기를 처음 돌리면 2019부터 백필됨. 한 번에:
python src/run_daily_update.py --full        # 미트박스·USDA·환율·EKAPE·KMTA·거시 일괄 백필
# KAMIS만 400일/회 제한 → 따라잡을 때까지 반복(이후엔 자동 증분)
python src/collectors/collect_kamis_hanwoo.py   # 현재까지 여러 번
python src/utils/preprocess_hanwoo.py
```

**일상(반복): 증분**
```powershell
python src/run_daily_update.py            # 평일
python src/run_daily_update.py --full     # 주 1회
python src/run_daily_update.py --monthly  # 매월 10·20일
```

> KAMIS 백필이 현재까지 따라잡힌 뒤에는 `run_daily_update`만으로 모든 일/월 데이터가 증분 수집된다. 백필 진행 중에는 동시 실행을 피한다.

---

## 7. 변경 이력
| 날짜 | 내용 |
|------|------|
| 2026-06-17 | 데이터 파이프라인 전체 지도 신규 작성 (주기·실행방법·백필vs증분·수동항목 정리) |
