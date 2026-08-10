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

> 마지막 갱신: 2026-08-11 08:23
> `python src/utils/extract_data_schema.py` 또는 `python src/run_daily_update.py` 파이프라인에서 자동 갱신

### 폴더: `0_raw/`

#### `beef_Short Plate_wholesale_price.xlsx`
- **총 행(Row) 수**: 약 361행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 상  품    원  장 | object | nan | 상품명: |
| Unnamed: 1 | object | nan | 미국산 |
| Unnamed: 2 | object | nan | nan |

#### `beef_import_data_fast.xlsx`
- **총 행(Row) 수**: 약 340행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준년월 | object | 2019-01 | 2019-01 |
| 국가 | object | 미국 | 호주 |
| 구분 | object | 냉동 | 냉동 |
| 갈비 | int64 | 5977 | 2935 |
| 등심 | int64 | 87 | 1486 |
| 목심 | int64 | 105 | 981 |
| 사태 | int64 | 147 | 604 |
| 설도 | int64 | 88 | 1168 |
| 안심 | int64 | 0 | 41 |
| 앞다리 | int64 | 115 | 1616 |
| 양지 | int64 | 2428 | 2125 |
| 우둔 | int64 | 0 | 1162 |
| 채끝 | int64 | 0 | 1 |
| 기타 | int64 | 0 | 1799 |
| 합계 | int64 | 8947 | 13918 |

#### `beef_price_data.xlsx`
- **총 행(Row) 수**: 약 120행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2025-12-22 | 2025-12-22 |
| 품목명 | object | 갈비살/늑간살-미국 / IBP(245L) | 갈비살/늑간살-미국 / 오로라 앵거스 비프(788) |
| 원산지 | object | 미국 | 미국 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 24580 | 22700 |

#### `beef_price_raw_FULL.xlsx`
- **총 행(Row) 수**: 약 440행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 관심상품 등록하기 | 관심상품 등록하기 |
| 품목 △ | object | 갈비-국산(한우암소) / 동명F&B | 갈비본살-미국 / IBP |
| 등급 | object | 3등급 | 프라임 |
| 보관 | object | 냉동 | 냉장 |
| 도매시세 (kg당 가격) | object | 17,580 원  - | 37,030 원  - |
| 미트박스 상품 | object | 상품보기 | 상품보기 |
| 기준일자_수집 | object | 2025-12-22 | 2025-12-22 |

#### `beef_price_raw_latest.xlsx`
- **총 행(Row) 수**: 약 465행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 관심상품 등록하기 | 관심상품 등록하기 |
| 품목 △ | object | 갈비-국산(한우암소) / 동명F&B | 갈비본살-미국 / IBP(245J) |
| 등급 | object | 3등급 | 프라임 |
| 보관 | object | 냉동 | 냉장 |
| 도매시세 (kg당 가격) | object | 18,970 원  - | 32,430 원  - |
| 미트박스 상품 | object | 상품보기 | 상품보기 |
| 기준일자_수집 | object | 2026-01-26 | 2026-01-26 |

#### `beef_primal_cut_prices.xlsx`
- **총 행(Row) 수**: 약 16행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| cutmeatName | object | 안심 | 등심 |
| hanBoxCnt | int64 | 0 | 0 |
| han_0Cnt | int64 | 0 | 0 |
| han_1Cnt | int64 | 0 | 0 |
| han_2Cnt | int64 | 0 | 0 |
| han_3Cnt | int64 | 0 | 0 |
| han_4Cnt | int64 | 0 | 0 |
| han_5Cnt | int64 | 0 | 0 |
| yukBoxCnt | int64 | 0 | 0 |
| yuk_0Cnt | int64 | 0 | 0 |
| yuk_1Cnt | int64 | 0 | 0 |
| yuk_2Cnt | int64 | 0 | 0 |
| yuk_3Cnt | int64 | 0 | 0 |
| yuk_4Cnt | int64 | 0 | 0 |
| yuk_5Cnt | int64 | 0 | 0 |

#### `beef_stock_data.xlsx`
- **총 행(Row) 수**: 약 1156행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준년월 | object | 2019-01 | 2019-01 |
| 부위별 부위별 | object | 안심 | 등심 |
| 조사재고량 조사재고량 | int64 | 590 | 18617 |
| 대비(%) 전월 | int64 | 0 | 0 |
| 대비(%) 전년 | int64 | 0 | 0 |

