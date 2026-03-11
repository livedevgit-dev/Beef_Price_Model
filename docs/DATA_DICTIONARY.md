# DATA DICTIONARY — Beef Price Model

> **최종 갱신일**: 2026-03-11  
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
