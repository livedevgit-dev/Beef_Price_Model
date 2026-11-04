# DATA DICTIONARY — Beef Price Model

> **최종 갱신일**: 2026-03-25
> **목적**: 프로젝트 내 모든 데이터 파일의 위치·구조·수집 주기를 한눈에 파악하기 위한 기준 문서
> **경로 기준**: `src/config.py`에 정의된 변수 및 `data/` 폴더 내 실제 파일

---

## 1. 원시 데이터 (`data/0_raw/`)

| 카테고리 | 데이터명(한글) | 데이터명(영어) | 파일명 및 config 변수 | 수집 주기 | 기준 날짜 포맷 | 주요 포함 항목(컬럼명 요약) |
|---------|--------------|--------------|---------------------|----------|-------------|------------------------|
| 환율 | 원/달러 환율 | USD-KRW Exchange Rate | `exchange_rate_data.xlsx` / `EXCHANGE_RATE_XLSX` | 일별 | `YYYY-MM-DD` (예: `2020-01-02`) | `Date`, `Close` |
| 수입물량 | 부위별 수입물량 마스터 | Master Import Volume | `master_import_volume.csv` / `MASTER_IMPORT_VOLUME_CSV` | 월별 | `YYYY-MM` (예: `2026-01`) | `std_date`, `구분`, `부위별_갈비_합계`, `부위별_등심_합계`, `부위별_목심_합계`, `부위별_사태_합계`, `부위별_설도_합계`, `부위별_안심_합계`, `부위별_앞다리_합계`, `부위별_양지_합계`, `부위별_우둔_합계`, `부위별_채끝_합계`, `부위별_기타_합계`, `부위별_계_합계` |
| 수입물량 | 식품안전정보원 수입 신고 데이터 | Food Safety Import Data | `raw_food_safety_data.csv` | 월별 | `YYYY-MM` (예: `2026-01`) | `std_ym`, `품명`, `구분`, `부위`, `국가`, `전년도_누계`, `전년도_12월_누계`, `당월_상순`, `당월_중순`, `당월_하순`, `당월_소계`, `당해년도_누계` |
| 수입물량 | 미국산 소고기 수입량 (2019~2024) | US Beef Import Total (2019–2024) | `미국산소고기_2019_2024_Total.csv` | 연 1회 (이력) | `YYYY-MM` (예: `2019-01`) | `년월`, `부위`, `중량` |
| 수입물량 | 미국산 소고기 수입량 (최근 12개월) | US Beef Import Recent 12M | `미국산소고기_202412_202511.csv` | 월별 (갱신) | `YYYY-MM` (예: `2025-01`) | `년월`, `부위`, `중량` |
| 수입물량 | 미국산 소고기 부위별 일일 수입 | US Beef Parts Import Daily | `us_beef_parts_import_daily.csv` | 일별 | *(날짜 컬럼 없음 — 집계 스냅샷)* | `col_0`~`col_10` (품명, 구분, 부위, 국가, 전년도누계, 전년도12월누계, 당월상순, 당월중순, 당월하순, 당월소계, 당해년도누계) |
| 재고 | 소고기 부위별 재고 | Beef Stock Data | `beef_stock_data.xlsx` / `BEEF_STOCK_XLSX` | 월별 | `YYYY-MM` (예: `2019-01`) | `기준년월`, `부위별 부위별`, `조사재고량 조사재고량`, `대비(%) 전월`, `대비(%) 전년` |
| 미국 도매가 | USDA 소고기 부위별 시세 히스토리 | USDA Beef History | `usda_beef_history.csv` / `USDA_BEEF_HISTORY_CSV` | 일별 (USDA LM_XB403) | `MM/DD/YYYY` (예: `02/19/2026`) | `report_date`, `item_description`, `number_trades`, `total_pounds`, `price_range_low`, `price_range_high`, `weighted_average`, `grade`, `trim_description` 외 메타데이터 |
| 미국 도매가 | USDA 프라이멀 부위별 시세 히스토리 | USDA Primal History | `usda_primal_history.csv` / `USDA_PRIMAL_HISTORY_CSV` | 일별 (USDA LM_XB403) | `MM/DD/YYYY` (예: `12/31/2019`) | `report_date`, `primal_desc`, `choice_600_900`, `select_600_900` 외 메타데이터 |
| 미국 도매가 | USDA 원시 보고서 스냅샷 | USDA Raw Snapshot | `usda_raw_20260212.csv` | 비정기 (스냅샷) | `MM/DD/YYYY` (예: `02/12/2026`) | `report_date`, `is_correction`, `narrative`, `trend`, `report_title` 외 메타데이터 |
| 한국 도매가 | 한국 도매가 (수동 입력) | Manual Korean Wholesale Price | `manual_kor_price.csv` / `MANUAL_KOR_PRICE_CSV` | 월별 (수동) | `Mon-YY` (예: `Jan-18`) | `날짜`, `갈비_냉동_미국산`, `갈비_냉동_호주산`, `갈비살_냉장_`, `갈비살_냉장_호주산`, `척아이롤_냉장_미국산`, `척아이롤_냉장_호주산`, `척아이롤_냉동_미국산`, `척아이롤_냉동_호주산`, `양지_냉장_미국산`, `양지_냉장_호주산` |
| 한국 도매가 | 숏플레이트 도매가 이력 | Short Plate Wholesale Price | `beef_Short Plate_wholesale_price.xlsx` / `SHORT_PLATE_WHOLESALE_XLSX` | 비정기 (수동) | `YYYY-MM-DD` (예: `2016-12-22`, 일부 `YYYY/MM/DD` 혼재) | `월/일`, `구분`, `단가` |
| 크롤링 | 미트박스 B2B 도매시세 크롤링 | Meatbox B2B Crawling | `raw_meatbox_20260126.csv` | 수시 (크롤링) | *(날짜 컬럼 없음 — 파일명에 일자 `YYYYMMDD` 포함)* | `품목명`, `보관`, `도매시세_raw`, `원산지`, `도매시세` |
| 크롤링 | 미트미플 카페 B2B 크롤링 | Cafe B2B Crawling | `raw_cafe_b2b_crawling.csv` / `RAW_CAFE_CRAWLING_CSV` | 수시 (크롤링) | *(현재 파일 미존재 — config에만 정의됨)* | *(현재 파일 미존재 — config에만 정의됨)* |
| 기타 | 크롤링 디버그 페이지 소스 | Debug Page Source | `debug_page_source.html` | — | — | *(HTML 디버그 파일, 분석 데이터 아님)* |