#### `exchange_rate_data.xlsx`
- **총 행(Row) 수**: 약 1627행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Date | object | 2020-01-02 | 2020-01-03 |
| Close | float64 | 1159.0 | 1167.5 |

#### `fas_export_sales_raw.csv`
- **총 행(Row) 수**: 약 792행

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

#### `found_missing_ids.xlsx`
- **총 행(Row) 수**: 약 8행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2026-01-22 | 2026-01-22 |
| 품목명 | object | 관심상품 등록하기 삼겹양지-호주  | 관심상품 등록하기 홍두깨-호주  |
| 원산지 | object | 호주 | 호주 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 0 | 0 |
| siseSeq | int64 | 43569155 | 43558120 |

#### `han_auction_raw.csv`
- **총 행(Row) 수**: 약 22989행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| auction_start_ymd | int64 | 20190101 | 20190101 |
| auction_end_ymd | int64 | 20190130 | 20190130 |
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
| price_won_per_kg | int64 | 20627 | 20748 |
| head_count | int64 | 678 | 721 |

#### `kamis_hanwoo_raw.csv`
- **총 행(Row) 수**: 약 83400행

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
- **총 행(Row) 수**: 약 27800행

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
- **총 행(Row) 수**: 약 11731행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-01 |
| country | object | KR | KR |
| indicator_id | object | kr_base_rate | kr_ccsi |
| indicator_name | object | 한국은행 기준금리 | 소비자심리지수(CCSI) |
| value | float64 | 1.75 | 98.3 |
| unit | object | 연% | p (장기평균=100) |
| freq | object | M | M |
| source | object | ECOS | ECOS |

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
- **총 행(Row) 수**: 약 182행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| std_date | object | 2026-07 | 2026-07 |
| 구분 | object | 미국 | 호주 |
| 부위별_갈비_합계 | float64 | 5503.3 | 4742.3 |
| 부위별_등심_합계 | float64 | 720.9 | 3079.2 |
| 부위별_목심_합계 | float64 | 1793.3 | 1034.6 |
| 부위별_사태_합계 | float64 | 63.6 | 565.2 |
| 부위별_설도_합계 | float64 | 675.5 | 3173.1 |
| 부위별_안심_합계 | float64 | 46.9 | 102.6 |
| 부위별_앞다리_합계 | float64 | 1376.2 | 4238.9 |
| 부위별_양지_합계 | float64 | 2716.2 | 3790.0 |
| 부위별_우둔_합계 | float64 | 21.9 | 2916.1 |
| 부위별_채끝_합계 | float64 | 0.0 | 197.7 |
| 부위별_기타_합계 | float64 | 0.0 | 7149.8 |
| 부위별_계_합계 | float64 | 25835.800000000003 | 61979.19999999999 |

#### `meatbox_id_list.xlsx`
- **총 행(Row) 수**: 약 150행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2026-01-22 | 2026-01-22 |
| 품목명 | object | 갈비살/늑간살-미국 / IBP(245L) | 갈비살/늑간살-미국 / 엑셀(ESA/앵거스)(86K(EXCEL/ESA)) |
| 원산지 | object | 미국 | 미국 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 24580 | 22340 |
| siseSeq | int64 | 43567223 | 43568980 |

#### `meatbox_raw_full_rows.xlsx`
- **총 행(Row) 수**: 약 617행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| page | int64 | 1 | 1 |
| visible_text | float64 | nan | nan |
| raw_html | object | <tr> 						<th>FAMILY</th> 						<td>없음</td> 						<td>없음</td> 					</tr> | <tr> 						<th>SILVER</th> 						<td>분기 중 월 1회 <br> 이상 구매</td> 						<td>1천원 쿠폰<br> X 1장</td> 					</tr> |

