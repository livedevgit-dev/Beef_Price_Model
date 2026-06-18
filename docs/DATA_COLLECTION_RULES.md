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
| **A-한우** | 매 영업일 | EKAPE 한우 경락+두수 / KAMIS 한우 도/소매 | `run_daily_update.py` (기본) | `han_auction_raw.csv`, `kamis_hanwoo_raw.csv`, `hanwoo_dashboard_ready.csv` |
| **B. 일별 (외부)** | 매 영업일 | USDA 부위별·프라이멀, 환율 | `run_daily_update.py --full` 또는 개별 수집기 | `usda_beef_history.csv`, `usda_primal_history.csv`, `exchange_rate_data.xlsx` |
| **B-거시** | 일/월 (외부) | FRED(옥수수·WTI·Food PPI), ECOS(기준금리·CPI·PPI) | `run_daily_update.py --full` 또는 개별 수집기 (키 없으면 skip) | `macro_indicators_raw.csv`, `macro_indicators_daily.csv`, `macro_dashboard_ready.csv` |
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
| **한우 경락 (EKAPE)** | **전 영업일** | 도매시장 휴장일 제외 (주말·공휴일) |

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

## 4-한우. 한우 수집 규칙 (Phase 1)

### 4-한우.1 데이터 소스

| 소스 | 엔드포인트 | 수집 단위 | 비고 |
|------|------------|----------|------|
| **EKAPE (필수)** | `data.ekape.or.kr/openapi-data/service/user/grade/auct/cattle` | 일별 × 등급(`qgradeYn=Y`: 1++/1+/1/2/3/등외) × 도축장 | `결함포함가격` 기준. 가격(원/kg, 도체)과 도축장별 경매두수를 동시에 반환 |
| **KAMIS (선택)** | `kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList&p_item_category_code=500` | 일별 × 부위(안심/등심/갈비/양지/설도 등) × 등급 × 도매/소매 | 단위 `100g` 등 → 전처리에서 원/kg로 환산. 키 미설정 시 자동 skip |

### 4-한우.2 실행 순서 (`run_daily_update.py` 기본 모드에 포함)

```
crawl_han_auction_api → collect_kamis_hanwoo → preprocess_hanwoo
```

- EKAPE는 증분(`auction_end_ymd` 기준), KAMIS는 증분(`reg_date` 기준)
- EKAPE 실패해도 미트박스 결과는 보존 (`critical=False`)

### 4-한우.3 완료 기준

| 파일 | 기준 |
|------|------|
| `0_raw/han_auction_raw.csv` | `auction_end_ymd` 최대값 ≥ 오늘 - 5일 (영업일 보정) |
| `0_raw/kamis_hanwoo_raw.csv` | `reg_date` 최대값 ≥ 오늘 - 5일 (키 설정 시) |
| `2_dashboard/hanwoo_dashboard_ready.csv` | 위 두 파일 갱신 후 자동 재생성 |

### 4-한우.4 장기 미수집 시

- EKAPE 수집기는 마지막 `auction_end_ymd` 이후를 30일 단위 청크로 자동 백필
- KAMIS 수집기는 1회 실행당 최대 400일 백필 (`MAX_DAYS_PER_RUN`). 그 이상 공백이면 N회 반복 실행
- API 트래픽 한도(EKAPE 1,000/일, KAMIS 10,000/일 개발계정) 내에서 충분히 작동

### 4-한우.5 KAMIS 키 신청