---

## 2. 가공 데이터 (`data/1_processed/`)

| 카테고리 | 데이터명(한글) | 데이터명(영어) | 파일명 및 config 변수 | 수집 주기 | 기준 날짜 포맷 | 주요 포함 항목(컬럼명 요약) |
|---------|--------------|--------------|---------------------|----------|-------------|------------------------|
| 통합 가격 | 통합 가격 마스터 | Master Price Data | `master_price_data.csv` / `MASTER_PRICE_CSV` | 파이프라인 실행 시 갱신 | `YYYY-MM-DD` (예: `2025-01-22`) | `date`, `part_name`, `country`, `wholesale_price`, `brand` |
| 통합 가격 | 통합 가격 마스터 (백업) | Master Price Data Backup | `master_price_data_backup_full.csv` | 파이프라인 실행 시 갱신 | `YYYY-MM-DD` (예: `2025-01-22`) | `date`, `part_name`, `country`, `wholesale_price`, `brand` |
| 통합 가격 | 정제된 가격 데이터 | Clean Price Data | `clean_price_data.csv` | 파이프라인 실행 시 갱신 | `YYYY-MM-DD` (예: `2025-12-22`) | `date`, `part_name`, `country`, `brand`, `wholesale_price` |
| 미국 원가 | USDA 원가 분석 (환율 반영) | Processed USDA Cost | `processed_usda_cost.csv` / `PROCESSED_USDA_COST_CSV` | 파이프라인 실행 시 갱신 | `Date`: `YYYY-MM-DD` (예: `2019-01-02`), `report_date`: `MM/DD/YYYY` | `Date`, `Exchange_Rate`, `report_date`, `item_description`, `number_trades`, `total_pounds`, `price_range_low/high`, `weighted_average`, `grade`, `total_volume_kg`, `price_range_low_USD_kg`, `price_range_high_USD_kg`, `weighted_average_USD_kg` 외 메타데이터 |
| 미국 원가 | USDA Plate 부위 USD/kg 시세 | USDA Plate USD/kg | `usda_plate_usd_kg.csv` / `USDA_PLATE_USD_KG_CSV` | 파이프라인 실행 시 갱신 | `YYYY-MM-DD` (예: `2019-01-02`) | `report_date`, `primal_desc`, `choice_usd_per_kg`, `select_usd_per_kg` |
| 참조 | USDA 코드 → 한글명 매핑 검증 결과 | Validation Mapping Result | `validation_mapping_result.csv` | 매핑 규칙 변경 시 | *(날짜 컬럼 없음)* | `USDA_Code`, `Korean_Name`, `Status`, `Original_Description`, `Note` |
| 시각화 | 리브 계절성 분석 차트 | Rib Seasonality Chart | `rib_seasonality_advanced.png` | 분석 실행 시 | — | *(PNG 이미지 파일)* |

---

## 3. 대시보드 데이터 (`data/2_dashboard/`)

| 카테고리 | 데이터명(한글) | 데이터명(영어) | 파일명 및 config 변수 | 수집 주기 | 기준 날짜 포맷 | 주요 포함 항목(컬럼명 요약) |
|---------|--------------|--------------|---------------------|----------|-------------|------------------------|
| 대시보드 | 대시보드 표출용 최종 데이터 | Dashboard Ready Data | `dashboard_ready_data.csv` / `DASHBOARD_READY_CSV` | 파이프라인 실행 시 갱신 | `YYYY-MM-DD` (예: `2025-01-22`) | `date`, `category`, `part`, `brand`, `wholesale_price`, `ma7`, `ma30`, `min_total`, `max_total` |

---

## 4. `src/config.py` 변수 ↔ 파일 매핑 요약

| config 변수명 | 파일 경로 | 존재 여부 |
|-------------|----------|----------|
| `MASTER_PRICE_CSV` | `data/1_processed/master_price_data.csv` | O |
| `DASHBOARD_READY_CSV` | `data/2_dashboard/dashboard_ready_data.csv` | O |
| `MASTER_IMPORT_VOLUME_CSV` | `data/0_raw/master_import_volume.csv` | O |
| `BEEF_STOCK_XLSX` | `data/0_raw/beef_stock_data.xlsx` | O |
| `EXCHANGE_RATE_XLSX` | `data/0_raw/exchange_rate_data.xlsx` | O |
| `USDA_BEEF_HISTORY_CSV` | `data/0_raw/usda_beef_history.csv` | O |
| `USDA_PRIMAL_HISTORY_CSV` | `data/0_raw/usda_primal_history.csv` | O |
| `PROCESSED_USDA_COST_CSV` | `data/1_processed/processed_usda_cost.csv` | O |
| `USDA_PLATE_USD_KG_CSV` | `data/1_processed/usda_plate_usd_kg.csv` | O |
| `MANUAL_KOR_PRICE_CSV` | `data/0_raw/manual_kor_price.csv` | O |
| `SHORT_PLATE_WHOLESALE_XLSX` | `data/0_raw/beef_Short Plate_wholesale_price.xlsx` | O |
| `RAW_CAFE_CRAWLING_CSV` | `data/0_raw/raw_cafe_b2b_crawling.csv` | **X (미존재)** |

