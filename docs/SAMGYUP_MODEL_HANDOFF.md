# 삼겹양지 예측·공급경보·전환시그널 핸드오프

> 수입육 삼겹양지(미국산 Short Plate) 가격 예측을 위한 데이터 수집 → 피처 통합 → 예측·영향력 → BI 구축 결과.
> 관련: [DATA_PIPELINE_OVERVIEW.md](DATA_PIPELINE_OVERVIEW.md), [KAMIS_HANDOFF.md](KAMIS_HANDOFF.md), [MACRO_HANDOFF.md](MACRO_HANDOFF.md)

---

## 0. 한눈에
- 삼겹양지 가격을 **미·중/한 수출, 재고, 원가, 환율, 사육두수, 거시**와 결합해 예측·해석·시그널화.
- **2025 덤핑 사태(미→중 수출 급감→한국 다이버전→가격 하락)를 FAS 데이터로 확증**, 재발 조기경보 자동화.
- BI 페이지(08)에서 예측·경보·영향력·품목전환을 한 화면에 표출.

## 1. 신규 데이터 수집기 (무료 키)
| 수집기 | 데이터 | 키 | 산출 |
|---|---|---|---|
| `collect_fas_export_sales.py` | 미국→중국/한국 소고기 주간 수출 (덤핑 경보) | `FAS_API_KEY` | `0_raw/fas_export_sales_raw.csv` |
| `collect_cattle_on_feed.py` | 미국 사육두수·배치·도축출하 (공급 4~6개월 선행) | `NASS_API_KEY` | `0_raw/us_cattle_on_feed.csv` |

- FAS: base `https://api.fas.usda.gov/api/esr`, 인증 `?api_key=`(실호출 검증). 상품(beef 1701)·국가(중국 5700/한국 5800) 런타임 조회.
- NASS: `https://quickstats.nass.usda.gov/api/api_GET/`, 시리즈 `CATTLE, ON FEED - INVENTORY/PLACEMENTS/SALES FOR SLAUGHTER`.
- 둘 다 키 없으면 graceful skip, `verify=False`(사내망), `run_daily_update --full`에 통합.

## 2. 분석·예측 파이프라인
```
build_samgyup_series.py  → 1_processed/samgyup_unified_monthly.csv   (미트박스2025+ + 도매상2016~ 통합)
preprocess_fas_signal.py → 2_dashboard/fas_supply_signal.csv         (월별 중국/한국 + 경보등급)
build_samgyup_model.py   → 1_processed/samgyup_model_features.csv     (월별 통합 피처 13종, xgboost 학습용)
                         → 2_dashboard/samgyup_forecast.csv           (계절+추세 예측 + 밴드)
                         → 2_dashboard/samgyup_feature_importance.csv (표준화 릿지 영향력)
build_switch_signal.py   → 2_dashboard/switch_signal.csv              (부위별 상대가치 매도/매수)
```
모두 `run_daily_update --full` [5-2] 단계에 포함(critical=False).

## 3. 핵심 분석 결과 (현재 데이터 기준)
**변수 영향력 (표준화 릿지, R²=0.88, n=38)** — 방향성 해석용(소표본·다중공선성 주의):
| 변수 | 계수 | 해석 |
|---|---|---|
| 재고(양지) | **-0.69** | 재고↑ → 가격↓ (가장 강함) |
| CPI 식품 | +0.34 | 물가 동행 |
| **FAS 중국수출** | +0.26 | 중국이 미국산 사가면 한국 가격↑(다이버전 감소) |
| 환율 | +0.19 | 원화 약세 → 가격↑ |

**예측(계절+추세, 2026 하반기)**: 7월 ~9,600 → 8~10월 ~10,000~10,250 → 11~12월 ~9,500~9,800. 밴드 ±~800. 하반기 평균 ≈ 1만원.

**공급 경보(FAS)**: 2026-06 **정상**(미→중 수출 재개, 한국행 낮음 → 공급압력 완화, 가격 우호적).

## 4. BI — 페이지 08 (Samgyup Forecast)
4개 섹션: ① 가격 예측(실측+예측밴드) ② 공급 조기경보(중국/한국 수출 + 경보등) ③ 변수 영향력 ④ 품목 전환 시그널(대체 매수). `streamlit run src/Home.py` → 08. AppTest 헤드리스 검증 통과(예외 0).

## 5. 한계 (솔직히)
- 삼겹양지 과거가 단일 도매상·희소 → 표본 38~51개월. 예측은 **계절+추세 기반**이며, 드라이버는 **해석(영향력)**에 사용(미래값 미확보로 점예측엔 직접 미투입).
- 릿지 R²=0.88은 in-sample → 과대평가 가능. 강한 확증 금지.
- 무거운 ML(xgboost)은 이 PC(numpy2.x)에서 미동작 → **집 PC에서 `samgyup_model_features.csv`로 학습** 권장.

## 6. 변경 이력
| 날짜 | 내용 |
|------|------|
| 2026-06-23 | FAS·Cattle on Feed 수집기, 삼겹양지 통합·피처·예측·영향력·전환시그널, BI 08 페이지, run_daily --full 통합 |