#### `meatbox_sise_43084139.xlsx`
- **총 행(Row) 수**: 약 366행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| siseSeq | int64 | 0 | 0 |
| siseDate | object | 2025-01-20 | 2025-01-21 |
| itemKindCd | float64 | nan | nan |
| itemCatSeq | int64 | 0 | 0 |
| brandCd | float64 | nan | nan |
| originCd | float64 | nan | nan |
| gradeCd | float64 | nan | nan |
| keepingCd | float64 | nan | nan |
| estNo | float64 | nan | nan |
| preAvgPrice | int64 | 0 | 0 |
| avgPrice | int64 | 0 | 0 |
| updateAvgPrice | int64 | 0 | 0 |
| preMinPrice | int64 | 0 | 0 |
| minPrice | int64 | 0 | 0 |
| updateMinPrice | int64 | 0 | 0 |
| estimatePrice | int64 | 0 | 0 |
| marketPrice | int64 | 0 | 0 |
| preMarketPrice | int64 | 0 | 0 |
| tradeCnt | int64 | 0 | 0 |
| maxKg | float64 | nan | nan |
| manageYn | float64 | nan | nan |
| modMemberSeq | int64 | 0 | 0 |
| moddate | float64 | nan | nan |
| favProductYn | float64 | nan | nan |
| productSeq | int64 | 0 | 0 |
| itemName | float64 | nan | nan |
| speciesKind | int64 | 0 | 0 |
| kindNmae | float64 | nan | nan |
| catName | float64 | nan | nan |
| originName | float64 | nan | nan |
| brandName | float64 | nan | nan |
| gradeName | float64 | nan | nan |
| keepingMethod | float64 | nan | nan |
| itemCnt | int64 | 0 | 0 |
| diffMarketPricePreAvgPrice | int64 | 0 | 0 |
| diffRateMarketPricePreAvgPrice | int64 | 0 | 0 |

#### `raw_food_safety_data.csv`
- **총 행(Row) 수**: 약 44행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| std_ym | object | 2026-01 | 2026-01 |
| 품명 | object | 소고기 | 소고기 |
| 구분 | object | 냉동 | 냉동 |
| 부위 | object | 갈비 | 갈비 |
| 국가 | object | 미국 | 호주 |
| 전년도_누계 | object | 86,119,639.746 | 37,300,431.04 |
| 전년도_12월_누계 | int64 | 0 | 0 |
| 당월_상순 | object | 1,959,187.634 | 1,351,661.63 |
| 당월_중순 | object | 2,351,361.735 | 1,124,170.21 |
| 당월_하순 | object | 2,110,859.31 | 1,028,600.92 |
| 당월_소계 | object | 6,421,408.679 | 3,504,432.76 |
| 당해년도_누계 | object | 6,421,408.679 | 3,504,432.76 |

#### `raw_meatbox_2026-01-26.xlsx`
- **총 행(Row) 수**: 약 480행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 관심상품 등록하기 | 관심상품 등록하기 |
| 품목 △ | object | 갈비-국산(한우암소) / 동명F&B | 갈비본살-미국 / IBP(245J) |
| 등급 | object | 3등급 | 프라임 |
| 보관 | object | 냉동 | 냉장 |
| 도매시세 (kg당 가격) | object | 18,970 원  - | 32,430 원  - |
| 미트박스 상품 | object | 상품보기 | 상품보기 |
| 기준일자_수집 | object | 2026-01-26 | 2026-01-26 |

#### `raw_meatbox_20260126.csv`
- **총 행(Row) 수**: 약 180행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 품목명 | object | 갈비살/늑간살-미국 / IBP(245L) | 갈비살/늑간살-미국 / 엑셀(ESA/앵거스)(86K(EXCEL/ESA)) |
| 보관 | object | 냉동 | 냉동 |
| 도매시세_raw | object | 24,580 원  - | 22,340 원  - |
| 원산지 | object | 미국 | 미국 |
| 도매시세 | int64 | 24580 | 22340 |

#### `us_beef_parts_import_daily.csv`
- **총 행(Row) 수**: 약 22행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| col_0 | object | 소고기 | 소고기 |
| col_1 | object | 냉동 | 냉동 |
| col_2 | object | 갈비 | 등심 |
| col_3 | object | 미국 | 미국 |
| col_4 | object | 80,246,513.521 | 3,985,130.09 |
| col_5 | object | 77,893,975.748 | 2,911,156.048 |
| col_6 | object | 2,736,054.072 | 90,033.21 |
| col_7 | object | 3,001,242.343 | 5,261.64 |
| col_8 | object | 1,441,317.613 | 20,624.01 |
| col_9 | object | 7,178,614.028 | 115,918.86 |
| col_10 | object | 85,072,589.776 | 3,027,074.908 |

#### `us_cattle_on_feed.csv`
- **총 행(Row) 수**: 약 271행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-01 |
| short_desc | object | CATTLE, ON FEED - INVENTORY | CATTLE, ON FEED - PLACEMENTS, MEASURED IN HEAD |
| value | float64 | 14367900.0 | 1964000.0 |
| unit | object | HEAD | HEAD |
| reference_period | object | FIRST OF JAN | JAN |

