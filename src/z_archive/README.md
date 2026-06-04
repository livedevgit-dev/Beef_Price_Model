# z_archive

리팩토링 이전·참조용 스크립트 보관 폴더입니다. **일상 파이프라인은 `src/run_daily_update.py`를 사용**하세요.

일회성 디버그·점검 스크립트는 `src/z_deprecated/`로 이동했습니다.

## 유지 스크립트 목록

| 파일 | 용도 | 비고 |
|------|------|------|
| `main_runner.py` | 일별·월간(1주차 월요일) 수집/가공 스케줄 실행 | `run_daily_update.py` 이전 오케스트레이터. 참조용 |
| `crawl_imp_meatbox_id_list.py` | 미트박스 전 페이지 ID·시세 리스트 vacuum 수집 | 현재 `collectors/crawl_imp_price_meatbox.py`의 선행 단계 |
| `crawl_imp_history_batch.py` | 미트박스 ID 기준 12개월 시세 API 일괄 수집 | history_batch 폴더 산출 |
| `crawl_imp_volume_daily.py` | 식약처 사이트 일별 미국산 부위별 수입량 크롤러 | 월별 수집기(`crawl_imp_volume_monthly.py`)와 별도 |
| `proc_clean_price.py` | raw FULL xlsx 가격·품목 정제 → beef_price_history | 병합 파이프라인 1단계 |
| `proc_merge_final.py` | history_batch + 최근 이력 병합 → master_price_data.csv | 병합 파이프라인 2단계 |
| `proc_merge_master_data.py` | 시세·환율·수입·재고 raw를 월별 마스터로 통합 | 다소스 통합 참조 |
| `anal_price_drop_rank.py` | history_batch 시세 하락률·고저가 랭킹 분석 | 탐색·리포트용 |
| `anal_price_prediction.py` | 수입·재고·시세 통합 matplotlib 분석 GUI | 탐색용 대화형 차트 |
| `viz_beef_dashboard.py` | Streamlit 기반 수급·시세 모바일 대시보드 | `pages/` 이전 프로토타입 |

## 파이프라인 관계 (참고)

```
[레거시 수집]                    [현재 운영]
crawl_imp_meatbox_id_list  →    collectors/crawl_imp_price_meatbox.py
crawl_imp_history_batch    →    (일일 증분으로 대체)
proc_clean_price           →    preprocess_meat_data.py
proc_merge_final           →    preprocess_meat_data.py
```

## z_deprecated

`check_*`, `debug_*`, `test_*`, `spot_*`, `rename_files.py` 등 22개 일회성 스크립트가 `src/z_deprecated/`에 있습니다. 삭제 전 참고가 필요할 때만 확인하세요.
