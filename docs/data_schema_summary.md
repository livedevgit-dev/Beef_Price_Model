# 프로젝트 데이터 스키마 요약
이 문서는 데이터 폴더 내 파일들의 구조를 자동으로 분석한 결과입니다.

## 폴더: 0_raw
### 파일명: `beef_import_data_fast.xlsx`
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

---

### 파일명: `beef_price_data.xlsx`
- **총 행(Row) 수**: 약 120행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2025-12-22 | 2025-12-22 |
| 품목명 | object | 갈비살/늑간살-미국 / IBP(245L) | 갈비살/늑간살-미국 / 오로라 앵거스 비프(788) |
| 원산지 | object | 미국 | 미국 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 24580 | 22700 |

---

### 파일명: `beef_price_raw_FULL.xlsx`
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

---

### 파일명: `beef_price_raw_latest.xlsx`
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

---

### 파일명: `beef_primal_cut_prices.xlsx`
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

---

### 파일명: `beef_Short Plate_wholesale_price.xlsx`
- **총 행(Row) 수**: 약 361행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 상  품    원  장 | object | nan | 상품명: |
| Unnamed: 1 | object | nan | 미국산 |
| Unnamed: 2 | object | nan | nan |

---

### 파일명: `beef_stock_data.xlsx`
- **총 행(Row) 수**: 약 1069행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준년월 | object | 2019-01 | 2019-01 |
| 부위별 부위별 | object | 안심 | 등심 |
| 조사재고량 조사재고량 | int64 | 590 | 18617 |
| 대비(%) 전월 | int64 | 0 | 0 |
| 대비(%) 전년 | int64 | 0 | 0 |

---

### 파일명: `exchange_rate_data.xlsx`
- **총 행(Row) 수**: 약 1514행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| Date | object | 2020-01-02 | 2020-01-03 |
| Close | float64 | 1159.0 | 1167.5 |

---

### 파일명: `found_missing_ids.xlsx`
- **총 행(Row) 수**: 약 8행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2026-01-22 | 2026-01-22 |
| 품목명 | object | 관심상품 등록하기 삼겹양지-호주  | 관심상품 등록하기 홍두깨-호주  |
| 원산지 | object | 호주 | 호주 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 0 | 0 |
| siseSeq | int64 | 43569155 | 43558120 |

---

### 파일명: `manual_kor_price.csv`
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

---

### 파일명: `master_import_volume.csv`
- **총 행(Row) 수**: 약 170행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| std_date | object | 2026-01 | 2026-01 |
| 구분 | object | 미국 | 호주 |
| 부위별_갈비_합계 | int64 | 6421 | 3504 |
| 부위별_등심_합계 | int64 | 54 | 1824 |
| 부위별_목심_합계 | int64 | 1288 | 720 |
| 부위별_사태_합계 | int64 | 8 | 509 |
| 부위별_설도_합계 | int64 | 4 | 1166 |
| 부위별_안심_합계 | int64 | 2 | 24 |
| 부위별_앞다리_합계 | int64 | 1099 | 2326 |
| 부위별_양지_합계 | int64 | 3827 | 2365 |
| 부위별_우둔_합계 | int64 | 0 | 1708 |
| 부위별_채끝_합계 | int64 | 3 | 44 |
| 부위별_기타_합계 | int64 | 0 | 2040 |
| 부위별_계_합계 | int64 | 12706 | 16230 |

---

### 파일명: `meatbox_id_list.xlsx`
- **총 행(Row) 수**: 약 150행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2026-01-22 | 2026-01-22 |
| 품목명 | object | 갈비살/늑간살-미국 / IBP(245L) | 갈비살/늑간살-미국 / 엑셀(ESA/앵거스)(86K(EXCEL/ESA)) |
| 원산지 | object | 미국 | 미국 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 24580 | 22340 |
| siseSeq | int64 | 43567223 | 43568980 |

---

### 파일명: `meatbox_raw_full_rows.xlsx`
- **총 행(Row) 수**: 약 617행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| page | int64 | 1 | 1 |
| visible_text | float64 | nan | nan |
| raw_html | object | <tr> 						<th>FAMILY</th> 						<td>없음</td> 						<td>없음</td> 					</tr> | <tr> 						<th>SILVER</th> 						<td>분기 중 월 1회 <br> 이상 구매</td> 						<td>1천원 쿠폰<br> X 1장</td> 					</tr> |

---

### 파일명: `meatbox_sise_43084139.xlsx`
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

---

### 파일명: `raw_food_safety_data.csv`
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

---

### 파일명: `raw_meatbox_2026-01-26.xlsx`
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

---

### 파일명: `raw_meatbox_20260126.csv`
- **총 행(Row) 수**: 약 180행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 품목명 | object | 갈비살/늑간살-미국 / IBP(245L) | 갈비살/늑간살-미국 / 엑셀(ESA/앵거스)(86K(EXCEL/ESA)) |
| 보관 | object | 냉동 | 냉동 |
| 도매시세_raw | object | 24,580 원  - | 22,340 원  - |
| 원산지 | object | 미국 | 미국 |
| 도매시세 | int64 | 24580 | 22340 |

---

