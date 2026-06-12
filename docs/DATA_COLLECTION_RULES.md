# 데이터 수집 운영 규칙 (Data Collection Rules)

> 목적: 재고·수입·USDA 등 **월별/일별 데이터 누락을 구조적으로 방지**하고, BI 구축 전에 수집·검증·보완 절차를 표준화한다.
>
> 관련 문서: [PROJECT_GUIDE.md](PROJECT_GUIDE.md), [DATA_DICTIONARY.md](DATA_DICTIONARY.md)

---

## 1. 원칙

1. **수집 주기와 검증 주기를 분리한다.** 수집만 하고 검증하지 않으면 누락을 인지하지 못한다.
2. **월별 데이터는 "한 번 실패 = 영구 누락"이 될 수 있다.** 증분 수집기는 마지막 성공 월 이후만 조회하므로, 중간 월이 비어 있으면 별도 보완이 필요하다.
3. **공식 통계(KMTA)와 잠정 통계(식약처)의 우선순위를 명시한다.** 같은 월에 두 소스가 다르면 규칙 없이 덮어쓰면 안 된다.
4. **기본 일일 파이프라인(`--price-only`)은 미트박스만 갱신한다.** 재고·수입·USDA는 별도 스케줄이 없으면 자동으로 뒤처진다.

---

## 2. 데이터 소스 분류

| 등급 | 갱신 주기 | 대상 데이터 | 실행 방법 | 산출 파일 |
|------|-----------|-------------|-----------|-----------|
| **A. 일별** | 매 영업일 | 미트박스 B2B 도매가 | `run_daily_update.py` (기본) | `master_price_data.csv`, `dashboard_ready_data.csv` |
| **B. 일별 (외부)** | 매 영업일 | USDA 부위별·프라이멀, 환율 | `run_daily_update.py --full` 또는 개별 수집기 | `usda_beef_history.csv`, `usda_primal_history.csv`, `exchange_rate_data.xlsx` |
| **C. 월별** | 월 1회 이상 (재시도 포함) | KMTA 수입량, KMTA 재고 | `--full` 또는 월별 수집기 단독 실행 | `master_import_volume.csv`, `beef_stock_data.xlsx` |
| **C-보완** | 월별 공백 시 | 식약처 검역 실적 (수입량 잠정) | `crawl_imp_food_safety.py` | `master_import_volume.csv` (동일 파일 병합) |
| **D. 수동** | 필요 시 | 한국 도매가 수기, 숏플레이트 이력 | 엑셀/CSV 직접 입력 | `manual_kor_price.csv` 등 |

---

## 3. 권장 실행 스케줄

| 시점 | 실행 명령 | 포함 데이터 |
|------|-----------|-------------|
| **매일 (평일)** | `python src/run_daily_update.py` | 미트박스 가격 + 전처리 + **GAP 리포트** |
| **매주 1회 (월요일 권장)** | `python src/run_daily_update.py --full` | A + B + C 전체 + USDA 전처리 + GAP |
| **매월 10일·20일** | `python src/run_daily_update.py --monthly` | KMTA **수입만** + GAP + 수입 공백 시 식약처 보완 |
| **재고 포함 (선택)** | `python src/run_daily_update.py --monthly --with-stock` | 수입 + 재고 (재고는 시간 소요 큼) |
| **검증만** | `python src/run_daily_update.py --gap-check` | 수집 없이 GAP 리포트만 |
| **USDA만 긴급 갱신** | 개별 3종 + 전처리 2종 (아래 5절) | USDA·환율·원가 |

> Windows 작업 스케줄러: `run_daily_update.bat` = 일별, `run_daily_update.bat --full` = 주 1회, `run_daily_update.bat --monthly` = 매월 10·20일.

---

## 4. 월별 데이터 누락 방지 규칙

### 4.1 왜 누락이 발생하는가