#### `usda_beef_history.csv`
- **총 행(Row) 수**: 약 167270행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 08/10/2026 | 08/10/2026 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| item_description | object | Brisket, deckle-off, bnls (120  1) | Brisket, point/off, bnls (120A  3) |
| number_trades | int64 | 30 | 6 |
| total_pounds | object | 100,824 | 4,588 |
| price_range_low | float64 | 481.0 | 765.0 |
| price_range_high | float64 | 535.4 | 822.0 |
| weighted_average | float64 | 494.16 | 780.76 |
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
| published_date | object | 08/10/2026 14:42:47 | 08/10/2026 14:42:47 |
| grade | object | Choice | Choice |
| trim_description | float64 | nan | nan |

#### `usda_choice_cuts_02112026.csv`
- **총 행(Row) 수**: 약 14316행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 02/11/2026 | 02/11/2026 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| item_description | object | Rib, ribeye, bnls, light (112A  3) | Rib, ribeye, bnls, heavy (112A  3) |
| number_trades | int64 | 10 | 45 |
| total_pounds | object | 116,806 | 197,338 |
| price_range_low | object | 1,072.16 | 1,015.00 |
| price_range_high | object | 1,238.50 | 1,163.50 |
| weighted_average | object | 1,081.83 | 1,048.19 |
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
| published_date | object | 02/11/2026 14:49:49 | 02/11/2026 14:49:49 |

#### `usda_choice_cuts_history.csv`
- **총 행(Row) 수**: 약 76314행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 02/11/2026 | 02/11/2026 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| item_description | object | Rib, ribeye, lip-on, bn-in (109E  1) | Rib, ribeye, bnls, light (112A  3) |
| number_trades | float64 | 16.0 | 10.0 |
| total_pounds | object | 258,790 | 116,806 |
| price_range_low | object | 893.66 | 1,072.16 |
| price_range_high | object | 1,098.00 | 1,238.50 |
| weighted_average | object | 901.04 | 1,081.83 |
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
| published_date | object | 02/11/2026 14:49:49 | 02/11/2026 14:49:49 |

#### `usda_primal_history.csv`
- **총 행(Row) 수**: 약 13615행

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

#### `usda_primal_values_02112026.csv`
- **총 행(Row) 수**: 약 44219행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 02/11/2026 | 02/11/2026 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| primal_desc | object | Primal Rib | Primal Chuck |
| choice_600_900 | float64 | 491.02 | 325.79 |
| select_600_900 | float64 | 485.19 | 332.31 |
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
| published_date | object | 02/11/2026 14:49:49 | 02/11/2026 14:49:49 |

#### `usda_raw_20260212.csv`
- **총 행(Row) 수**: 약 6317행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 02/11/2026 | 02/10/2026 |
| is_correction | float64 | nan | nan |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
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
| published_date | object | 02/11/2026 14:49:49 | 02/10/2026 14:44:16 |

#### `미국산소고기_2019_2024_Total.csv`
- **총 행(Row) 수**: 약 749행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 년월 | object | 2019-01 | 2019-01 |
| 부위 | object | 갈비 | 등심 |
| 중량 | float64 | 6930137.81 | 379739.77 |

#### `미국산소고기_202412_202511.csv`
- **총 행(Row) 수**: 약 121행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 년월 | object | 2025-01 | 2025-01 |
| 부위 | object | 갈비 | 등심 |
| 중량 | float64 | 6043215.33 | 23446.39 |

#### `삼겹양지 유통가격 추이 1.xlsx`
- **총 행(Row) 수**: 약 361행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 상  품    원  장 | object | nan | 상품명: |
| Unnamed: 1 | object | nan | 미국산 |
| Unnamed: 2 | object | nan | nan |

### 폴더: `1_processed/`

#### `beef_price_history.xlsx`
- **총 행(Row) 수**: 약 2691행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2025-12-22 | 2025-12-22 |
| 품목명 | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 엑셀(86R) |
| 원산지 | object | 미국 | 미국 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 11180 | 11180 |

#### `clean_price_data.csv`
- **총 행(Row) 수**: 약 440행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-12-22 | 2025-12-22 |
| part_name | object | 갈비 | 갈비본살 |
| country | object | 국산(한우암소) | 미국 |
| brand | object | 동명F&B | IBP |
| wholesale_price | int64 | 17580 | 37030 |

