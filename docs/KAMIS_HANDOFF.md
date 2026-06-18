# KAMIS 한우 도·소매가 연동 핸드오프

> KAMIS Open API(한우 부위·등급별 도/소매가) 수집 → 전처리 → 한우 대시보드(06) 반영을 end-to-end 로 구축·검증한 결과.
>
> 관련: [PROJECT_GUIDE.md](PROJECT_GUIDE.md), [DATA_COLLECTION_RULES.md](DATA_COLLECTION_RULES.md) (4-한우 섹션), [MACRO_HANDOFF.md](MACRO_HANDOFF.md)

---

## 0. 결론 요약

- KAMIS 연동 **동작 확인 완료** — 수집·전처리·06 대시보드 모두 정상.
- 수집기/전처리에 **실제 API 응답과 어긋난 버그 4건을 발견·수정**함(아래 §2).
- **KAMIS 일별 API는 과거 한우 부위가격을 거의 제공하지 않음**(과거 일자는 `dpr1=0`). 최근/당일은 실값 제공. → 과거 백필은 희소, **going-forward 일일 수집은 조밀**.

---

## 1. 인증 (.env)

| 키 | 내용 |
|---|---|
| `KAMIS_CERT_KEY` | KAMIS Open-API 인증키 (kamis.or.kr 발급) |
| `KAMIS_CERT_ID` | **KAMIS 홈페이지 계정 아이디** (별도 발급이 아니라 가입 ID) |

둘 다 **필수**(공식 사양 확인). 비어 있으면 `collect_kamis_hanwoo.py` 자동 skip.

---

## 2. 수정 내역 (실제 API 응답과 불일치하던 부분)

KAMIS `dailyPriceByCategoryList`(부류 500=축산물) 실제 응답 구조:

| 필드 | 값 예시 | 의미 |
|---|---|---|
| `item_name` | `소` | 품목(한우 식별) |
| `kind_name` | `안심`, `등심`, `갈비`, `설도`, `양지` | **부위** |
| `rank` | `1++등급`, `1+등급`, `1등급` | **등급 (별도 필드!)** |
| `unit` | `100g` | 단위 |
| `dpr1` | `18,437` 또는 `0` | 당일가 (`0`=해당일 미제공) |
| `product_cls_code` | `01`(소매) / `02`(도매) | 도/소매 구분 |

수정한 버그:

| # | 파일 | 문제 | 수정 |
|---|------|------|------|
| 1 | `collect_kamis_hanwoo.py` | 사내망 SSL 검사로 `CERTIFICATE_VERIFY_FAILED`(http→https 리다이렉트) | `verify=False` + `urllib3.disable_warnings` (USDA/Macro 수집기와 동일) |
| 2 | `collect_kamis_hanwoo.py` | 등급(`rank`) 필드 미수집 → 등급 정보 유실, dedup 시 부위별 1개로 붕괴 | `rank` 컬럼 저장 + `DUPLICATE_KEYS`에 `rank` 추가 |
| 3 | `preprocess_hanwoo.py` | 부위·등급을 `kind_name`의 `"안심(1++등급)"` 패턴으로 파싱(실제론 없음) → part 전부 "기타", grade "전체" | 부위=`kind_name` 직접, 등급=`rank`(`"1++등급"`→`"1++"`) |
| 4 | `preprocess_hanwoo.py` | `product_cls_code`가 CSV에서 int(1/2)로 읽혀 `"01"/"02"` 매핑 실패 → source 전부 `kamis_unknown` | `astype(str).str.zfill(2)` 후 매핑 |
| 5 | `06_Hanwoo_Dashboard.py` | `import plotly.express` → `xarray`가 NumPy 2.0 제거된 `np.unicode_` 사용 → 페이지 import 크래시 | `plotly.express` 제거, 해당 차트를 `graph_objects`로 대체 |
| 6 | `collect_kamis_hanwoo.py` | 예외 로그에 인증키 포함 URL 노출 위험 | 예외 타입만 출력 |