### 파일명: `usda_beef_history.csv`
- **총 행(Row) 수**: 약 156778행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 02/19/2026 | 02/19/2026 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| item_description | object | Brisket, deckle-off, bnls (120  1) | Brisket, point/off, bnls (120A  3) |
| number_trades | float64 | 34.0 | nan |
| total_pounds | object | 464,798 | nan |
| price_range_low | float64 | 398.3 | nan |
| price_range_high | float64 | 458.0 | nan |
| weighted_average | float64 | 407.14 | nan |
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
| published_date | object | 02/19/2026 15:39:53 | 02/19/2026 15:39:53 |
| grade | object | Choice | Choice |
| trim_description | float64 | nan | nan |

---

### 파일명: `usda_choice_cuts_02112026.csv`
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

---

### 파일명: `usda_choice_cuts_history.csv`
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

---

### 파일명: `usda_primal_history.csv`
- **총 행(Row) 수**: 약 12796행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 12/31/2019 | 12/31/2019 |
| narrative | float64 | nan | nan |
| trend | float64 | nan | nan |
| primal_desc | object | Primal Rib | Primal Chuck |
| choice_600_900 | float64 | 336.99 | 173.02 |
| select_600_900 | float64 | 320.94 | 169.4 |
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
| published_date | object | 12/31/2019 14:44:22 | 12/31/2019 14:44:22 |

---

### 파일명: `usda_primal_values_02112026.csv`
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

---

### 파일명: `usda_raw_20260212.csv`
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

---

### 파일명: `us_beef_parts_import_daily.csv`
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

---

### 파일명: `미국산소고기_2019_2024_Total.csv`
- **총 행(Row) 수**: 약 749행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 년월 | object | 2019-01 | 2019-01 |
| 부위 | object | 갈비 | 등심 |
| 중량 | float64 | 6930137.81 | 379739.77 |

---

### 파일명: `미국산소고기_202412_202511.csv`
- **총 행(Row) 수**: 약 121행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 년월 | object | 2025-01 | 2025-01 |
| 부위 | object | 갈비 | 등심 |
| 중량 | float64 | 6043215.33 | 23446.39 |

---

## 폴더: 1_processed
### 파일명: `beef_price_history.xlsx`
- **총 행(Row) 수**: 약 2691행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| 기준일자 | object | 2025-12-22 | 2025-12-22 |
| 품목명 | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 엑셀(86R) |
| 원산지 | object | 미국 | 미국 |
| 보관 | object | 냉동 | 냉동 |
| 도매시세 | int64 | 11180 | 11180 |

---

### 파일명: `clean_price_data.csv`
- **총 행(Row) 수**: 약 440행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-12-22 | 2025-12-22 |
| part_name | object | 갈비 | 갈비본살 |
| country | object | 국산(한우암소) | 미국 |
| brand | object | 동명F&B | IBP |
| wholesale_price | int64 | 17580 | 37030 |

---

### 파일명: `dashboard_ready_data.csv`
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

---

### 파일명: `master_price_data.csv`
- **총 행(Row) 수**: 약 49661행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-22 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 오마하(960A) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10390.0 |
| brand | object | - | - |

---

### 파일명: `master_price_data_backup.csv`
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

---

### 파일명: `master_price_data_backup_full.csv`
- **총 행(Row) 수**: 약 49634행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | object | 2025-01-22 | 2025-01-22 |
| part_name | object | BBQ등갈비-미국 / 엑셀(86R) | BBQ등갈비-미국 / 오마하(960A) |
| country | object | 미국 | 미국 |
| wholesale_price | float64 | 10380.0 | 10390.0 |
| brand | object | - | - |

---

### 파일명: `monthly_master_data.xlsx`
- **총 행(Row) 수**: 약 532행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| date | datetime64[ns] | 2024-12-01 00:00:00 | 2024-12-01 00:00:00 |
| avg_price | int64 | 9930 | 9930 |
| avg_exchange | float64 | 1441.7 | 1441.7 |
| import_vol | object | 미국 | 미국 |
| stock_vol | object | 안심 | 등심 |

---

### 파일명: `processed_usda_cost.csv`
- **총 행(Row) 수**: 약 157568행

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

---

### 파일명: `usda_plate_usd_kg.csv`
- **총 행(Row) 수**: 약 1822행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| report_date | object | 2019-01-02 | 2019-01-03 |
| primal_desc | object | Primal Plate | Primal Plate |
| choice_usd_per_kg | float64 | 3.4039 | 3.4313 |
| select_usd_per_kg | float64 | 3.4039 | 3.4313 |

---

### 파일명: `validation_mapping_result.csv`
- **총 행(Row) 수**: 약 42행

| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |
|---|---|---|---|
| USDA_Code | float64 | nan | nan |
| Korean_Name | object | Unmapped | Unmapped |
| Status | object | ⚠️ 매핑 제외 | ⚠️ 매핑 제외 |
| Original_Description | object | Rib, ribeye, lip-on, bn-in (109E  1) | Chuck, semi-bnls, neck/off (113C  1) |
| Note | object | 분석 대상 아님 (필요 시 규칙 추가) | 분석 대상 아님 (필요 시 규칙 추가) |

---