#### `dashboard_ready_data.csv`
- **총 행(Row) 수**: 약 47082행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-23 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 엑셀(86R) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10380.0 |
| brand | object | - | - |
| part_clean | object | BBQ등갈비 | BBQ등갈비 |
| brand_clean | object | 엑셀(86R) | 엑셀(86R) |
| ma7 | float64 | 10380.0 | 10380.0 |
| ma30 | float64 | 10380.0 | 10380.0 |
| min_total | float64 | 9860.0 | 9860.0 |
| max_total | float64 | 11180.0 | 11180.0 |

#### `han_auction_daily.csv`
- **총 행(Row) 수**: 약 22989행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-30 | 2019-01-30 |
| source | object | ekape_auction | ekape_auction |
| grade | object | 1++ | 1++ |
| sex | object | 전체 | 전체 |
| market_code | int64 | 202 | 302 |
| market_name | object | 부경축공 | 협신식품 |
| is_national_total | bool | False | False |
| is_regional_total | bool | False | False |
| price_won_per_kg | int64 | 20627 | 20748 |
| head_count | int64 | 678 | 721 |

#### `macro_indicators_daily.csv`
- **총 행(Row) 수**: 약 58380행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-02 |
| country | object | KR | KR |
| indicator_id | object | kr_base_rate | kr_base_rate |
| indicator_name | object | 한국은행 기준금리 | 한국은행 기준금리 |
| value | float64 | 1.75 | 1.75 |
| unit | object | 연% | 연% |
| freq | object | M | M |
| source | object | ECOS | ECOS |
| ma30 | float64 | nan | nan |
| yoy_pct | float64 | nan | nan |
| mom_pct | float64 | nan | nan |

#### `master_price_data.csv`
- **총 행(Row) 수**: 약 63254행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-22 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 오마하(960A) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10390.0 |
| brand | object | - | - |

#### `master_price_data_backup.csv`
- **총 행(Row) 수**: 약 46508행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-22 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 오마하(960A) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10390.0 |
| brand | object | - | - |
| item_name | float64 | nan | nan |
| origin | float64 | nan | nan |
| grade | float64 | nan | nan |
| marketPrice | float64 | nan | nan |

#### `master_price_data_backup_full.csv`
- **총 행(Row) 수**: 약 63114행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-22 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 오마하(960A) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10390.0 |
| brand | object | - | - |

#### `ml_features_rib.csv`
- **총 행(Row) 수**: 약 73행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 2020-04-01 | 2020-05-01 |
| kr_price | float64 | 2411.0 | 2492.0 |
| us_price | float64 | 12.16638527607362 | 17.422213756613758 |
| exchange_rate | float64 | 1224.2 | 1230.4736842105262 |
| import_vol | float64 | 12108.0 | 11683.0 |
| stock | float64 | 59834.0 | 60827.0 |
| import_vol_mom | float64 | 0.3793574846206424 | -0.0351007598282127 |
| import_vol_yoy | float64 | 0.0519548218940051 | 0.0153832782895879 |
| stock_mom | float64 | 0.0868633292160139 | 0.0165959153658454 |
| stock_yoy | float64 | 0.2525958800870875 | 0.2332880517426654 |
| stock_ma_3 | float64 | 55903.333333333336 | 58571.0 |
| margin_spread | float64 | -12483.088854969325 | -18945.575548203844 |
| us_price_lag_1 | float64 | 13.169493785310737 | 12.16638527607362 |
| exchange_rate_lag_1 | float64 | 1220.4318181818182 | 1224.2 |
| us_price_lag_2 | float64 | 12.578357228915664 | 13.169493785310737 |
| exchange_rate_lag_2 | float64 | 1195.6 | 1220.4318181818182 |
| us_price_lag_3 | float64 | 12.96344375 | 12.578357228915664 |
| exchange_rate_lag_3 | float64 | 1167.9 | 1195.6 |
| kr_price_lead_1 | float64 | 2492.0 | 2396.0 |
| kr_price_lead_2 | float64 | 2396.0 | 2363.0 |
| kr_price_diff_lead_1 | float64 | 81.0 | -96.0 |
| kr_price_diff_lead_2 | float64 | -15.0 | -129.0 |

