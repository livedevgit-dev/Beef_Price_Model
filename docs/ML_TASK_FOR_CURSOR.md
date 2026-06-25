# ML 작업 지시서 (집 PC / Cursor 실행용)

> 이 문서 하나만 읽고 바로 실행하면 된다. 무거운 ML 학습(xgboost)을 집 PC(GPU)에서 수행하고,
> 산출물을 `data/3_reports/ml/` 에 저장 → 커밋/푸시하면 노트북이 회수해 해석·BI 에 사용한다.

---

## 0. 환경 준비
```bash
git clone https://github.com/livedevgit-dev/Beef_Price_Model.git   # 이미 있으면 git pull
cd Beef_Price_Model
python -m venv venv && venv\Scripts\activate         # (Windows) / mac·linux: source venv/bin/activate
pip install -r requirements.txt                      # xgboost, scikit-learn 포함
```
- API 키 불필요(이미 수집된 데이터로 학습). `.env` 없어도 됨.
- GPU 사용 시 xgboost `tree_method="hist", device="cuda"` 사용 가능(데이터가 작아 CPU도 무방).

## 1. 작업 경계 (충돌 방지 — 반드시 준수)
- **쓰기 허용**: `data/3_reports/ml/`(산출물), `src/Models/`(새 학습 스크립트)
- **수정 금지(읽기만)**: `data/0_raw/`, `data/1_processed/`, `data/2_dashboard/`, 모든 `src/collectors/`, `src/utils/`, `.env`
  - 이유: 데이터 수집·전처리는 노트북 소유. 같은 파일을 양쪽이 쓰면 git 충돌.
- **커밋 대상**: `data/3_reports/ml/` 와 `src/Models/` 의 신규/변경분만. (data/0_raw 등은 `git add` 하지 말 것)

---

## 2. Task A — 삼겹양지 가격 예측 모델

**입력**: `data/1_processed/samgyup_model_features.csv`
- 51개월(2019-01~2026-06), 월별. 타겟 컬럼 `samgyup`(원/kg).
- 피처(13): `usda_plate`(Short Plate 원가 USD/kg), `fx`(환율, 결측 10), `import_yj`(양지 수입), `stock_yj`(양지 재고), `fas_china`/`fas_korea`(미국→중·한 수출), `cof_inventory`/`cof_placements`(사육두수/배치), `us_soybean_meal`, `kr_ppi_food`, `kr_cpi_food`, `us_wti`, `kr_base_rate`

**요구사항**
1. **시계열 검증 필수** — 셔플 금지. walk-forward(expanding window) 또는 TimeSeriesSplit. **반드시 out-of-sample 지표 보고**(in-sample 금지).
2. **누수(leakage) 방지** — 예측 시점에 알 수 없는 동시점 피처는 lag 처리. 선행지표(`cof_placements`, `fas_china`)는 lag(1~6)도 피처로 시험.
3. **베이스라인 대비** — 기존 계절+추세 예측(`data/2_dashboard/samgyup_forecast.csv`)과 OOS 성능 비교. **xgboost가 베이스라인을 못 이기면 솔직히 보고**(소표본이라 가능성 있음).
4. 모델: xgboost 회귀(+규제). 과적합 주의(n≈38 완전행). 필요시 Ridge/Lasso도 비교.

**산출물** → `data/3_reports/ml/`
- `samgyup_pred.csv` : `date, actual, pred, lo, hi`(과거 OOS 예측 + 향후 1~3개월)
- `samgyup_metrics.json` : `{mae, rmse, r2_oos, baseline_mae, n, horizon, note}`
- `samgyup_importance.csv` : `feature, importance`(+ 가능하면 SHAP)

---

## 3. Task B — 부위별 상승 가능성 랭킹 (대체매수 추천)

**입력**: `data/2_dashboard/dashboard_ready_data.csv`
- 미트박스 수입육 27개 부위, 일별 2025-01-22~현재. 컬럼: `date, category, part, brand, wholesale_price, ma7, ma30, min_total, max_total`
- 부위 예: 삼겹양지, 차돌양지, 차돌박이, 부채살, 살치살, 안창살, 아롱사태, 등갈비/백립, 목뼈 등

**요구사항 (사용자 핵심 요청)**
1. 각 부위의 **향후 N개월(예: 1·3개월) 수익률을 예측**해 **상승 가능성 높은 부위를 추천**.
2. **부위별 개별 모델 금지** — 데이터가 1.5년뿐이라 과적합. **전 부위 통합(pooled) 모델 1개**로 학습(표본 확대).
   - 부위별 피처: 모멘텀(1/3개월 수익률), 자기 이력 백분위, 변동성, 월 계절성, `ma7/ma30` 등
   - 공유 피처(선택): 월별로 매핑해 결합 — `data/2_dashboard/fas_supply_signal.csv`, 환율, macro
   - 타겟: 부위별 forward 1·3개월 수익률(%)
3. **시계열 OOS 검증** 필수. 1.5년 한계상 신뢰구간 넓음 → **방향성 스크린으로 해석, 과신 금지** 명시.

**산출물** → `data/3_reports/ml/`
- `cut_upside_ranking.csv` : `part, current_price, pred_return_1m, pred_return_3m, rank, confidence`
- `cut_model_metrics.json` : `{r2_oos, mae, n, note}`

> 참고: 노트북에 이미 "현재 저평가(평균회귀)" 시그널(`switch_signal.csv`)이 있음. B의 "예측 상승률"과 **병행**하면 (예측↑ + 저평가) = 강한 매수. ranking CSV 에 가능하면 `pct_rank`(저평가도)도 join 해 두면 좋음.

---

## 4. 완료 시
1. `data/3_reports/ml/` 의 산출물 + `src/Models/` 신규 스크립트만 커밋:
   ```bash
   git add data/3_reports/ml src/Models
   git commit -m "ml: 삼겹양지 예측(A) + 부위 상승랭킹(B) 산출"
   git push
   ```
2. 무엇을 했는지 1줄 요약 + OOS 성능 + 베이스라인 대비를 커밋 메시지/`metrics.json` 에 남길 것.

## 5. 원칙 (중요)
- **정직하게**: in-sample 자랑 금지. OOS로 평가하고, 신호가 약하면 약하다고 보고.
- **데이터 한계 인지**: 삼겹양지 38개월·부위 1.5년 → 작은 표본. 규제·검증으로 과적합 억제.
- 경계 밖 파일 수정 금지(§1).
