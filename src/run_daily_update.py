import argparse
import os
import subprocess
import sys
import time

# [파일 정의서]
# - 파일명: run_daily_update.py
# - 역할: 전체 파이프라인 제어
# - 대상: 수입육 (공통)
# - 주요 기능: 크롤링, 전처리, 데이터 사전 갱신을 순차적으로 실행하여 데이터 최신성 유지
# - 실행 옵션:
#     python src/run_daily_update.py                → 가격 파이프라인만 (기본, 기존 동작)
#     python src/run_daily_update.py --price-only   → 가격 파이프라인만 (명시적)
#     python src/run_daily_update.py --full          → 전체 수집 + 전처리


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))


def _run_step(label, script_path, critical=True):
    """단일 스크립트를 서브프로세스로 실행하고 결과를 반환한다."""
    print(f"\n{'-'*60}")
    print(f">> {label}")
    print(f"  스크립트: {os.path.relpath(script_path, CURRENT_DIR)}")
    start = time.time()
    try:
        subprocess.run([sys.executable, script_path], check=True)
        elapsed = time.time() - start
        print(f"  [OK] 완료 ({elapsed:.1f}초)")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [FAIL] 오류 발생 ({elapsed:.1f}초): {e}")
        if critical:
            print("  >> 치명적 단계이므로 파이프라인을 중단합니다.")
        return False


def _collector(name):
    return os.path.join(CURRENT_DIR, "collectors", name)


def _util(name):
    return os.path.join(CURRENT_DIR, "utils", name)


# --- 수집 단계 정의 -----------------------------------------------
DAILY_COLLECTORS = [
    ("미트박스 B2B 도매시세",            _collector("crawl_imp_price_meatbox.py")),
    ("USDA 부위별 시세 (LM_XB403)",      _collector("api_us_beef_collect_usda.py")),
    ("USDA 프라이멀 시세",               _collector("collect_usda_primal.py")),
    ("USD/KRW 환율",                     _collector("crawl_com_usd_krw.py")),
]

MONTHLY_COLLECTORS = [
    ("KMTA 월별 수입량",                 _collector("crawl_imp_volume_monthly.py")),
    ("KMTA 월별 재고",                   _collector("crawl_imp_stock_monthly.py")),
    ("식약처 수입 검역 실적",             _collector("crawl_imp_food_safety.py")),
]

USDA_PROCESSORS = [
    ("USDA 원가 산출 (환율 반영)",       _util("process_usda_data.py")),
    ("USDA Plate USD/kg 변환",          _util("preprocess_primal.py")),
]

COMMON_PROCESSORS = [
    ("미트박스 전처리 → dashboard_ready", _util("preprocess_meat_data.py")),
]

SCHEMA_UPDATER = [
    ("DATA_DICTIONARY 스키마 갱신",       _util("extract_data_schema.py")),
]


def run_price_only():
    """기존 동작: 미트박스 가격 수집 → 전처리 → 스키마 갱신"""
    print("=" * 60)
    print("  모드: --price-only (미트박스 가격 파이프라인)")
    print("=" * 60)

    total, success, fail = 0, 0, 0

    # 수집
    label, path = DAILY_COLLECTORS[0]  # crawl_imp_price_meatbox
    total += 1
    if not _run_step(f"[수집] {label}", path, critical=True):
        fail += 1
        return total, success, fail
    success += 1

    # 전처리
    for label, path in COMMON_PROCESSORS:
        total += 1
        if not _run_step(f"[전처리] {label}", path, critical=True):
            fail += 1
            return total, success, fail
        success += 1

    # 스키마 갱신 (실패해도 계속)
    for label, path in SCHEMA_UPDATER:
        total += 1
        if _run_step(f"[문서] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    return total, success, fail


def run_full():
    """전체 수집: 일별 + 월별 수집 → USDA 전처리 → 미트박스 전처리 → 스키마 갱신"""
    print("=" * 60)
    print("  모드: --full (전체 수집 + 전처리)")
    print("=" * 60)

    total, success, fail = 0, 0, 0

    # -- 1단계: 일별 수집 --
    print(f"\n{'='*60}")
    print("  [1] 일별 데이터 수집")
    print(f"{'='*60}")
    for label, path in DAILY_COLLECTORS:
        total += 1
        if _run_step(f"[일별 수집] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    # -- 2단계: 월별 수집 --
    print(f"\n{'='*60}")
    print("  [2] 월별 데이터 수집")
    print(f"{'='*60}")
    for label, path in MONTHLY_COLLECTORS:
        total += 1
        if _run_step(f"[월별 수집] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    # -- 3단계: USDA 전처리 --
    print(f"\n{'='*60}")
    print("  [3] USDA 전처리")
    print(f"{'='*60}")
    for label, path in USDA_PROCESSORS:
        total += 1
        if _run_step(f"[USDA 전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    # -- 4단계: 미트박스 전처리 --
    print(f"\n{'='*60}")
    print("  [4] 미트박스 전처리")
    print(f"{'='*60}")
    for label, path in COMMON_PROCESSORS:
        total += 1
        if _run_step(f"[전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    # -- 5단계: 스키마 갱신 --
    print(f"\n{'='*60}")
    print("  [5] 문서 갱신")
    print(f"{'='*60}")
    for label, path in SCHEMA_UPDATER:
        total += 1
        if _run_step(f"[문서] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    return total, success, fail


def main():
    parser = argparse.ArgumentParser(
        description="Beef Price Model 데이터 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
사용 예시:
  python src/run_daily_update.py               가격 파이프라인만 (기본)
  python src/run_daily_update.py --price-only   가격 파이프라인만 (명시적)
  python src/run_daily_update.py --full          전체 수집 + 전처리
""",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--full",
        action="store_true",
        help="전체 수집 (USDA·환율·수입량·재고·식약처) + 전처리",
    )
    group.add_argument(
        "--price-only",
        action="store_true",
        help="미트박스 가격 수집 + 전처리만 (기본값)",
    )
    args = parser.parse_args()

    pipeline_start = time.time()

    if args.full:
        total, success, fail = run_full()
    else:
        total, success, fail = run_price_only()

    elapsed = time.time() - pipeline_start

    print(f"\n{'=' * 60}")
    print(f"  파이프라인 완료  |  총 {total}단계  |  성공 {success}  |  실패 {fail}  |  {elapsed:.1f}초")
    print(f"{'=' * 60}")
    if fail == 0:
        print("모든 단계가 정상적으로 완료되었습니다. 대시보드와 데이터 사전을 확인하세요!")
    else:
        print(f"[!] {fail}개 단계에서 오류가 발생했습니다. 위 로그를 확인하세요.")


if __name__ == "__main__":
    main()