#### `ml_features_rolling_rib.csv`
- **총 행(Row) 수**: 약 69행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Unnamed: 0 | object | 2020-04-01 | 2020-05-01 |
| kr_price | float64 | 2411.0 | 2492.0 |
| us_price | float64 | 12.16638527607362 | 17.422213756613758 |
| exchange_rate | float64 | 1224.2 | 1230.4736842105262 |
| import_vol | float64 | 12108.0 | 11683.0 |
| stock | float64 | 59834.0 | 60827.0 |
| import_vol_mom | float64 | 0.3793574846206424 | -0.0351007598282127 |
| import_vol_yoy | float64 | 0.0519548218940051 | 0.0153832782895879 |
| stock_mom | float64 | 0.0868633292160139 | 0.0165959153658454 |
| stock_yoy | float64 | 0.2525958800870875 | 0.2332880517426654 |
| stock_ma_3 | float64 | 55903.333333333336 | 58571.0 |
| margin_spread | float64 | -12483.088854969325 | -18945.575548203844 |
| us_price_lag_1 | float64 | 13.169493785310737 | 12.16638527607362 |
| exchange_rate_lag_1 | float64 | 1220.4318181818182 | 1224.2 |
| us_price_lag_2 | float64 | 12.578357228915664 | 13.169493785310737 |
| exchange_rate_lag_2 | float64 | 1195.6 | 1220.4318181818182 |
| us_price_lag_3 | float64 | 12.96344375 | 12.578357228915664 |
| exchange_rate_lag_3 | float64 | 1167.9 | 1195.6 |
| kr_price_lead_1 | float64 | 2492.0 | 2396.0 |
| kr_price_lead_2 | float64 | 2396.0 | 2363.0 |
| kr_price_lead_3 | float64 | 2363.0 | 2490.0 |
| kr_price_lead_4 | float64 | 2490.0 | 2478.0 |
| kr_price_lead_5 | float64 | 2478.0 | 2468.0 |
| kr_price_lead_6 | float64 | 2468.0 | 2470.0 |
| kr_price_max_6m | float64 | 2492.0 | 2490.0 |
| target_max_diff_6m | float64 | 81.0 | -2.0 |

#### `monthly_master_data.xlsx`
- **총 행(Row) 수**: 약 532행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | datetime64[ns] | 2024-12-01 00:00:00 | 2024-12-01 00:00:00 |
| avg_price | int64 | 9930 | 9930 |
| avg_exchange | float64 | 1441.7 | 1441.7 |
| import_vol | object | 미국 | 미국 |
| stock_vol | object | 안심 | 등심 |

#### `part_crosswalk.csv`
- **총 행(Row) 수**: 약 81행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| canonical_id | object | la_galbi | la_galbi |
| canonical_name_ko | object | LA갈비 | LA갈비 |
| kmta_part | object | 갈비 | 갈비 |
| usda_primal | object | Primal Plate | Primal Plate |
| ml_target | bool | True | True |
| notes | object | USDA Short Plate short rib(123A). 늑간살(rib finger)은 갈비뼈 사이 살 — LA갈비와 동일 원료 축 | USDA Short Plate short rib(123A). 늑간살(rib finger)은 갈비뼈 사이 살 — LA갈비와 동일 원료 축 |
| source | object | meatbox | meatbox |
| source_key | object | LA갈비 | 갈비살/늑간살 |
| source_label | object | LA갈비 | 갈비살/늑간살 |

#### `processed_usda_cost.csv`
- **총 행(Row) 수**: 약 168112행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Date | object | 2019-01-01 | 2019-01-02 |
| Exchange_Rate | float64 | 1159.0 | 1159.0 |
| report_date | object | nan | 01/02/2019 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| item_description | object | nan | Brisket, deckle-off, bnls (120  1) |
| number_trades | float64 | nan | 32.0 |
| total_pounds | float64 | nan | 124354.0 |
| price_range_low | float64 | nan | 280.0 |
| price_range_high | float64 | nan | 310.0 |
| weighted_average | float64 | nan | 291.82 |
| report_title | object | nan | National Daily Boxed Beef Cutout & Boxed Beef Cuts - Negotiated Sales - PM (PDF) (LM_XB403) |
| slug_name | object | nan | AMS_2453 |
| slug_id | float64 | nan | 2453.0 |
| office_name | object | nan | Des Moines, IA |
| office_code | object | nan | LS-NW |
| office_city | object | nan | Des Moines |
| office_state | object | nan | IA |
| market_location_name | object | nan | Des Moines, IA |
| market_location_city | object | nan | Des Moines |
| market_location_state | object | nan | IA |
| market_type | object | nan | Direct Livestock - LMR Beef |
| market_type_category | object | nan | Direct Livestock - LMR Beef |
| published_date | object | nan | 01/02/2019 14:59:12 |
| grade | object | nan | Choice |
| trim_description | float64 | nan | nan |
| total_volume_kg | float64 | nan | 56405.98 |
| price_range_low_USD_kg | float64 | nan | 6.1729 |
| price_range_high_USD_kg | float64 | nan | 6.8343 |
| weighted_average_USD_kg | float64 | nan | 6.4335 |

