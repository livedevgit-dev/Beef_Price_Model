# 소고기 시세 예측 모델 (Beef Price Model)

수입 소고기 도매시세 데이터를 수집·분석·예측하는 프로젝트입니다.

## Quick Start

```bash
# 대시보드 실행
streamlit run src/Home.py

# 데이터 수집 + 전처리 + 스키마 문서 갱신
python src/run_daily_update.py
```

## 프로젝트 구조

```
Beef_Price_Model/
├── src/           # 소스 코드 (수집기, 전처리, 대시보드, 모델)
├── data/          # 데이터 (0_raw → 1_processed → 2_dashboard)
└── docs/          # 프로젝트 문서
```

## 문서

| 문서 | 설명 |
|------|------|
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 폴더 구조, 모듈 설명, 실행 방법, 네이밍 규칙 |
| [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | 데이터 파일 목록, 스키마, 수집 주기, 날짜 포맷 |
| [docs/PROJECT_STRUCTURE_PROPOSAL.md](docs/PROJECT_STRUCTURE_PROPOSAL.md) | 구조 리팩토링 계획 및 진행 상태 |