---

## 5. 데이터 흐름 요약

```
[외부 소스]                     [0_raw]                    [1_processed]              [2_dashboard]
───────────────────────────────────────────────────────────────────────────────────────────────────
USDA LM_XB403 API         → usda_beef_history.csv    → processed_usda_cost.csv
                          → usda_primal_history.csv  → usda_plate_usd_kg.csv
식품안전정보원              → raw_food_safety_data.csv → master_import_volume.csv
관세청/수입통계             → 미국산소고기_*.csv
Yahoo Finance / 한국은행   → exchange_rate_data.xlsx
축산물품질평가원/수동       → beef_stock_data.xlsx
한국 도매시장/수동          → manual_kor_price.csv
                          → beef_Short Plate_*.xlsx
미트박스 크롤링             → raw_meatbox_*.csv       → clean_price_data.csv
                                                     → master_price_data.csv     → dashboard_ready_data.csv
```

---

## 6. 날짜 포맷 변환 시 주의사항

| 원본 포맷 | 해당 파일 | 병합 시 권장 변환 |
|----------|----------|-----------------|
| `MM/DD/YYYY` | `usda_beef_history.csv`, `usda_primal_history.csv`, `usda_raw_*.csv`, `processed_usda_cost.csv`(report_date) | `pd.to_datetime(col, format='%m/%d/%Y')` |
| `Mon-YY` | `manual_kor_price.csv` | `pd.to_datetime(col, format='%b-%y')` |
| `YYYY-MM` | `master_import_volume.csv`, `raw_food_safety_data.csv`, `beef_stock_data.xlsx`, `미국산소고기_*.csv` | `pd.to_datetime(col + '-01')` 또는 `Period` 사용 |
| `YYYY-MM-DD` | 나머지 대부분 (processed·dashboard 계열) | 별도 변환 불필요 (표준 ISO 8601) |
| `YYYY-MM-DD` 혼재 | `beef_Short Plate_wholesale_price.xlsx` | `pd.to_datetime(col)` — datetime/문자열 혼재 주의 |

---

## 7. 참고 사항

- **config에만 정의되고 파일이 없는 항목**: `RAW_CAFE_CRAWLING_CSV` (`raw_cafe_b2b_crawling.csv`) — 미트미플 크롤링 모듈이 실행되면 생성될 예정
- **비데이터 파일**: `debug_page_source.html`은 크롤러 디버그 목적이므로 분석 파이프라인에 포함되지 않음
- **인코딩**: 대부분 UTF-8. Excel(`.xlsx`) 파일은 openpyxl 기반 읽기 권장
- **이 문서의 갱신**: 데이터 스키마가 변경되거나 새 파일이 추가될 때 반드시 이 문서를 함께 업데이트할 것

---

<!-- AUTO-GENERATED-SCHEMA:START -->
<!-- 이 영역은 extract_data_schema.py가 자동으로 갱신합니다. 수동 편집하지 마세요. -->

## 부록: 자동생성 컬럼 스키마

> 마지막 갱신: 2026-11-04 09:36
> `python src/utils/extract_data_schema.py` 또는 `python src/run_daily_update.py` 파이프라인에서 자동 갱신

### 폴더: `0_raw/`

#### `beef_Short Plate_wholesale_price.xlsx`
- **총 행(Row) 수**: 약 361행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 상  품    원  장 | object | nan | 상품명: |
| Unnamed: 1 | object | nan | 미국산 |
| Unnamed: 2 | object | nan | nan |

#### `beef_stock_data.xlsx`
- **총 행(Row) 수**: 약 1196행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준년월 | object | 2019-01 | 2019-01 |
| 부위별 부위별 | object | 안심 | 등심 |
| 조사재고량 조사재고량 | int64 | 590 | 18617 |
| 대비(%) 전월 | int64 | 0 | 0 |
| 대비(%) 전년 | int64 | 0 | 0 |
| 비고 | float64 | nan | nan |

#### `exchange_rate_data.xlsx`
- **총 행(Row) 수**: 약 1930행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Date | object | 2019-01-02 | 2019-01-03 |
| Close | float64 | 1118.1 | 1119.0 |

#### `fas_export_sales_raw.csv`
- **총 행(Row) 수**: 약 816행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| week_ending | object | 2019-01-03T00:00:00 | 2019-01-03T00:00:00 |
| market_year | int64 | 2019 | 2019 |
| commodity_code | int64 | 1701 | 1701 |
| commodity_name | object | Fresh, Chilled, or Frozen Muscle Cuts of Beef | Fresh, Chilled, or Frozen Muscle Cuts of Beef |
| country_code | int64 | 5700 | 5800 |
| country_name | object | 중국 | 한국 |
| weekly_exports | int64 | 37 | 850 |
| outstanding_sales | int64 | 642 | 28680 |
| gross_new_sales | int64 | 412 | 11072 |
| current_my_net_sales | int64 | 408 | 10875 |
| current_my_total_commitment | int64 | 679 | 29530 |
| unit | int64 | 1 | 1 |