#### `samgyup_model_features.csv`
- **총 행(Row) 수**: 약 53행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-03-01 |
| samgyup | float64 | 6368.0 | 6260.0 |
| usda_plate | float64 | 3.440809090909091 | 3.652428571428571 |
| fx | float64 | nan | nan |
| import_yj | float64 | 2834.0 | 4493.0 |
| stock_yj | float64 | 16183.0 | 17437.0 |
| fas_china | float64 | 37.0 | 315.0 |
| fas_korea | float64 | 850.0 | 16383.0 |
| cof_inventory | float64 | 14367900.0 | 11785000.0 |
| cof_placements | float64 | 1964000.0 | 2011000.0 |
| us_soybean_meal | float64 | 344.7295 | 337.617 |
| kr_ppi_food | float64 | 98.7 | 98.67 |
| kr_cpi_food | float64 | 95.789 | 95.508 |
| us_wti | float64 | 51.505 | 58.04451612903225 |
| kr_base_rate | float64 | 1.75 | 1.75 |
| kr_temp_avg | float64 | 1.4219354838709677 | 8.636774193548387 |
| kr_precip | float64 | 0.26 | 1.229032258064516 |

#### `samgyup_unified_monthly.csv`
- **총 행(Row) 수**: 약 70행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2016-12-01 | 2017-01-01 |
| price_won_per_kg | float64 | 5200.0 | 5467.0 |
| source | object | dealer | dealer |
| n_obs | int64 | 4 | 6 |

#### `usda_plate_usd_kg.csv`
- **총 행(Row) 수**: 약 1937행

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
| USDA_Code | object | 123A | 114D |
| Original_Description | object | Short Plate, short rib (123A  3) | Chuck, clod, top blade (114D  3) |
| Korean_Name | object | LA갈비-미국 | 부채살-미국 |
| Status | object | 정상 | 정상 |
| Note | object | Master 품목명과 연결 가능 | Master 품목명과 연결 가능 |

### 폴더: `2_dashboard/`

#### `dashboard_ready_data.csv`
- **총 행(Row) 수**: 약 66318행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2026-08-11 | 2025-01-22 |
| category | object | 미국 | 미국 |
| part | object | BBQ등갈비 | BBQ등갈비 |
| brand | object | 엑셀(86K) | 엑셀(86R) |
| wholesale_price | float64 | 10760.0 | 10380.0 |
| ma7 | float64 | nan | nan |
| ma30 | float64 | nan | nan |
| min_total | float64 | 10760.0 | 9860.0 |
| max_total | float64 | 10760.0 | 12380.0 |

#### `data_status.csv`
- **총 행(Row) 수**: 약 15행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 데이터 | object | 미트박스 시세 | USDA 부위시세 |
| 소스 | object | 미트박스 | USDA |
| 주기 | object | 일 | 일 |
| 최신데이터 | object | 2026-08-10 | 2026-08-03 |
| 지연(일) | int64 | 0 | 7 |
| 상태 | object | 최신 | 최신 |

#### `fas_supply_signal.csv`
- **총 행(Row) 수**: 약 91행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-02-01 |
| china_exp | int64 | 37 | 782 |
| korea_exp | int64 | 850 | 26773 |
| china_vs_med | float64 | nan | nan |
| korea_vs_med | float64 | nan | nan |
| alert_level | int64 | 0 | 0 |
| note | object | 정상 | 정상 |

#### `hanwoo_dashboard_ready.csv`
- **총 행(Row) 수**: 약 73135행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-30 | 2019-03-01 |
| source | object | ekape_auction | ekape_auction |
| grade | int64 | 1 | 1 |
| sex | object | 전체 | 전체 |
| market_code | object | Center | Center |
| market_name | object | Center | Center |
| is_national_total | bool | False | False |
| is_regional_total | bool | False | False |
| price_won_per_kg | float64 | 17606.0 | 17606.0 |
| head_count | int64 | 4608 | 2236 |
| part | object | 전체(도체) | 전체(도체) |
| country_name | float64 | nan | nan |
| ma7 | float64 | nan | nan |
| ma30 | float64 | nan | nan |