1. KAMIS [Open-API 이용안내](https://www.kamis.or.kr/customer/reference/openapi_list.do) 가입·신청
2. 발급된 인증키/아이디를 `.env`의 `KAMIS_CERT_KEY` / `KAMIS_CERT_ID`에 입력
   - `KAMIS_CERT_ID`는 별도 발급이 아니라 **KAMIS 가입 계정 아이디**. 둘 다 필수
3. 다음 파이프라인 실행부터 자동 수집

### 4-한우.6 KAMIS 응답 구조·데이터 특성 (검증 2026-06)

- 실제 응답: 부위는 `kind_name`(안심/등심/갈비/설도/양지), **등급은 별도 `rank` 필드**(`1++등급` 등), 단위 `100g`(→ ×10으로 원/kg 환산), `dpr1`이 당일가.
- **과거 일자는 `dpr1=0`(미제공)이 대부분** — KAMIS 일별 API는 최근/당일가에 적합하고, 과거 일별 백필은 데이터가 희소함. 과거 시계열 깊이가 필요하면 기간/월별 API로 별도 보강 권장.
- 사내망 SSL 검사 대응으로 수집기는 `verify=False` 사용(USDA/Macro 수집기와 동일).
- 상세: [KAMIS_HANDOFF.md](KAMIS_HANDOFF.md)

---

## 4-거시. 거시경제 지표 (Macro) 수집 규칙

> 금리·물가(CPI)·PPI·옥수수·WTI 등 가격 예측 ML 의 외생변수. **환율(USD/KRW)은 `exchange_rate_data.xlsx` 에 이미 있으므로 macro 에서 중복 수집하지 않는다.**

### 4-거시.1 데이터 소스 / 지표 (Tier 1)

| indicator_id | 소스 | series/통계표 | 주기 | 단위 | 검증 |
|--------------|------|---------------|------|------|------|
| `us_corn` | FRED | `PMAIZMTUSDM` (Global price of Corn, 사료비 proxy) | 월 | USD/MT | ✅ 공식 |
| `us_soybean` | FRED | `PSOYBUSDM` (Global price of Soybeans, 사료비) | 월 | USD/MT | ✅ 공식 |
| `us_soybean_meal` | FRED | `PSMEAUSDM` (Soybean Meal 대두박, 사료 직접 투입재) | 월 | USD/MT | ✅ 공식 |
| `us_wti` | FRED | `DCOILWTICO` (WTI, Cushing) | 일 | USD/bbl | ✅ 공식 |
| `us_food_ppi` | FRED | `WPU02` (PPI Processed Foods and Feeds) | 월 | Index 1982=100 | ✅ 공식 |
| `kr_base_rate` | ECOS | `722Y001` / `0101000` (한국은행 기준금리) | 월 | 연% | ✅ 검증 (실제 금리 이력 일치) |
| `kr_cpi_food` | ECOS | `901Y009` / `A` (식료품 및 비주류음료) | 월 | 2020=100 | ✅ 검증 |
| `kr_cpi_total` | ECOS | `901Y009` / `0` (소비자물가 총지수) | 월 | 2020=100 | ✅ 검증 |
| `kr_ppi_food` | ECOS | `404Y014` / `301AA` (음식료품) | 월 | 2020=100 | ✅ 검증 |
| `kr_ccsi` | ECOS | `511Y002` / `FME` (소비자심리지수) | 월 | p(=100기준) | ✅ 검증 |
| `kr_esi` | ECOS | `513Y001` / `E1000` (경제심리지수) | 월 | p | ✅ 검증 |
| `kr_temp_avg` | KMA | ASOS 일자료 `avgTa` (전국대표 평균기온) | 일 | °C | ✅ 공식 |
| `kr_temp_max` | KMA | ASOS 일자료 `maxTa` (전국대표 최고기온) | 일 | °C | ✅ 공식 |
| `kr_precip` | KMA | ASOS 일자료 `sumRn` (전국대표 강수량) | 일 | mm | ✅ 공식 |

> **항목코드(`ITEM_CODE`) 검증 완료(2025-06)** — ECOS `StatisticItemList` API 로 확인. `collect_macro_ecos.py` 의 `ECOS_INDICATORS` 참조. 대체 후보: CPI 식료품만 `901Y009/A01`, PPI 식료품만 `404Y014/3011AA`, PPI 농림수산품 `404Y014/101AA`. 코드가 틀리면 ECOS 가 `INFO-200`(무자료)을 반환하고 **해당 indicator 만 skip**, 파이프라인은 계속된다.

### 4-거시.2 산출물 (long → daily → dashboard)

| 단계 | 파일 | 스키마 |
|------|------|--------|
| Raw | `0_raw/macro_indicators_raw.csv` | `date, country, indicator_id, indicator_name, value, unit, freq, source` (FRED+ECOS 공유) |
| Processed | `1_processed/macro_indicators_daily.csv` | 위 + `ma30, yoy_pct, mom_pct` (일별 ffill) |
| Dashboard | `2_dashboard/macro_dashboard_ready.csv` | wide: `date` × 지표값 + `<id>_yoy_pct` — 가격 데이터와 `date` 기준 merge |

- `country`: `US` / `KR`, `source`: `FRED` / `ECOS`
- **월별 지표의 `date` 는 해당 월 1일(`YYYY-MM-01`)로 통일** (FRED 월별 규약과 정합). 일별(WTI)은 관측일 그대로.
- **히스토리 시작: 2019-01-01** (다른 데이터셋과 정합). 1회 실행 청크 제한 없음 — FRED/ECOS 모두 기간 범위 단일 호출.
- 증분: indicator_id 별 raw `max(date)` 이후만. dedup 키 `(date, country, indicator_id)`.
- ffill 정책: 금리·물가는 다음 발표 전까지 값이 유지되므로 일별 ffill 에 **limit 없음** (가격 ffill 의 limit=7 과 다름).

### 4-거시.3 실행 / 완료 기준

```bash
python src/collectors/collect_macro_fred.py    # FRED (키 없으면 skip)
python src/collectors/collect_macro_ecos.py    # ECOS (키 없으면 skip)
python src/utils/preprocess_macro.py           # raw → daily + dashboard
```

또는 `python src/run_daily_update.py --full` 의 `[2-1] Macro 수집` / `[5-1] Macro 전처리` 블록에 포함(`critical=False` — 실패해도 기존 파이프라인 중단 없음). GAP 리포트에 `거시지표(Macro)` 항목이 출력되며, 키 미설정 시 `SKIP(info)`, 월 지표 발표 지연 감안 40일 lag 까지 `OK`.

### 4-거시.4 API 키 신청

| 키 | 신청 |
|----|------|
| `FRED_API_KEY` | https://fredaccount.stlouisfed.org/apikeys |
| `ECOS_API_KEY` | https://ecos.bok.or.kr/api/ |
| `KMA_API_KEY` | 공공데이터포털 'ASOS 일자료 조회서비스' 활용신청 — https://www.data.go.kr/data/15059093/openapi.do (**Decoding 인증키** 사용) |

`.env` 에 입력하면 다음 실행부터 자동 수집. 비워 두면 각 수집기가 graceful skip.
기후(KMA) 지표는 전국 대표 관측소(서울·부산·대구·광주·대전) 일자료의 날짜별 평균이며, 산출물은 동일한 long format raw/processed/dashboard 에 합쳐진다.

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
| 2026-06-16 | 거시경제 지표(Macro) 수집 규칙 추가 — FRED/ECOS Tier-1 6종, long→daily→dashboard 파이프라인, GAP 항목 |
