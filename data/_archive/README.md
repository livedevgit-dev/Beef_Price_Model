# data/_archive

2026-10-30 데이터 정합성 점검 때 **현재 코드(src/, z_archive·z_deprecated 제외)가 읽지 않는** 파일을 옮겨 둔 곳입니다.
삭제하지 않고 원래 폴더 구조대로 보관합니다. 파이프라인 자동 커밋 대상(`data/0_raw`, `data/1_processed`, `data/2_dashboard`)이 아니어서 더 이상 갱신되지 않습니다.

| 원래 위치 | 내용 |
|---|---|
| `0_raw/usda_choice_cuts_*`, `usda_primal_values_02112026.csv`, `usda_raw_20260212.csv` | 2026-02 USDA 일괄 수집 스냅샷 (현재는 `usda_beef_history.csv` / `usda_primal_history.csv` 사용) |
| `0_raw/미국산소고기_*.csv`, `us_beef_parts_import_daily.csv` | 초기 수입량 수작업 자료 |
| `0_raw/raw_meatbox_*`, `meatbox_*.xlsx`, `debug_page_source.html`, `found_missing_ids.xlsx` | 2026-01 미트박스 백필 작업 중간 산출물 (백필 원본은 `0_raw/history_batch/` 에 그대로 있음) |
| `0_raw/beef_*.xlsx`, `raw_food_safety_data.csv` | 초기 실험용 원본 |
| `1_processed/dashboard_ready_data.csv` | 2026-02-09 에 멈춘 옛 스키마 (현재는 `2_dashboard/dashboard_ready_data.csv`) |
| `1_processed/master_price_data_backup.csv`, `clean_price_data.csv`, `beef_price_history.xlsx`, `monthly_master_data.xlsx` | 옛 백업·중간 산출물 |
| `root/beef_primal_cut_prices.xlsx` | 프로젝트 루트에 있던 사본 |

다시 쓰려면 원래 위치로 옮기면 됩니다 (`git mv`).
