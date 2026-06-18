# Macro(거시·외생변수) 파이프라인 구축 핸드오프

> 수입육 도매가·한우 경락가 예측 ML 용 **거시경제·외생변수 수집 파이프라인** 신규 구축 결과 공유 문서.
> 별도 작업 세션에서 구현했으며, 다른 세션(한우/KAMIS/피처엔지니어링)과의 작업 경계를 명시함.
>
> 관련 문서: [DATA_COLLECTION_RULES.md](DATA_COLLECTION_RULES.md) (4-거시 섹션), [PROJECT_GUIDE.md](PROJECT_GUIDE.md)

---

## 0. 작업 범위

- **이 작업 범위:** 거시지표(Macro)만 — 금리·물가(CPI/PPI)·옥수수·대두·WTI·심리지수·기후
- **미수정 (다른 세션 범위 — 충돌 방지):**
  - 한우 전반: `crawl_han_auction_api.py`, `preprocess_hanwoo.py`, `06_Hanwoo_Dashboard.py`, `hanwoo_*` 데이터
  - KAMIS: `collect_kamis_hanwoo.py`
  - 피처 엔지니어링: `feature_engineering.py`, `feature_engineering_rolling.py`
  - `.env` 실파일, `.gitignore`
  - → 위 파일들은 **일절 수정하지 않음** (읽기만 함)
- **환율(USD/KRW)** 은 기존 `exchange_rate_data.xlsx` 에 있으므로 macro 에서 **중복 수집하지 않음**

---

## 1. 변경·신규 파일 전체

| 구분 | 파일 | 내용 |
|---|---|---|
| 수정 | `src/config.py` | `MACRO_RAW_CSV`, `MACRO_PROCESSED_CSV`, `MACRO_DASHBOARD_CSV` 경로 추가 |
| 수정 | `.env.example` | `FRED_API_KEY`, `ECOS_API_KEY`, `KMA_API_KEY` (이름·발급 URL만, 값 없음) |
| 신규 | `src/collectors/collect_macro_fred.py` | FRED 미국 지표 수집기 |
| 신규 | `src/collectors/collect_macro_ecos.py` | 한국은행 ECOS 국내 지표 수집기 |
| 신규 | `src/collectors/collect_macro_kma.py` | 기상청 ASOS 기후 수집기 |
| 신규 | `src/utils/preprocess_macro.py` | raw→daily(ffill+ma30/yoy/mom)→dashboard 전처리 |
| 신규(선택) | `src/pages/07_Macro_Environment.py` | Streamlit 거시환경 대시보드 |
| 수정 | `src/run_daily_update.py` | `--full` 에 Macro 수집[2-1]·전처리[5-1] 블록(`critical=False`) + GAP 항목 |
| 수정 | `docs/DATA_COLLECTION_RULES.md`, `docs/PROJECT_GUIDE.md` | Macro 섹션·표 갱신 |

---

## 2. 수집 지표 (총 14종, 모두 long format)

### 미국 — FRED (`collect_macro_fred.py`) — 실데이터 수집 완료

| indicator_id | series | 주기 | 용도 |
|---|---|---|---|
| `us_corn` | `PMAIZMTUSDM` | 월 | 옥수수(사료비) |
| `us_soybean` | `PSOYBUSDM` | 월 | 대두(사료비) |
| `us_soybean_meal` | `PSMEAUSDM` | 월 | 대두박(사료 직접 투입재) |
| `us_wti` | `DCOILWTICO` | 일 | WTI 원유(물류·선행) |
| `us_food_ppi` | `WPU02` | 월 | 미국 가공식품 PPI |

### 국내 — ECOS 한국은행 (`collect_macro_ecos.py`) — 실데이터 수집 완료

| indicator_id | 통계표/항목 | 주기 | 용도 |
|---|---|---|---|
| `kr_base_rate` | `722Y001` / `0101000` | 월 | 기준금리 |
| `kr_cpi_food` | `901Y009` / `A` | 월 | 식료품·비주류음료 CPI |
| `kr_cpi_total` | `901Y009` / `0` | 월 | 전체 CPI |
| `kr_ppi_food` | `404Y014` / `301AA` | 월 | 음식료품 PPI |
| `kr_ccsi` | `511Y002` / `FME` | 월 | 소비자심리지수 |
| `kr_esi` | `513Y001` / `E1000` | 월 | 경제심리지수 |

### 기후 — KMA 기상청 ASOS (`collect_macro_kma.py`) — KMA 키 신청 후 동작

| indicator_id | 필드 | 주기 | 용도 |
|---|---|---|---|
| `kr_temp_avg` | `avgTa` | 일 | 평균기온(전국 5개소 평균) |
| `kr_temp_max` | `maxTa` | 일 | 최고기온 |
| `kr_precip` | `sumRn` | 일 | 강수량 |

> 전국 대표 관측소: 서울(108)·부산(159)·대구(143)·광주(156)·대전(133) 일자료의 날짜별 평균.
> 모든 API 코드는 공식 문서 / ECOS `StatisticItemList` API 로 검증 완료. **미해결 항목코드 TODO 없음.**

---

## 3. 산출물 스키마