#### `han_auction_raw.csv`
- **총 행(Row) 수**: 약 372442행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| auction_start_ymd | int64 | 20190102 | 20190102 |
| auction_end_ymd | int64 | 20190102 | 20190102 |
| grade_type | object | QW | QW |
| grade_cd | int64 | 0 | 0 |
| grade_nm | object | 1++ | 1++ |
| breed_cd | float64 | nan | nan |
| breed_nm | object | 전체 | 전체 |
| sex_cd | float64 | nan | nan |
| sex_nm | object | 전체 | 전체 |
| qgrade_yn | object | Y | Y |
| defect_include_yn | object | Y | Y |
| market_code | int64 | 202 | 302 |
| market_name | object | 부경축공 | 협신식품 |
| is_regional_total | bool | False | False |
| is_national_total | bool | False | False |
| price_won_per_kg | int64 | 20902 | 21341 |
| head_count | int64 | 18 | 28 |

#### `kamis_hanwoo_raw.csv`
- **총 행(Row) 수**: 약 50051행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| reg_date | object | 2019-01-01 | 2019-01-01 |
| product_cls_code | int64 | 1 | 1 |
| product_cls_name | object | 소매 | 소매 |
| item_name | object | 소 | 소 |
| kind_name | object | 갈비 | 갈비 |
| rank | object | 1++등급 | 1+등급 |
| unit | object | 100g | 100g |
| country_name | float64 | nan | nan |
| market_name | float64 | nan | nan |
| price | float64 | nan | nan |

#### `kamis_pork_raw.csv`
- **총 행(Row) 수**: 약 14325행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| reg_date | object | 2019-01-01 | 2019-01-01 |
| product_cls_code | int64 | 1 | 1 |
| product_cls_name | object | 소매 | 소매 |
| item_name | object | 돼지 | 돼지 |
| kind_name | object | 갈비 | 목심 |
| rank | object | 갈비 | 목심 |
| unit | object | 100g | 100g |
| country_name | float64 | nan | nan |
| market_name | float64 | nan | nan |
| price | float64 | nan | nan |

#### `macro_indicators_raw.csv`
- **총 행(Row) 수**: 약 18912행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-01 |
| country | object | AU | KR |
| indicator_id | object | au_beef_price | kr_base_rate |
| indicator_name | object | IMF Global Price of Beef (호주·NZ 냉동 정육 CIF 미국) | 한국은행 기준금리 |
| value | float64 | 185.9565217391304 | 1.75 |
| unit | object | US cents/lb | 연% |
| freq | object | M | M |
| source | object | FRED | ECOS |

#### `manual_kor_price.csv`
- **총 행(Row) 수**: 약 97행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 날짜 | object | Jan-18 | Feb-18 |
| 갈비_냉동_미국산 | int64 | 2407 | 2445 |
| 갈비_냉동_호주산 | int64 | 1972 | 1961 |
| 갈비살_냉장_ | int64 | 2642 | 2332 |
| 갈비살_냉장_호주산 | float64 | nan | nan |
| 척아이롤_냉장_미국산 | float64 | nan | nan |
| 척아이롤_냉장_호주산 | float64 | nan | nan |
| 척아이롤_냉동_미국산 | float64 | nan | nan |
| 척아이롤_냉동_호주산 | float64 | nan | nan |
| 양지_냉장_미국산 | float64 | nan | nan |
| 양지_냉장_호주산 | float64 | nan | nan |

#### `master_import_volume.csv`
- **총 행(Row) 수**: 약 188행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| std_date | object | 2026-10 | 2026-10 |
| 구분 | object | 미국 | 호주 |
| 부위별_갈비_합계 | float64 | 6303.4 | 3384.6 |
| 부위별_등심_합계 | float64 | 198.3 | 2100.4 |
| 부위별_목심_합계 | float64 | 717.1 | 599.6 |
| 부위별_사태_합계 | float64 | 94.1 | 37.4 |
| 부위별_설도_합계 | float64 | 135.7 | 1244.5 |
| 부위별_안심_합계 | float64 | 23.2 | 3.8 |
| 부위별_앞다리_합계 | float64 | 1655.2 | 2658.7 |
| 부위별_양지_합계 | float64 | 4408.0 | 2454.0 |
| 부위별_우둔_합계 | float64 | 45.4 | 1155.6 |
| 부위별_채끝_합계 | float64 | 0.0 | 85.2 |
| 부위별_기타_합계 | float64 | 0.1 | 595.4 |
| 부위별_계_합계 | float64 | 13580.5 | 14319.2 |
| data_source | object | MFDS | MFDS |

#### `us_cattle_on_feed.csv`
- **총 행(Row) 수**: 약 280행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-01 |
| short_desc | object | CATTLE, ON FEED - INVENTORY | CATTLE, ON FEED - PLACEMENTS, MEASURED IN HEAD |
| value | float64 | 11680000.0 | 1964000.0 |
| unit | object | HEAD | HEAD |
| reference_period | object | FIRST OF JAN | JAN |
| domaincat | object | CAPACITY: (1,000 OR MORE HEAD) | CAPACITY: (1,000 OR MORE HEAD) |

