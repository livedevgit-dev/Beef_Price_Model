# [파일 정의서]
# - 파일명: run_ml.py
# - 역할: 분석 (ML 파이프라인 원클릭 실행기)
# - 대상: 수입육 갈비(rib) 가격 예측 (현 단계)
# - 주요 기능:
#   - run_daily_update.py 와 동일한 _run_step 패턴으로 피처 생성 → 학습·중요도 분석을 순차 실행
#   - argparse: --all(기본) / --features-only / --train-only
#   - 각 단계 성공/실패·소요시간 요약
# - 참고:
#   현재 ML은 갈비(rib) 한정·월별·in-sample 중요도 분석 단계이며, macro/KAMIS·모델 저장·
#   예측 산출은 향후 확장 대상이다. 본 파일은 "딸깍 실행" 오케스트레이터다.

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))


def _run_step(label: str, rel_path: str, critical: bool = True) -> bool:
    """단일 스크립트를 서브프로세스로 실행한다 (run_daily_update 패턴 동일)."""
    script_path = SRC_DIR / rel_path
    print(f"\n{'-' * 60}")
    print(f">> {label}")
    print(f"  스크립트: {rel_path}")
    if not script_path.exists():
        print(f"  [SKIP] 파일을 찾을 수 없습니다: {script_path}")
        return not critical
    start = time.time()
    try:
        subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
        print(f"  [OK] 완료 ({time.time() - start:.1f}초)")
        return True
    except Exception as e:
        print(f"  [FAIL] 오류 ({time.time() - start:.1f}초): {e}")
        if critical:
            print("  >> 치명적 단계이므로 파이프라인을 중단합니다.")
        return False


# --- 단계 정의 --------------------------------------------------------------
FEATURE_STEPS = [
    ("거래 활성 품목 선정 (universe)", "utils/select_universe.py"),
    ("삼겹양지 통합 시계열", "utils/build_samgyup_series.py"),
    ("삼겹양지 피처·예측·영향력", "utils/build_samgyup_model.py"),
]

TRAIN_STEPS = [
    ("삼겹양지 익월가 예측 (XGBoost, walk-forward)", "Models/train_samgyup_xgb.py"),
    ("부위별 상승가능성 랭킹 (pooled XGBoost)", "Models/train_cut_upside.py"),
    ("일반인용 시장 리포트 생성 (공유·BI용)", "reports/generate_market_report.py"),
]

_LEGACY_TRAIN_STEPS = [
    ("학습·중요도 — 1개월 델타 (XGBoost)", "Models/train_baseline.py"),
    ("학습·중요도 — 6개월 최대상승폭 (XGBoost)", "Models/train_rolling_horizon.py"),
]


def run_pipeline(do_features: bool, do_train: bool) -> tuple[int, int, int]:
    total = success = fail = 0

    if do_features:
        print(f"\n{'=' * 60}\n  [1] 피처 엔지니어링\n{'=' * 60}")
        for label, path in FEATURE_STEPS:
            total += 1
            # 피처 생성 실패 시 학습이 불가하므로 critical
            if _run_step(f"[피처] {label}", path, critical=True):
                success += 1
            else:
                fail += 1
                return total, success, fail

    if do_train:
        print(f"\n{'=' * 60}\n  [2] 모델 학습 · 변수 중요도\n{'=' * 60}")
        for label, path in TRAIN_STEPS:
            total += 1
            # 한 모델이 실패해도 다른 모델은 계속 (non-critical)
            if _run_step(f"[학습] {label}", path, critical=False):
                success += 1
            else:
                fail += 1

    return total, success, fail


def main():
    parser = argparse.ArgumentParser(
        description="Beef Price Model — ML 파이프라인 원클릭 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
사용 예시:
  python src/run_ml.py                  피처 생성 + 학습 전체 (기본)
  python src/run_ml.py --features-only  피처 생성만
  python src/run_ml.py --train-only     학습만 (피처 CSV가 이미 있어야 함)

참고: 현재 ML은 갈비(rib) 한정·월별·in-sample 중요도 분석 단계입니다.
      데이터 규모가 작아 GPU(예: RTX 4070)는 성능 이점이 없습니다(CPU로 충분).
""",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--features-only", action="store_true", help="피처 생성만 실행")
    group.add_argument("--train-only", action="store_true", help="학습만 실행")
    args = parser.parse_args()

    do_features = not args.train_only
    do_train = not args.features_only

    print("=" * 60)
    mode = "전체(피처+학습)" if (do_features and do_train) else ("피처만" if do_features else "학습만")
    print(f"  ML 파이프라인 실행  |  모드: {mode}")
    print("=" * 60)

    start = time.time()
    total, success, fail = run_pipeline(do_features, do_train)
    elapsed = time.time() - start

    print(f"\n{'=' * 60}")
    print(f"  ML 파이프라인 완료  |  총 {total}단계  |  성공 {success}  |  실패 {fail}  |  {elapsed:.1f}초")
    print(f"{'=' * 60}")
    if fail == 0:
        print("모든 ML 단계가 정상적으로 완료되었습니다.")
    else:
        print(f"[!] {fail}개 단계에서 오류가 발생했습니다. 위 로그를 확인하세요.")
    raise SystemExit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
