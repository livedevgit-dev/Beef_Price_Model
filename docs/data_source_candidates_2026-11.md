# 추가 데이터 소스 검증 (2026-11-09 실측)

미국(·호주) 수입 쇠고기 관련, 아직 수집하지 않는 공개 소스를 실제 호출로 확인한 결과. 사내 프록시 때문에 Python 에서는 `verify=False`(기존 수집기와 동일 패턴)가 필요하다.
"기존 키"는 `.env` 의 EKAPE_API_KEY(data.go.kr 공용), FAS_API_KEY, NASS_API_KEY 를 뜻한다.

## 우선순위 (가치 대비 노력)

| 순위 | 소스 | 새로 얻는 것 | 이력 | 지연 | 키 | 난이도 |
|---|---|---|---|---|---|---|
| 1 | 관세청 품목별 국가별 수출입실적 (data.go.kr 15100475) | 국가×냉장/냉동×HSK10(갈비 `0202201000` / 기타 `0202209000` / 뼈없음 `0202300000`) 월별 kg·USD → CIF 단가. 호주 0201+0202 누적으로 세이프가드 소진율 자체 산출 | 1995~ | 5~6주 (매월 15일경 전월분) | 기존 | 쉬움 |
| 2 | USDA FAS GATS OpenData `censusExports` | 미국 측 HS10 FOB 단가·물량 (0202306000 냉동 뼈없음, 0202206000 냉동 뼈있음, 0201306090 냉장 뼈없음 등). 선적 기준이라 관세청보다 약 1개월 선행 | 1995~ | ~35일 | 기존 FAS 키 (`X-Api-Key`) | 쉬움 |
| 3 | AMS Datamart 추가 리포트 2459 LM_XB455(선도 22~90일 인도), 2465 LM_XB463(전체 거래유형) | 선도 거래가 = 선행 신호. 기존 2453 수집기 패턴 재사용 | 2005~ 추정 | 당일 | 없음 | 쉬움 |
| 4 | CME 생우·비육우 선물 (Yahoo `LE=F`, `GF=F`) | 유일한 forward-looking 시장가 | 2001~ | 당일 | 없음 | 쉬움 |
| 5 | NASS Quick Stats Cold Storage(냉동 쇠고기 재고)·주간 도축 두수 | 미국 공급 펀더멘털 | 1917~ / 주간 | ~23일 / ~12일 | 기존 NASS 키 | 쉬움 |
| 6 | 식약처 식품안전나라 I2780 수입쇠고기 냉동전환 정보 | 냉장→냉동 전환량(냉장 미국산 재고 압박 지표), 부위명·수입업체 | 미확인 | 7일 내 증분 | 무료 키 **신규 발급 필요** | 중간 |

## 엔드포인트 메모

- 관세청: `https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList?serviceKey=…&strtYymm=YYYYMM&endYymm=YYYYMM&cntyCd=US&hsSgn=0202` (XML). 조회창 **1년 이내**(초과 시 resultCode=99) → 연도별 루프. hsSgn 2/4/6/10자리 허용, 4자리 요청 시 6자리 하위 행, 6자리 요청 시 10자리 행. 필드 year, hsCd, statKor, impWgt(kg), impDlr(USD), expWgt, expDlr.
  검증값: 2025 미국 0202201000 74,127t / $680M(≈$9.17/kg), 2026-09 호주 0202300000 10,136t / $80.1M($7.90/kg).
- GATS: `https://api.fas.usda.gov/api/gats/censusExports/partnerCode/KS/year/2026/month/9`, 헤더 `X-Api-Key`. **한국 코드는 `KS`**(`KR` 아님). 필드 date, hS10Code, quantity1(kg), value(USD). 공개 일정 `census/data/exports/dataReleaseDates`. `apps.fas.usda.gov/OpenData` 호스트는 403/500.
  검증값: 2026-09 0202306000 $8.34/kg, 0201306090 $15.47/kg.
- ERS 월별 무역 CSV(무인증, 지육환산, 1989~): `https://www.ers.usda.gov/media/29544/beef-and-veal-monthly-us-trade-carcass-weight-1000-pounds.csv` — GATS 와 중복, 검증용.
- UN Comtrade preview(무키): `https://comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode=410&period=202506&cmdCode=020230&partnerCode=842&flowCode=M` — 관세청과 kg·USD 일치, 백업·검증용.
- Yahoo: `https://query1.finance.yahoo.com/v8/finance/chart/LE=F?range=5d&interval=1d` (JSON).
- NASS: `…/api_GET/?key=…&commodity_desc=BEEF&statisticcat_desc=STOCKS&year=2026&format=JSON` (short_desc `BEEF, COLD STORAGE, FROZEN - STOCKS, MEASURED IN LB`), 도축 `commodity_desc=CATTLE&statisticcat_desc=SLAUGHTERED&freq_desc=WEEKLY&agg_level_desc=NATIONAL`. `sector_desc` 필터 추가 시 invalid query.
- 식약처 I2780: `http://openapi.foodsafetykorea.go.kr/api/{keyId}/I2780/xml/1/1000` — 필드 ORGNP_NM, PRDLST_NM, FREEZING_CNVRS_WT(kg), APLC_DTM, BSSH_NM, CHNG_DT. 1,000행/호출, 100회/시간.

## 확인했으나 제외

- **삼겹양지(뼈없는 short plate/navel)의 USDA 공식 컷 시세는 없다.** LM_XB403 Choice Cuts 42품목에 123A(뼈있는 short rib)·130·120·116A 는 있으나 navel 은 없고, 쇠고기 "export" 리포트도 없음(돈육만). 수집 중인 `Primal Plate` 복합가격이 유일한 공식 대리값.
- 축산물품질평가원(ekapepia 다봄 v3)·data.go.kr 15057912/15000577/15148888: 수입육 **부위별 도매가 장기 시계열 없음**(수입물량&가격은 관세청 재가공, 소비자가만 있음). 미트박스가 유일한 도매가 소스.
- KMTA 주간판매동향: 회원 전용(비밀번호 팝업). 해외시세는 대부분 0.
- USMEF: PDF 만. DAFF 호주 수출통계: 접속 timeout(지역 차단 추정), 세이프가드 공식 트래커 없음 → 관세청 자료(1번)로 자체 산출.
- US Census API 직접 호출은 별도 키 필요 — GATS 가 같은 데이터를 기존 키로 제공하므로 불필요.