#### `usda_beef_history.csv`
- **총 행(Row) 수**: 약 172172행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 10/29/2026 | 10/29/2026 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| item_description | object | Brisket, deckle-off, bnls (120  1) | Brisket, point/off, bnls (120A  3) |
| number_trades | int64 | 24 | 5 |
| total_pounds | object | 203,836 | 2,519 |
| price_range_low | float64 | 378.0 | 619.0 |
| price_range_high | float64 | 458.0 | 735.0 |
| weighted_average | float64 | 391.22 | 650.43 |
| report_title | object | National Daily Boxed Beef Cutout & Boxed Beef Cuts - Negotiated Sales - PM (PDF) (LM_XB403) | National Daily Boxed Beef Cutout & Boxed Beef Cuts - Negotiated Sales - PM (PDF) (LM_XB403) |
| slug_name | object | AMS_2453 | AMS_2453 |
| slug_id | int64 | 2453 | 2453 |
| office_name | object | Des Moines, IA | Des Moines, IA |
| office_code | object | LS-NW | LS-NW |
| office_city | object | Des Moines | Des Moines |
| office_state | object | IA | IA |
| market_location_name | object | Des Moines, IA | Des Moines, IA |
| market_location_city | object | Des Moines | Des Moines |
| market_location_state | object | IA | IA |
| market_type | object | Direct Livestock - LMR Beef | Direct Livestock - LMR Beef |
| market_type_category | object | Direct Livestock - LMR Beef | Direct Livestock - LMR Beef |
| published_date | object | 10/29/2026 14:43:53 | 10/29/2026 14:43:53 |
| grade | object | Choice | Choice |
| trim_description | float64 | nan | nan |

#### `usda_primal_history.csv`
- **총 행(Row) 수**: 약 14014행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 01/02/2019 | 01/02/2019 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| primal_desc | object | Primal Brisket | Primal Chuck |
| choice_600_900 | float64 | 199.59 | 180.93 |
| select_600_900 | float64 | 193.57 | 179.1 |
| report_title | object | National Daily Boxed Beef Cutout & Boxed Beef Cuts - Negotiated Sales - PM (PDF) (LM_XB403) | National Daily Boxed Beef Cutout & Boxed Beef Cuts - Negotiated Sales - PM (PDF) (LM_XB403) |
| slug_name | object | AMS_2453 | AMS_2453 |
| slug_id | int64 | 2453 | 2453 |
| office_name | object | Des Moines, IA | Des Moines, IA |
| office_code | object | LS-NW | LS-NW |
| office_city | object | Des Moines | Des Moines |
| office_state | object | IA | IA |
| market_location_name | object | Des Moines, IA | Des Moines, IA |
| market_location_city | object | Des Moines | Des Moines |
| market_location_state | object | IA | IA |
| market_type | object | Direct Livestock - LMR Beef | Direct Livestock - LMR Beef |
| market_type_category | object | Direct Livestock - LMR Beef | Direct Livestock - LMR Beef |
| published_date | object | 01/02/2019 14:59:12 | 01/02/2019 14:59:12 |

#### `삼겹양지 유통가격 추이 1.xlsx`
- **총 행(Row) 수**: 약 361행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 상  품    원  장 | object | nan | 상품명: |
| Unnamed: 1 | object | nan | 미국산 |
| Unnamed: 2 | object | nan | nan |

### 폴더: `1_processed/`

#### `han_auction_daily.csv`
- **총 행(Row) 수**: 약 372442행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-02 | 2019-01-02 |
| auction_start_date | object | 2019-01-02 | 2019-01-02 |
| period_days | int64 | 1 | 1 |
| source | object | ekape_auction | ekape_auction |
| grade | object | 1++ | 1++ |
| sex | object | 전체 | 전체 |
| market_code | int64 | 202 | 302 |
| market_name | object | 부경축공 | 협신식품 |
| is_national_total | bool | False | False |
| is_regional_total | bool | False | False |
| price_won_per_kg | int64 | 20902 | 21341 |
| head_count | int64 | 18 | 28 |

#### `macro_indicators_daily.csv`
- **총 행(Row) 수**: 약 105701행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-02 |
| country | object | AU | AU |
| indicator_id | object | au_beef_price | au_beef_price |
| indicator_name | object | IMF Global Price of Beef (호주·NZ 냉동 정육 CIF 미국) | IMF Global Price of Beef (호주·NZ 냉동 정육 CIF 미국) |
| value | float64 | 185.9565 | 185.9565 |
| unit | object | US cents/lb | US cents/lb |
| freq | object | M | M |
| source | object | FRED | FRED |
| ma30 | float64 | nan | nan |
| yoy_pct | float64 | nan | nan |
| mom_pct | float64 | nan | nan |

#### `master_price_data.csv`
- **총 행(Row) 수**: 약 70577행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-22 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 오마하(960A) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10390.0 |
| brand | object | - | - |
| grade | float64 | nan | nan |

#### `ml_features_rib.csv`
- **총 행(Row) 수**: 약 80행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 2020-01-01 | 2020-02-01 |
| kr_price | float64 | 2514.0 | 2517.0 |
| us_price | float64 | 12.96344375 | 12.578357228915664 |
| exchange_rate | float64 | 1164.275 | 1193.79 |
| import_vol | float64 | 9194.0 | 9289.0 |
| stock | float64 | 49700.0 | 52824.0 |
| import_vol_mom | float64 | -0.0959685349065879 | 0.0103328257559278 |
| import_vol_yoy | float64 | -0.015842432027403 | 0.1314250913520096 |
| stock_mom | float64 | -0.0880901267866645 | 0.0628571428571429 |
| stock_yoy | float64 | 0.1535337124289195 | 0.2269243275886097 |
| stock_ma_3 | float64 | 53337.66666666666 | 52341.66666666666 |
| margin_spread | float64 | -12579.01347203125 | -12498.91707630723 |
| us_price_lag_1 | float64 | 14.090734117647058 | 12.96344375 |
| exchange_rate_lag_1 | float64 | 1175.8428571428572 | 1164.275 |
| us_price_lag_2 | float64 | 14.31930548780488 | 14.090734117647058 |
| exchange_rate_lag_2 | float64 | 1167.452380952381 | 1175.8428571428572 |
| us_price_lag_3 | float64 | 13.256560512820514 | 14.31930548780488 |
| exchange_rate_lag_3 | float64 | 1184.1333333333332 | 1167.452380952381 |
| kr_price_lead_1 | float64 | 2517.0 | 2517.0 |
| kr_price_lead_2 | float64 | 2517.0 | 2411.0 |
| kr_price_diff_lead_1 | float64 | 3.0 | 0.0 |
| kr_price_diff_lead_2 | float64 | 3.0 | -106.0 |