| 단계 | 파일 | 컬럼 |
|---|---|---|
| Raw | `data/0_raw/macro_indicators_raw.csv` | `date, country, indicator_id, indicator_name, value, unit, freq, source` |
| Processed | `data/1_processed/macro_indicators_daily.csv` | 위 + `ma30, yoy_pct, mom_pct` (일별 ffill) |
| Dashboard | `data/2_dashboard/macro_dashboard_ready.csv` | wide(`date` × 지표값 + `_yoy_pct`), 가격 데이터와 `date` merge |

- `country`: `US` / `KR`, `source`: `FRED` / `ECOS` / `KMA`
- 월별 지표 date = `YYYY-MM-01` 통일 / 일별은 관측일 그대로
- 히스토리 시작 **2019-01-01**, 증분 수집, dedup 키 `(date, country, indicator_id)`
- ffill 정책: 금리·물가는 다음 발표 전까지 값 유지(limit 없음) — 가격 ffill(limit=7)과 다름
- 현재 데이터(KMA 제외 상태): raw 2,747행 / processed 29,975행(11종) / dashboard 2,725행 × 22열

---

## 4. 실행 방법

```powershell
cd D:\Beef_Price_Model
# 개별 수집 (키 없으면 각 수집기 자동 skip)
python src/collectors/collect_macro_fred.py
python src/collectors/collect_macro_ecos.py
python src/collectors/collect_macro_kma.py
python src/utils/preprocess_macro.py           # raw -> daily + dashboard
# 통합 (Macro 포함, critical=False — 실패해도 기존 파이프라인 유지)
python src/run_daily_update.py --full
python src/run_daily_update.py --gap-check      # GAP 리포트에 '거시지표(Macro)' 항목 포함
```

---

## 5. API 키 현황

| 키 | 발급처 | 상태 |
|---|---|---|
| `FRED_API_KEY` | https://fredaccount.stlouisfed.org/apikeys | 입력·동작 확인 |
| `ECOS_API_KEY` | https://ecos.bok.or.kr/api/ | 입력·동작 확인 |
| `KMA_API_KEY` | https://www.data.go.kr/data/15059093/openapi.do | 신청 필요 (**Decoding 인증키** 사용) |

KMA 키 신청: data.go.kr 로그인 → 해당 서비스 "활용신청"(즉시 승인) → 마이페이지 → **일반 인증키(Decoding)** 복사 → `.env` 의 `KMA_API_KEY=` 에 입력. (활용신청 직후 키 적용까지 수십 분 지연 가능)

---

## 6. 환경 이슈 & 처리 (중요)

1. **사내망 SSL 검사** — 사내망 SSL 중간 프록시로 `CERTIFICATE_VERIFY_FAILED` 발생. `truststore` 는 이 Anaconda 환경과 충돌(RecursionError)하여, 기존 `collect_usda_primal.py` 와 동일한 **`verify=False` + `urllib3.disable_warnings`** 패턴으로 통일함 (3개 macro 수집기 모두 적용).
2. **API 키 로그 노출 방지** — requests 예외 메시지에 키 포함 URL 이 출력되던 문제 수정(예외 타입만 출력). 단, 초기 디버깅 중 FRED·ECOS 키가 로그에 1회 노출되었으므로 **해당 두 키 재발급 권장**(무료, 5분).
3. **KMA 키 인코딩** — requests 가 자동 URL 인코딩하므로 반드시 **Decoding(일반) 인증키** 사용(Encoding 키는 이중 인코딩되어 실패).

---

## 7. 검증 결과 (값 정합성)

- `kr_base_rate`: 2019=1.75 → 2020 코로나 0.5 → 2023 3.5 → 현재 2.5 — **실제 기준금리 이력 완벽 일치**
- `us_wti`: 최저 -36.98(2020.4 마이너스 유가) ~ 123.64 — 정확
- `kr_cpi_food`(126.79) > `kr_cpi_total`(119.92) — 식품 물가가 더 가파른 실제 패턴과 일관
- `kr_ccsi` 106.1, 대두 439 / 대두박 322 USD/MT 등 전 지표 합리성 확인
- 전 파일 `py_compile` 통과, 키 미설정 시 정상 graceful skip

---

## 8. 남은 작업 / 향후 제안

**미해결 TODO: 없음** (ECOS 항목코드 전부 검증 완료)

**향후 확장 (ML / 다른 세션 영역과 조율 필요):**

- 유가(WTI) **lag 피처**(30/60/90일), **계절성·명절 더미** → `feature_engineering.py` 영역 (이 세션 미수정)
- **외식물가** CPI — `901Y009` 에 없음(별도 지출목적별 표), 추후 옵션
- **질병 플래그**(ASF·구제역·조류인플루엔자) — 가격 급변 설명력 큼
- Tier2: USDA NASS(Cattle on Feed·Slaughter), 통계청 지표 등
- **과적합 주의**: 월별 관측치 ~89개 → 변수 다수 투입 시 허위상관·다중공선성. "넓게 수집, 피처선택(L1/SHAP)으로 좁게 사용 + walk-forward 검증" 원칙 권장

---

## 9. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-17 | Macro 파이프라인 구축 — FRED/ECOS/KMA 수집기, 전처리, run_daily_update 통합, docs. 14종 지표(FRED 5 + ECOS 6 + KMA 3), ECOS 항목코드 검증 완료 |
