# z_deprecated

`z_archive`에서 분리한 **일회성·디버그·점검** 스크립트입니다. 현재 파이프라인에서 호출하지 않으며, 삭제해도 `run_daily_update.py` 동작에 영향이 없습니다.

## 분류

| 유형 | 파일 |
|------|------|
| 디버그·구조 진단 | `debug_meatbox_structure.py`, `inspect_menu_structure.py`, `check_data_structure.py`, `check_history_structure.py` |
| USDA API 탐색 | `check_api_sections.py`, `check_available_items.py`, `preview_primal_data.py`, `test_one_day.py` |
| 데이터 점검 | `check_duplicates.py`, `check_data_status.py`, `check_plate_items.py`, `check_korean_schema.py`, `check_latest_real.py`, `check_history_columns.py`, `analysis_raw_columns.py`, `anal_compare_missing.py` |
| UI·크롤링 테스트 | `test_tab_count.py`, `check_form_names.py` |
| 일회성 spot 수집 | `spot.py`, `spot_202412_202511_import.py` |
| 시각화·탐색(대체 완료) | `visualize_import_volume.py`, `analyze_beef_volatility.py` |
| 유지보수 일회 작업 | `rename_files.py` |

## 이동일

2026-05-19 (Phase 4: z_archive 정리)
