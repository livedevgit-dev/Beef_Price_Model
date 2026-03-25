# Beef Price Model - 프로젝트 구조 정리 제안서

> 작성일: 2026-03-03
> 최종 갱신일: 2026-03-25
> 목적: 현재 구조 파악 및 리팩토링/정리 방안 정의
> 상태: Phase 1 완료, Phase 2 완료, Phase 3–5 미착수

---

## 1. 현재 구조 요약

### 1.1 디렉터리 구조

```
Beef_Price_Model/
├── .env                      # API 키 (USDA_API_KEY 등)
├── README.md
├── requirements.txt
├── setup_project.py          # 초기 스캐폴드 (2_final 등 사용 안 하는 폴더 생성)
├── src/
│   ├── Home.py               # Streamlit 진입점
│   ├── run_daily_update.py   # 일일 파이프라인 (Meatbox + preprocess만)
│   ├── collectors/           # 데이터 수집기 (9개)
│   ├── utils/                # 전처리/유틸 (6개)
│   ├── pages/                # 대시보드 페이지 (4개)
│   └── z_archive/            # 아카이브 (33개 스크립트)
└── data/
    ├── 0_raw/                # 원시 데이터
    ├── 1_processed/          # 1차 가공 데이터
    └── 2_dashboard/          # 대시보드용 최종 데이터
```

### 1.2 데이터 흐름

```
[Collectors] → 0_raw / 1_processed
       ↓
[Utils]      → 1_processed / 2_dashboard
       ↓
[Pages]      → 대시보드 시각화
```

**핵심 파이프라인 (run_daily_update):**
```
crawl_imp_price_meatbox → master_price_data.csv
                              ↓
preprocess_meat_data    → dashboard_ready_data.csv
```

**미통합 수집기 (수동 실행):**
- crawl_imp_volume_monthly, crawl_imp_stock_monthly, crawl_com_usd_krw
- api_us_beef_collect_usda, collect_usda_primal, crawl_imp_food_safety 등

---

## 2. 현재 이슈

