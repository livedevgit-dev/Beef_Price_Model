import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# [파일 정의서]
# - 파일명: run_daily_update.py
# - 역할: 전체 파이프라인 제어
# - 대상: 수입육 (공통)
# - 주요 기능: 크롤링, 전처리, 데이터 사전 갱신을 순차적으로 실행하여 데이터 최신성 유지
# - 실행 옵션:
#     python src/run_daily_update.py                → 가격 파이프라인만 (기본, 기존 동작)
#     python src/run_daily_update.py --price-only   → 가격 파이프라인만 (명시적)
#     python src/run_daily_update.py --full          → 전체 수집 + 전처리
# - 성공 시 Git: 모든 단계 성공(fail==0)이면 data/, docs/DATA_DICTIONARY.md 자동 커밋 (--no-commit 으로 끔)
# - 푸시: --push 또는 환경변수 PIPELINE_GIT_PUSH=1


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = Path(CURRENT_DIR).resolve().parent

# 파이프라인이 갱신하는 경로만 스테이징 (코드 변경은 포함하지 않음)
GIT_PIPELINE_PATHS = [
    "data/0_raw",
    "data/1_processed",
    "data/2_dashboard",
    "docs/DATA_DICTIONARY.md",
]


def _run_step(label, script_path, critical=True):
    """단일 스크립트를 서브프로세스로 실행하고 결과를 반환한다."""
    print(f"\n{'-'*60}")
    print(f">> {label}")
    print(f"  스크립트: {os.path.relpath(script_path, CURRENT_DIR)}")
    start = time.time()
    try:
        subprocess.run(
            [sys.executable, script_path],
            check=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        elapsed = time.time() - start
        print(f"  [OK] 완료 ({elapsed:.1f}초)")
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [FAIL] 오류 발생 ({elapsed:.1f}초): {e}")
        if critical:
            print("  >> 치명적 단계이므로 파이프라인을 중단합니다.")
        return False


def _run_step_with_retry(label, script_path, max_attempts=3, critical=True):
    """단일 스크립트를 최대 N회 재시도 실행한다."""
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"\n[재시도] {label} ({attempt}/{max_attempts})")
        if _run_step(label, script_path, critical=critical):
            return True
    print(f"[FAIL] 재시도 {max_attempts}회 모두 실패했습니다: {label}")
    return False


def _collector(name):
    return os.path.join(CURRENT_DIR, "collectors", name)


def _util(name):
    return os.path.join(CURRENT_DIR, "utils", name)


def _git_available() -> bool:
    try:
        r = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _try_git_commit_and_push(
    mode_label: str,
    do_commit: bool,
    do_push: bool,
) -> None:
    """
    파이프라인 산출물만 스테이징 후 커밋. 성공 시 선택적으로 git push.
    """
    if not do_commit:
        return

    root = PROJECT_ROOT
    if not (root / ".git").is_dir():
        print("\n[Git] .git 이 없어 커밋을 건너뜁니다.")
        return

    if not _git_available():
        print("\n[Git] git 명령을 찾을 수 없어 커밋을 건너뜁니다.")
        return

    to_add = []
    for rel in GIT_PIPELINE_PATHS:
        p = root / rel
        if p.exists():
            to_add.append(rel)

    if not to_add:
        print("\n[Git] 커밋 대상 경로가 없어 건너뜁니다.")
        return

    try:
        subprocess.run(
            ["git", "add", "--"] + to_add,
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[Git] git add 실패: {e.stderr or e}")
        return

    chk = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
    )
    if chk.returncode == 0:
        print("\n[Git] 변경 사항 없음 — 커밋하지 않습니다.")
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"chore(data): pipeline OK [{mode_label}] {ts}"
    try:
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"\n[Git] 커밋 완료: {msg}")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        print(f"\n[Git] 커밋 실패: {err or e}")
        return

    if not do_push:
        print("[Git] 원격 반영은 하지 않았습니다. 푸시하려면 --push 또는 PIPELINE_GIT_PUSH=1")
        return

    pr = subprocess.run(
        ["git", "push"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if pr.returncode == 0:
        print("[Git] git push 완료 (origin)")
    else:
        out = (pr.stderr or pr.stdout or "").strip()
        print(f"[Git] git push 실패 — 자격 증명·네트워크·브랜치를 확인하세요.\n{out}")


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
    if not _run_step_with_retry(f"[수집] {label}", path, max_attempts=3, critical=True):
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
        run_ok = (
            _run_step_with_retry(f"[일별 수집] {label}", path, max_attempts=3, critical=False)
            if path.endswith("crawl_imp_price_meatbox.py")
            else _run_step(f"[일별 수집] {label}", path, critical=False)
        )
        if run_ok:
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
  python src/run_daily_update.py --full --push   전체 수집 후 커밋 + git push

성공 시(모든 단계 성공) data/, docs/DATA_DICTIONARY.md 가 자동 커밋됩니다.
  --no-commit   커밋 생략
  --push        커밋 후 origin 으로 push (또는 환경변수 PIPELINE_GIT_PUSH=1)
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
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="모든 단계가 성공해도 Git 커밋하지 않음",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="커밋 후 git push (또는 PIPELINE_GIT_PUSH=1)",
    )
    args = parser.parse_args()

    pipeline_start = time.time()

    if args.full:
        total, success, fail = run_full()
        mode_label = "full"
    else:
        total, success, fail = run_price_only()
        mode_label = "price-only"

    elapsed = time.time() - pipeline_start

    print(f"\n{'=' * 60}")
    print(f"  파이프라인 완료  |  총 {total}단계  |  성공 {success}  |  실패 {fail}  |  {elapsed:.1f}초")
    print(f"{'=' * 60}")
    if fail == 0:
        print("모든 단계가 정상적으로 완료되었습니다. 대시보드와 데이터 사전을 확인하세요!")
        want_push = args.push or os.environ.get("PIPELINE_GIT_PUSH", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        _try_git_commit_and_push(
            mode_label,
            do_commit=not args.no_commit,
            do_push=want_push,
        )
    else:
        print(f"[!] {fail}개 단계에서 오류가 발생했습니다. 위 로그를 확인하세요.")
    raise SystemExit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()