#### `ml_features_rolling_rib.csv`
- **총 행(Row) 수**: 약 76행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 2020-01-01 | 2020-02-01 |
| kr_price | float64 | 2514.0 | 2517.0 |
| us_price | float64 | 12.96344375 | 12.578357228915664 |
| exchange_rate | float64 | 1164.275 | 1193.79 |
| import_vol | float64 | 9194.0 | 9289.0 |
| stock | float64 | 49700.0 | 52824.0 |
| import_vol_mom | float64 | -0.0959685349065879 | 0.0103328257559278 |
| import_vol_yoy | float64 | -0.015842432027403 | 0.1314250913520096 |
| stock_mom | float64 | -0.0880901267866645 | 0.0628571428571429 |
| stock_yoy | float64 | 0.1535337124289195 | 0.2269243275886097 |
| stock_ma_3 | float64 | 53337.66666666666 | 52341.66666666666 |
| margin_spread | float64 | -12579.01347203125 | -12498.91707630723 |
| us_price_lag_1 | float64 | 14.090734117647058 | 12.96344375 |
| exchange_rate_lag_1 | float64 | 1175.8428571428572 | 1164.275 |
| us_price_lag_2 | float64 | 14.31930548780488 | 14.090734117647058 |
| exchange_rate_lag_2 | float64 | 1167.452380952381 | 1175.8428571428572 |
| us_price_lag_3 | float64 | 13.256560512820514 | 14.31930548780488 |
| exchange_rate_lag_3 | float64 | 1184.1333333333332 | 1167.452380952381 |
| kr_price_lead_1 | float64 | 2517.0 | 2517.0 |
| kr_price_lead_2 | float64 | 2517.0 | 2411.0 |
| kr_price_lead_3 | float64 | 2411.0 | 2492.0 |
| kr_price_lead_4 | float64 | 2492.0 | 2396.0 |
| kr_price_lead_5 | float64 | 2396.0 | 2363.0 |
| kr_price_lead_6 | float64 | 2363.0 | 2490.0 |
| kr_price_max_6m | float64 | 2517.0 | 2517.0 |
| target_max_diff_6m | float64 | 3.0 | 0.0 |

#### `part_crosswalk.csv`
- **총 행(Row) 수**: 약 115행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| canonical_id | object | la_galbi | la_galbi |
| canonical_name_ko | object | LA갈비 | LA갈비 |
| kmta_part | object | 갈비 | 갈비 |
| usda_primal | object | Primal Plate | Primal Plate |
| ml_target | bool | True | True |
| notes | object | USDA Short Plate short rib(123A). 늑간살(rib finger)은 갈비뼈 사이 살 — LA갈비와 동일 원료 축. 숏립앤드(short rib end)=숏립 정형 끝단. 양지갈비(호주)=양지 쪽 갈비뼈(plate/brisket rib) 추정 — 뼈 비중 높은 저가품, 확인 필요 | USDA Short Plate short rib(123A). 늑간살(rib finger)은 갈비뼈 사이 살 — LA갈비와 동일 원료 축. 숏립앤드(short rib end)=숏립 정형 끝단. 양지갈비(호주)=양지 쪽 갈비뼈(plate/brisket rib) 추정 — 뼈 비중 높은 저가품, 확인 필요 |
| source | object | meatbox | meatbox |
| source_key | object | LA갈비 | 갈비살/늑간살 |
| source_label | object | LA갈비 | 갈비살/늑간살 |
| meatbox_origins | object | 미국/호주 | 미국/호주 |
| usda_compare | object | direct(미국)/proxy(호주) | direct(미국)/proxy(호주) |

#### `processed_usda_cost.csv`
- **총 행(Row) 수**: 약 172349행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Date | object | 2019-01-01 | 2019-01-02 |
| Exchange_Rate | float64 | 1118.1 | 1118.1 |
| report_date | object | nan | 01/02/2019 |
| item_description | object | nan | Brisket, deckle-off, bnls (120  1) |
| number_trades | float64 | nan | 32.0 |
| total_pounds | float64 | nan | 124354.0 |
| price_range_low | float64 | nan | 280.0 |
| price_range_high | float64 | nan | 310.0 |
| weighted_average | float64 | nan | 291.82 |
| grade | object | nan | Choice |
| trim_description | float64 | nan | nan |
| total_volume_kg | float64 | nan | 56405.98 |
| price_range_low_USD_kg | float64 | nan | 6.1729 |
| price_range_high_USD_kg | float64 | nan | 6.8343 |
| weighted_average_USD_kg | float64 | nan | 6.4335 |

#### `samgyup_model_features.csv`
- **총 행(Row) 수**: 약 55행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-03-01 |
| samgyup | float64 | 6368.0 | 6260.0 |
| usda_plate | float64 | 3.440809090909091 | 3.652428571428571 |
| fx | float64 | 1122.0 | 1130.72 |
| import_yj | float64 | nan | 3991.0 |
| stock_yj | float64 | nan | nan |
| fas_china | float64 | 7.4 | 78.75 |
| fas_korea | float64 | 170.0 | 4095.75 |
| cof_inventory | float64 | 11680000.0 | 11785000.0 |
| cof_placements | float64 | nan | 1858000.0 |
| us_soybean_meal | float64 | nan | 338.0440689461579 |
| kr_ppi_food | float64 | nan | 98.69 |
| kr_cpi_food | float64 | nan | 96.441 |
| us_wti | float64 | 51.37571428571429 | 58.151428571428575 |
| kr_base_rate | float64 | nan | 1.75 |
| kr_temp_avg | float64 | 1.4219354838709677 | 8.636774193548387 |
| kr_precip | float64 | 0.26 | 1.229032258064516 |