| 원인 | 설명 |
|------|------|
| **실행 누락** | 기본 모드는 미트박스만 수집. `--full`을 주기적으로 돌리지 않으면 재고·수입이 멈춘다. |
| **협회 게시 지연** | KMTA 재고·수입은 통상 **익월 중순~하순**에 전월 데이터가 올라온다. 월초 1회만 돌리면 해당 월을 건너뛸 수 있다. |
| **미등록 응답** | 재고 수집기는 "등록된 자료가 없습니다"면 **건너뛰기만** 하고, 파일에는 추가하지 않는다. 다음 실행 때 같은 월을 재시도한다 (정상). |
| **수입 이중 소스** | 식약처로 5월을 채우면 마스터 최신월이 5월이 되어, KMTA 수집기는 6월부터만 조회한다. KMTA 5월 공식치로 **자동 교체되지 않는다.** |
| **실패 무시** | `--full`에서 월별·USDA 단계는 `critical=False`라 실패해도 파이프라인이 성공으로 끝날 수 있다. |

### 4.2 월별 데이터 "완료" 정의

| 데이터 | 완료로 인정하는 최신 월 | 비고 |
|--------|-------------------------|------|
| **재고** | **전월** (`YYYY-(M-1)`) | 당월은 협회 미등록이 일반적 |
| **수입 (KMTA)** | **전월** | 당월 말 전에는 없을 수 있음 |
| **수입 (식약처 잠정)** | **전월** | KMTA 미게시 시에만 사용 |
| **미트박스** | **당일 또는 전 영업일** | 일별 |
| **USDA** | **전 영업일** | 미국 휴장일 제외 |

예: 오늘이 2026-06-12이면 재고·수입은 **2026-05**까지 있어야 정상. 2026-04까지만 있으면 **1개월 누락**.

### 4.3 월별 수집 재시도 규칙

1. **매월 10일, 20일**에 파이프라인 월별 모드를 실행한다 (협회 업데이트 재시도).

```bash
python src/run_daily_update.py --monthly
```

- 기본: KMTA **수입량**만 수집 (재고 제외 — 소요 시간이 큼)
- 수입이 전월 기준 미달이면 **식약처 보완을 자동 시도** (`crawl_imp_food_safety.py`)
- 재고까지 필요할 때만: `--monthly --with-stock`

2. 실행 후 GAP 리포트가 파이프라인 **종료 시 자동 출력**된다.

### 4.4 수집 후 검증 (GAP 리포트)

`run_daily_update.py` 종료 시 자동으로 GAP 검증 리포트가 출력된다. 검증만 할 때:

```bash
python src/run_daily_update.py --gap-check
```

| 결과 | 조치 |
|------|------|
| `GAP` (수입) | `--monthly` 재실행 (식약처 자동 보완 포함) |
| `GAP` (재고) | `--monthly --with-stock` 또는 KMTA 사이트에서 해당 월 등록 여부 확인 |
| 연속 월 홀 (예: 02 있고 04만 있음) | **수동 백필**: 해당 월을 start로 지정해 수집기 재실행 |

### 4.5 수입량 소스 우선순위

| 순위 | 소스 | 용도 |
|------|------|------|
| 1 | **KMTA** (`crawl_imp_volume_monthly.py`) | 공식 월별 부위별 수입량 (확정치) |
| 2 | **식약처** (`crawl_imp_food_safety.py`) | KMTA 미게시 월의 **잠정치** |

**규칙**

- KMTA에 해당 월 데이터가 있으면 **KMTA를 정본**으로 한다.
- 식약처로 먼저 채운 월이라도, 이후 KMTA가 올라오면 **해당 월을 KMTA로 교체**해야 한다. (현재 코드는 자동 교체 안 됨 → 월별 수집 시 `std_date` 기준 덮어쓰기 로직 개선 필요)
- BI·레터에는 `data_source` 컬럼(향후 추가)으로 KMTA/MFDS 구분 표시 권장.

---

## 5. USDA 수집 규칙

### 5.1 실행 순서 (순서 고정)