#### `macro_dashboard_ready.csv`
- **총 행(Row) 수**: 약 2780행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2019-01-01 | 2019-01-02 |
| kr_base_rate | float64 | 1.75 | 1.75 |
| kr_ccsi | float64 | 98.3 | 98.3 |
| kr_cpi_beef_dom | float64 | 91.195 | 91.195 |
| kr_cpi_beef_imp | float64 | 96.731 | 96.731 |
| kr_cpi_food | float64 | 95.789 | 95.789 |
| kr_cpi_pork | float64 | 84.205 | 84.205 |
| kr_cpi_total | float64 | 98.884 | 98.884 |
| kr_esi | float64 | 92.6 | 92.6 |
| kr_ppi_food | float64 | 98.7 | 98.7 |
| kr_precip | float64 | 0.02 | 0.0 |
| kr_retail_cvs | float64 | 98.6 | 98.6 |
| kr_retail_dept | float64 | 112.4 | 112.4 |
| kr_retail_hypermarket | float64 | 101.1 | 101.1 |
| kr_service_food | float64 | 120.8 | 120.8 |
| kr_temp_avg | float64 | -1.46 | -1.52 |
| kr_temp_max | float64 | 2.28 | 3.58 |
| us_corn | float64 | 166.8462 | 166.8462 |
| us_food_ppi | float64 | 206.2 | 206.2 |
| us_soybean | float64 | 333.7771 | 333.7771 |
| us_soybean_meal | float64 | 344.7295 | 344.7295 |
| us_wti | float64 | nan | 46.31 |
| kr_base_rate_yoy_pct | float64 | nan | nan |
| kr_ccsi_yoy_pct | float64 | nan | nan |
| kr_cpi_beef_dom_yoy_pct | float64 | nan | nan |
| kr_cpi_beef_imp_yoy_pct | float64 | nan | nan |
| kr_cpi_food_yoy_pct | float64 | nan | nan |
| kr_cpi_pork_yoy_pct | float64 | nan | nan |
| kr_cpi_total_yoy_pct | float64 | nan | nan |
| kr_esi_yoy_pct | float64 | nan | nan |
| kr_ppi_food_yoy_pct | float64 | nan | nan |
| kr_precip_yoy_pct | float64 | nan | nan |
| kr_retail_cvs_yoy_pct | float64 | nan | nan |
| kr_retail_dept_yoy_pct | float64 | nan | nan |
| kr_retail_hypermarket_yoy_pct | float64 | nan | nan |
| kr_service_food_yoy_pct | float64 | nan | nan |
| kr_temp_avg_yoy_pct | float64 | nan | nan |
| kr_temp_max_yoy_pct | float64 | nan | nan |
| us_corn_yoy_pct | float64 | nan | nan |
| us_food_ppi_yoy_pct | float64 | nan | nan |
| us_soybean_yoy_pct | float64 | nan | nan |
| us_soybean_meal_yoy_pct | float64 | nan | nan |
| us_wti_yoy_pct | float64 | nan | nan |

#### `meatbox_universe.csv`
- **총 행(Row) 수**: 약 28행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| part | object | 척리블렛 | 삼겹양지(조각) |
| n_days | int64 | 513 | 391 |
| coverage_pct | int64 | 90 | 69 |
| recent_days | int64 | 38 | 2 |
| max_gap | int64 | 1 | 81 |
| start | object | 2025-01-23 | 2025-01-22 |
| tier | int64 | 0 | 0 |
| status | object | 제외(거래끊김) | 제외(거래끊김) |

#### `samgyup_feature_importance.csv`
- **총 행(Row) 수**: 약 15행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| feature | object | stock_yj | kr_cpi_food |
| std_coef | float64 | -0.71 | 0.288 |

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
| part | object | 황제늑간 | 갈비살/늑간살 |
| tier | int64 | 1 | 1 |
| current_price | int64 | 21558 | 26148 |
| pct_rank | int64 | 99 | 98 |
| momentum_30d | float64 | 12.7 | 13.2 |
| signal | object | 매도후보(고평가) | 매도후보(고평가) |
| n_obs | int64 | 567 | 567 |

<!-- AUTO-GENERATED-SCHEMA:END -->