#### `samgyup_unified_monthly.csv`
- **총 행(Row) 수**: 약 72행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2016-12-01 | 2017-01-01 |
| price_won_per_kg | float64 | 5200.0 | 5467.0 |
| source | object | dealer | dealer |
| n_obs | int64 | 4 | 6 |

#### `usda_plate_usd_kg.csv`
- **총 행(Row) 수**: 약 1994행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 2019-01-02 | 2019-01-03 |
| primal_desc | object | Primal Plate | Primal Plate |
| choice_usd_per_kg | float64 | 3.4039 | 3.4313 |
| select_usd_per_kg | float64 | 3.4039 | 3.4313 |

#### `validation_mapping_result.csv`
- **총 행(Row) 수**: 약 42행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| USDA_Code | object | 123A | 112A |
| Original_Description | object | Short Plate, short rib (123A  3) | Rib, ribeye, bnls, heavy (112A  3) |
| Korean_Name | object | LA갈비-미국 | 등심-호주 |
| Status | object | 정상 | 정상 |
| Note | object | Master 품목명과 연결 가능 | Master 품목명과 연결 가능 |

### 폴더: `2_dashboard/`

#### `dashboard_ready_data.csv`
- **총 행(Row) 수**: 약 81054행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2026-08-11 | 2026-08-12 |
| category | object | 미국 | 미국 |
| part | object | BBQ등갈비 | BBQ등갈비 |
| brand | object | 엑셀(86K) | 엑셀(86K) |
| wholesale_price | float64 | 10760.0 | 10760.0 |
| ma7 | float64 | nan | nan |
| ma30 | float64 | nan | nan |
| min_total | float64 | 10760.0 | 10760.0 |
| max_total | float64 | 11800.0 | 11800.0 |
| is_filled | bool | False | True |

#### `data_status.csv`
- **총 행(Row) 수**: 약 24행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 데이터 | object | 미트박스 시세 | USDA 부위시세 |
| 소스 | object | 미트박스 | USDA |
| 주기 | object | 일 | 일 |
| 최신데이터 | object | 2026-11-03 | 2026-10-29 |
| 지연(일) | int64 | 0 | 5 |
| 상태 | object | 최신 | 최신 |

#### `fas_supply_signal.csv`
- **총 행(Row) 수**: 약 94행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-02-01 |
| china_exp | int64 | 37 | 782 |
| korea_exp | int64 | 850 | 26773 |
| china_vs_med | float64 | 0.0 | 0.08 |
| korea_vs_med | float64 | 0.04 | 1.43 |
| alert_level | int64 | 0 | 0 |
| note | object | 정상 (중국 시장 개방 이전 — 중국 기준 판단 제외) | 정상 (중국 시장 개방 이전 — 중국 기준 판단 제외) |
| weeks | int64 | 5 | 4 |
| expected_weeks | int64 | 5 | 4 |
| is_partial | bool | False | False |
| china_wk_avg | float64 | 7.4 | 195.5 |
| korea_wk_avg | float64 | 170.0 | 6693.2 |
| china_base | float64 | 2589.2 | 2589.2 |
| korea_base | float64 | 4065.8 | 4678.1 |

#### `hanwoo_dashboard_ready.csv`
- **총 행(Row) 수**: 약 166612행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2026-05-08 | 2026-05-12 |
| period_days | int64 | 1 | 1 |
| source | object | ekape_auction | ekape_auction |
| grade | int64 | 1 | 1 |
| sex | object | 전체 | 전체 |
| market_code | int64 | 613 | 613 |
| market_name | object | 관성 | 관성 |
| is_national_total | bool | False | False |
| is_regional_total | bool | False | False |
| price_won_per_kg | float64 | 17441.0 | 18101.0 |
| head_count | int64 | 6 | 40 |
| part | object | 전체(도체) | 전체(도체) |
| country_name | float64 | nan | nan |
| origin | object | 국내산 | 국내산 |
| ma7 | float64 | 17756.0 | 17842.25 |
| ma30 | float64 | 17346.9 | 17317.315789473683 |
| is_outlier | bool | False | False |