---

## 3. 데이터 흐름 / 산출물

```
collect_kamis_hanwoo.py  → data/0_raw/kamis_hanwoo_raw.csv
crawl_han_auction_api.py → data/0_raw/han_auction_raw.csv   (EKAPE, 별도)
        │
preprocess_hanwoo.py     → data/1_processed/han_auction_daily.csv (EKAPE 정규화)
                         → data/2_dashboard/hanwoo_dashboard_ready.csv (EKAPE+KAMIS 통합 long)
        │
06_Hanwoo_Dashboard.py   → 섹션 1~4(EKAPE 중심) + 섹션 5(KAMIS 부위별 도·소매)
```

**KAMIS raw 컬럼**: `reg_date, product_cls_code, product_cls_name, item_name, kind_name(부위), rank(등급), unit, country_name, market_name, price`

**대시보드 KAMIS row**: `source`(kamis_retail/kamis_wholesale), `part`(부위), `grade`(1++/1+/1), `price_won_per_kg`(100g→kg 환산, ×10), `ma7`, `ma30`

> 도매(`02`)·소매(`01`) 응답이 동일 값으로 관측됨 — KAMIS 한우 부위육은 사실상 소비자가만 제공하는 것으로 보임. 06 대시보드는 소매/도매 선택 가능하되 기본 소매.

---

## 4. 실행 방법

```powershell
cd D:\Beef_Price_Model
python src/collectors/collect_kamis_hanwoo.py   # 증분 수집 (1회 최대 400일, 키 없으면 skip)
python src/utils/preprocess_hanwoo.py           # EKAPE+KAMIS 통합 → hanwoo_dashboard_ready.csv
# 대시보드: streamlit run src/Home.py  → 06_Hanwoo_Dashboard 섹션 5
```

---

## 5. 데이터 현황 & 백필 전략

- **현재 수집분**: 2019-01-01 ~ 2020-02-04 (1차 400일 청크), raw 12,000행 중 **실값 634행**(나머지는 과거 미제공 `dpr1=0`).
- **백필**: 수집기는 마지막 일자 이후를 1회 400일씩 증분. 2025-06 현재까지 따라잡으려면 **약 6회 반복 실행** 필요(`python src/collectors/collect_kamis_hanwoo.py` 반복).
- **중요**: 과거(2019~2023)는 KAMIS 일별 미제공으로 대부분 비며, **최근 1~2년이 조밀**함. 따라서 백필을 끝까지 돌리면 최근 구간에서 대시보드가 채워짐. going-forward 일일 파이프라인으로는 매일 실값 누적.
- **과거 시계열 깊이가 필요하면**: KAMIS 일별 대신 **기간/월별 API**(예: 품목별 기간 조회)가 과거 데이터를 더 잘 제공 → 별도 수집기로 보강 가능(향후 과제).

---

## 6. 검증 결과

- 수집: 2019-01~2020-02, 실패일 0, `rank`·`unit`·`product_cls_code` 정상 저장
- 전처리: 부위 5종(갈비·등심·설도·안심·양지) × 등급 3종(1++/1+/1), source 도/소매 분리 정상
- 환산: 안심 1++ 소매 2020-02-04 = **114,490원/kg** (100g×10, 2020년 시세로 합리적)
- 06 대시보드: AppTest 헤드리스 실행 — 예외 0, 섹션 1~5 렌더링, 전체기간 시 부위별 metric/차트 정상(안심 114,490·등심 113,370·갈비 70,500·양지 57,120원/kg)

---

## 7. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-17 | KAMIS 연동 end-to-end 구축. 수집기/전처리 버그 4건 + 06 페이지 NumPy2.0 import 이슈 수정, 부위별 도·소매 섹션 추가. 1차 백필(2019-01~2020-02) 및 검증 완료. KAMIS 일별 과거 미제공 특성 문서화 |