```bash
python src/collectors/api_us_beef_collect_usda.py   # 1. 부위별 (증분)
python src/collectors/collect_usda_primal.py       # 2. 프라이멀 (연도별 전체)
python src/collectors/crawl_com_usd_krw.py         # 3. 환율 (증분)
python src/utils/process_usda_data.py              # 4. KRW 원가
python src/utils/preprocess_primal.py              # 5. Plate USD/kg
```

또는 `python src/run_daily_update.py --full` (위 1~5가 일별·전처리 블록에 포함).

### 5.2 완료 기준

| 파일 | 기준 |
|------|------|
| `usda_beef_history.csv` | `report_date` 최대값 = **전 영업일** |
| `usda_primal_history.csv` | 동일 |
| `exchange_rate_data.xlsx` | `Date` 최대값 = **오늘 또는 전일** |
| `processed_usda_cost.csv` | `Date` = beef와 동일 범위 |
| `usda_plate_usd_kg.csv` | primal 전처리 후 갱신 |

### 5.3 장기 미수집 시

- `api_us_beef_collect_usda.py`는 마지막 날짜 이후 영업일을 자동 백필 (6개월 단위 중간 저장).
- 공백이 6개월 이상이면 실행 시간·API 제한에 유의. [PROJECT_GUIDE.md 8절](PROJECT_GUIDE.md) 참고.
- `collect_usda_primal.py`는 실행마다 2019~현재 **전체 재수집** (시간 소요 큼).

---

## 6. 파이프라인 모드 정리

| 모드 | 명령 | 수집 범위 |
|------|------|-----------|
| 일별 (기본) | `run_daily_update.py` | 미트박스만 |
| 전체 | `run_daily_update.py --full` | 일별 4 + 월별 3 + USDA 전처리 + 미트박스 전처리 |
| 커밋 없음 | `--no-commit` | CI/검증용 |
| 원격 반영 | `--push` | 성공 시 git push |

**운영 권장**

- 평일: `--price-only` (또는 인자 없음)
- 주 1회: `--full`
- 월 2회: 월별 수집기 단독 + 4.4 검증

---

## 7. 장애 대응

| 증상 | 확인 | 조치 |
|------|------|------|
| 재고가 2~3개월 전에서 멈춤 | `beef_stock_data.xlsx` `기준년월` max | `crawl_imp_stock_monthly.py` 실행, KMTA 사이트에서 해당 월 등록 여부 확인 |
| 수입이 전월보다 뒤처짐 | `master_import_volume.csv` `std_date` max | KMTA → 식약처 순으로 보완 |
| USDA가 1주 이상 뒤처짐 | `usda_beef_history.csv` max date | 5.1 순서로 수집·전처리 |
| `--full` 성공인데 데이터 안 늘어남 | 로그에 `[FAIL]` 여부 | 실패 단계 개별 재실행 |
| pandas `read_html` 오류 | pandas 2.2+ | `StringIO(response.text)` 패턴 사용 (재고·수입 수집기 반영됨) |

---

## 8. BI 구축 전 선행 작업 (TODO)

USDA·재고·수입을 가격 대시보드와 같은 BI 형태로 보여주기 **전에** 아래를 권장한다.

1. [x] `run_daily_update.py` GAP 검증 (`--gap-check`, 종료 시 자동 리포트)
2. [ ] `master_import_volume.csv`에 `data_source` (KMTA / MFDS) 컬럼 추가
3. [ ] KMTA 확정치가 올라온 월에 식약처 잠정치 **자동 교체** 로직
4. [ ] `run_daily_update.py`에 `--monthly` / `--usda` 분리 옵션 (리소스 절약)
5. [x] Streamlit `05_USDA_Analysis.py` — USDA Plate 시세, 다소스 통합 비교, `part_crosswalk.csv`

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-12 | 초안 작성 (월별 누락 원인·스케줄·검증·USDA 규칙 정리) |