#### `macro_dashboard_ready.csv`
- **총 행(Row) 수**: 약 2860행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-02 |
| au_beef_price | float64 | 185.9565 | 185.9565 |
| au_eyci | float64 | nan | 472.7273 |
| au_heavy_steer | float64 | nan | 280.5917 |
| kr_base_rate | float64 | 1.75 | 1.75 |
| kr_ccsi | float64 | 98.3 | 98.3 |
| kr_cpi_beef_dom | float64 | 91.195 | 91.195 |
| kr_cpi_beef_imp | float64 | 96.731 | 96.731 |
| kr_cpi_diesel | float64 | 104.995 | 104.995 |
| kr_cpi_dineout | float64 | 98.891 | 98.891 |
| kr_cpi_dineout_beef | float64 | 96.662 | 96.662 |
| kr_cpi_food | float64 | 95.789 | 95.789 |
| kr_cpi_pork | float64 | 84.205 | 84.205 |
| kr_cpi_total | float64 | 98.884 | 98.884 |
| kr_esi | float64 | 92.6 | 92.6 |
| kr_fx_aud | float64 | nan | 787.98 |
| kr_impi_beef_krw | float64 | 96.96 | 96.96 |
| kr_impi_beef_lc | float64 | 101.98 | 101.98 |
| kr_ppi_cold_storage | float64 | 102.69 | 102.69 |
| kr_ppi_food | float64 | 98.7 | 98.7 |
| kr_ppi_ocean_freight | float64 | 113.54 | 113.54 |
| kr_ppi_road_freight | float64 | 98.47 | 98.47 |
| kr_precip | float64 | 0.02 | 0.0 |
| kr_retail_cvs | float64 | 98.6 | 98.6 |
| kr_retail_dept | float64 | 112.4 | 112.4 |
| kr_retail_food | float64 | 105.0 | 105.0 |
| kr_retail_hypermarket | float64 | 101.1 | 101.1 |
| kr_service_food | float64 | 120.8 | 120.8 |
| kr_temp_avg | float64 | -1.46 | -1.52 |
| kr_temp_max | float64 | 2.28 | 3.58 |
| us_corn | float64 | 166.8462 | 166.8462 |
| us_diesel | float64 | nan | nan |
| us_fed_steer | float64 | 188.2 | 188.2 |
| us_food_ppi | float64 | 206.2 | 206.2 |
| us_ppi_ocean_freight | float64 | 307.2 | 307.2 |
| us_soybean | float64 | 333.7771 | 333.7771 |
| us_soybean_meal | float64 | 344.7295 | 344.7295 |
| us_wti | float64 | nan | 46.31 |
| au_beef_price_yoy_pct | float64 | nan | nan |
| au_eyci_yoy_pct | float64 | nan | nan |
| au_heavy_steer_yoy_pct | float64 | nan | nan |
| kr_base_rate_yoy_pct | float64 | nan | nan |
| kr_ccsi_yoy_pct | float64 | nan | nan |
| kr_cpi_beef_dom_yoy_pct | float64 | nan | nan |
| kr_cpi_beef_imp_yoy_pct | float64 | nan | nan |
| kr_cpi_diesel_yoy_pct | float64 | nan | nan |
| kr_cpi_dineout_yoy_pct | float64 | nan | nan |
| kr_cpi_dineout_beef_yoy_pct | float64 | nan | nan |
| kr_cpi_food_yoy_pct | float64 | nan | nan |
| kr_cpi_pork_yoy_pct | float64 | nan | nan |
| kr_cpi_total_yoy_pct | float64 | nan | nan |
| kr_esi_yoy_pct | float64 | nan | nan |
| kr_fx_aud_yoy_pct | float64 | nan | nan |
| kr_impi_beef_krw_yoy_pct | float64 | nan | nan |
| kr_impi_beef_lc_yoy_pct | float64 | nan | nan |
| kr_ppi_cold_storage_yoy_pct | float64 | nan | nan |
| kr_ppi_food_yoy_pct | float64 | nan | nan |
| kr_ppi_ocean_freight_yoy_pct | float64 | nan | nan |
| kr_ppi_road_freight_yoy_pct | float64 | nan | nan |
| kr_precip_yoy_pct | float64 | nan | nan |
| kr_retail_cvs_yoy_pct | float64 | nan | nan |
| kr_retail_dept_yoy_pct | float64 | nan | nan |
| kr_retail_food_yoy_pct | float64 | nan | nan |
| kr_retail_hypermarket_yoy_pct | float64 | nan | nan |
| kr_service_food_yoy_pct | float64 | nan | nan |
| kr_temp_avg_yoy_pct | float64 | nan | nan |
| kr_temp_max_yoy_pct | float64 | nan | nan |
| us_corn_yoy_pct | float64 | nan | nan |
| us_diesel_yoy_pct | float64 | nan | nan |
| us_fed_steer_yoy_pct | float64 | nan | nan |
| us_food_ppi_yoy_pct | float64 | nan | nan |
| us_ppi_ocean_freight_yoy_pct | float64 | nan | nan |
| us_soybean_yoy_pct | float64 | nan | nan |
| us_soybean_meal_yoy_pct | float64 | nan | nan |
| us_wti_yoy_pct | float64 | nan | nan |

#### `meatbox_universe.csv`
- **총 행(Row) 수**: 약 30행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| part | object | 황제늑간 | 센터컷 |
| n_days | int64 | 476 | 474 |
| coverage_pct | int64 | 74 | 73 |
| recent_days | int64 | 10 | 0 |
| max_gap | int64 | 17 | 8 |
| start | object | 2025-01-22 | 2025-01-22 |
| tier | int64 | 0 | 0 |
| status | object | 제외(거래끊김) | 제외(거래끊김) |

#### `samgyup_feature_importance.csv`
- **총 행(Row) 수**: 약 15행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| feature | object | fx | stock_yj |
| std_coef | float64 | 0.619 | -0.488 |

#### `samgyup_forecast.csv`
- **총 행(Row) 수**: 약 72행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-02-01 |
| type | object | actual | actual |
| base | int64 | 6368 | 6314 |
| low | float64 | nan | nan |
| high | float64 | nan | nan |

#### `switch_signal.csv`
- **총 행(Row) 수**: 약 23행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| part | object | 갈비살/늑간살 | 차돌박이 |
| tier | int64 | 1 | 1 |
| current_price | int64 | 31350 | 26732 |
| pct_rank | int64 | 100 | 100 |
| momentum_30d | float64 | 6.3 | 11.2 |
| signal | object | 매도후보(고평가) | 매도후보(고평가) |
| n_obs | int64 | 620 | 628 |

<!-- AUTO-GENERATED-SCHEMA:END -->