| 구분 | 내용 |
|------|------|
| **setup_project.py** | `2_final`, `docs`, `notebooks` 등 실제 사용하지 않는 폴더/파일 생성 |
| **경로 중복** | 각 모듈이 `project_root` 계산 로직을 따로 구현 |
| **run_daily_update** | Meatbox 가격 파이프라인만 포함, USDA·환율·수입량·재고 미포함 |
| **utils/__init__.py** | `preprocess_meat_data`만 export, 나머지 유틸 미정의 |
| **src/README.md** | 04_Backtesting_Analysis, USDA/Primal 관련 유틸 누락 |
| **z_archive** | 33개 스크립트, 용도 불명확, 테스트/디버깅/레거시 혼재 |
| **requirements** | 루트와 src에 중복, pyproject.toml 없음 |
| **docs/** | data_definition.md 등 없음, 문서 미정비 |

---

## 3. 정리 제안

### Phase 1: 경로·설정 통합 (우선순위 높음)

#### 3.1 `src/config.py` 도입

```python
# src/config.py
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "0_raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "1_processed"
DATA_DASHBOARD = PROJECT_ROOT / "data" / "2_dashboard"
```

- `collectors`, `utils`, `pages`에서 `config`를 import하여 경로 일원화

#### 3.2 `setup_project.py` 수정

- 실제 구조에 맞게 `2_dashboard` 기준으로 조정
- `2_final`, `2_analyzed` 등 미사용 폴더 제거
- `src/data_collector.py`, `docs/data_definition.md`는 실제 사용 여부에 따라 유지/삭제

---

### Phase 2: 문서·의존성 정리

#### 3.3 문서 통합

| 작업 | 설명 |
|------|------|
| **src/README.md 업데이트** | 04_Backtesting_Analysis, USDA/Primal 관련 collectors·utils 반영 |
| **data/README.md 작성** | 0_raw, 1_processed, 2_dashboard 각 파일 역할·출처·갱신 주기 정의 |
| **docs/data_definition.md** | 칼럼 정의, 데이터 소스, 매핑 테이블 정리 (선택) |

#### 3.4 의존성 일원화

- 루트 `requirements.txt`를 단일 소스로 사용
- `src/requirements.txt` 삭제 또는 `../requirements.txt`로 참조
- (선택) `pyproject.toml` 도입으로 패키지·가상환경 관리 표준화

---

### Phase 3: 파이프라인 확장

#### 3.5 `run_daily_update.py` 확장

현재: Meatbox 가격만 갱신  
제안: 수집 주기에 따라 2단계로 분리

```python
# 옵션 A: 전체 수집 (주 1회 등)
run_full_update()   # 모든 collector + preprocess

# 옵션 B: 가격만 수집 (일 1회)
run_price_update()  # Meatbox + preprocess (현재와 동일)
```

- `argparse`로 `--full` / `--price-only` 플래그 추가 가능

#### 3.6 USDA 파이프라인 통합

- `process_usda_data`, `preprocess_primal` 실행 순서·입출력 명시
- run_daily_update에 포함할지, 별도 스케줄(예: 주 1회)로 실행할지 결정

---

### Phase 4: z_archive 정리

#### 3.7 아카이브 분류

| 유형 | 예시 | 권장 조치 |
|------|------|-----------|
| **완전 폐기** | `check_*`, `debug_*`, 일회성 스크립트 | 삭제 또는 별도 `z_deprecated/`로 이동 |
| **재사용 가능** | `viz_beef_dashboard`, `anal_price_prediction` | 필요 시 `pages/`, `utils/`로 편입 |
| **참고용** | `proc_merge_*`, `crawl_imp_*` 변형 | `docs/archive_reference.md`에 요약만 남기고 스크립트는 삭제 |

#### 3.8 추천 작업

1. z_archive 내 각 스크립트 1줄 주석으로 목적 정리
2. 1개월 이상 사용하지 않는 스크립트 → `z_deprecated/` 또는 삭제
3. 유지할 스크립트만 `z_archive/README.md`에 목록·용도 기록

---

### Phase 5: utils 패키지 정리

#### 3.9 `utils/__init__.py` 확장

```python
__all__ = [
    'preprocess_meat_data',
    'preprocess_primal',
    'process_usda_data',
    'init_manual_data',
    'validate_mapping',
    'check_existing_names',
]
```

#### 3.10 유틸 역할 정리

| 모듈 | 역할 | run_daily에 포함 여부 |
|------|------|------------------------|
| preprocess_meat_data | master → dashboard_ready | ✅ 포함 |
| process_usda_data | USDA + 환율 → KRW 원가 | 별도 (주 1회 권장) |
| preprocess_primal | Primal → plate USD/kg | 별도 (USDA와 연계) |
| init_manual_data | 수동 가격 템플릿 생성 | 필요 시 수동 |
| validate_mapping | USDA↔한글 명칭 매핑 검증 | 필요 시 수동 |
| check_existing_names | 마스터 표준명 추출 | 필요 시 수동 |

---

## 4. 제안 폴더 구조 (정리 후)

```
Beef_Price_Model/
├── .env
├── README.md
├── requirements.txt
├── pyproject.toml              # (선택) 의존성·패키지 관리
├── setup_project.py            # 실제 구조에 맞게 수정
├── docs/
│   ├── PROJECT_STRUCTURE_PROPOSAL.md  # 본 문서
│   ├── data_definition.md      # (선택) 데이터 정의
│   └── archive_reference.md    # (선택) z_archive 요약
├── src/
│   ├── config.py               # NEW: 경로·설정 일원화
│   ├── Home.py
│   ├── run_daily_update.py     # 확장: --full / --price-only
│   ├── collectors/
│   ├── utils/
│   ├── pages/
│   └── z_archive/
│       └── README.md           # NEW: 아카이브 목록·용도
└── data/
    ├── README.md               # NEW: 파일별 역할·출처
    ├── 0_raw/
    ├── 1_processed/
    └── 2_dashboard/
```

---

## 5. 실행 우선순위

| 단계 | 작업 | 난이도 | 효과 |
|------|------|--------|------|
| 1 | `config.py` 추가 + 경로 일원화 | 낮음 | 유지보수성↑, 버그 감소 |
| 2 | setup_project.py 수정 | 낮음 | 혼선 감소 |
| 3 | src/README.md, data/README.md 업데이트 | 낮음 | 온보딩·협업 용이 |
| 4 | requirements 일원화 | 낮음 | 의존성 관리 단순화 |
| 5 | run_daily_update 확장 (옵션) | 중간 | 자동화 범위 확대 |
| 6 | z_archive 분류·정리 | 중간 | 코드베이스 정리 |

---

## 6. 요약 및 진행 상태

| Phase | 상태 | 완료일 | 비고 |
|-------|------|--------|------|
| **Phase 1**: 경로·설정 통합 | **완료** | 2025-03-03 | `src/config.py` 추가, 경로 일원화 |
| **Phase 2**: 문서·의존성 정리 | **완료** | 2026-03-25 | docs/ 통합, 중복 문서 제거, `src/README.md` → `docs/PROJECT_GUIDE.md` 이전, `DATA_DICTIONARY.md` + `data_schema_summary.md` 통합, `extract_data_schema.py` → DATA_DICTIONARY 부록 갱신 방식으로 전환 |
| **Phase 3**: 파이프라인 확장 | 미착수 | — | `run_daily_update.py` 확장 (`--full` / `--price-only`) |
| **Phase 4**: z_archive 정리 | 미착수 | — | 레거시 스크립트 분류·정리 |
| **Phase 5**: utils 패키지 정리 | 미착수 | — | `__init__.py` 확장, 역할 정리 |
