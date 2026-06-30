"""
[파일 정의서]
- 파일명: run_auto.py
- 역할: 실행 (스마트 자동 오케스트레이터 — .bat 하나로 일/주/월 작업 자동 판단)
- 동작(상태 기반 — 고정날짜 아님, 주말·공휴일 누락에 강함):
    1. 매 실행: 일일 갱신(미트박스·한우). 단 '전체 갱신'이 도래했으면 그걸로 대체.
    2. 전체 갱신(--full): 마지막 실행 후 7일 이상 경과 시 (또는 월간 ML 직전).
    3. 월초 수입 갱신(--monthly): 이번 달에 아직 안 했으면 1회 — 전월 수입을
       KMTA→식약처 보완 경로로 수집. (--full이 돈 날은 식약처 포함이라 자동 충족 처리)
    4. 월간 ML·리포트: 이번 달에 아직 안 했고 28일 이후면 실행.
- 상태파일: data/.run_state/last_full.txt, last_ml.txt, last_import.txt (ISO 날짜)
- 실행: python src/run_auto.py   (--dry 면 판단만 출력, 실행 안 함)
"""
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
STATE = ROOT / "data" / ".run_state"
PY = sys.executable
DRY = "--dry" in sys.argv

FULL_INTERVAL_DAYS = 7     # 전체 갱신 주기
ML_DAY = 28                # 이 날짜 이후면 월간 ML 대상


def _read(m):
    p = STATE / m
    if not p.exists():
        return None
    try:
        return date.fromisoformat(p.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _mark(m):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / m).write_text(date.today().isoformat(), encoding="utf-8")


def _days_since(d):
    return 99999 if d is None else (date.today() - d).days


def _ran_this_month(d):
    t = date.today()
    return d is not None and d.year == t.year and d.month == t.month


def _run(script, args, label):
    print(f"\n{'='*64}\n>>> {label}\n    실행: {script} {' '.join(args)}\n{'='*64}")
    if DRY:
        print("    [DRY] 실제 실행 생략")
        return 0
    return subprocess.run([PY, str(SRC / script)] + args, cwd=str(ROOT)).returncode


def main():
    today = date.today()
    last_full = _read("last_full.txt")
    last_ml = _read("last_ml.txt")
    last_import = _read("last_import.txt")

    ml_due = today.day >= ML_DAY and not _ran_this_month(last_ml)
    full_due = _days_since(last_full) >= FULL_INTERVAL_DAYS or (ml_due and last_full != today)
    import_due = not _ran_this_month(last_import)   # 월 1회 — 새 달 첫 실행 시 전월 수입 수집

    print(f"\n[스마트 자동실행] {today.isoformat()} ({['월','화','수','목','금','토','일'][today.weekday()]})")
    print(f"  마지막 전체갱신: {last_full or '없음'} ({_days_since(last_full)}일 전)")
    print(f"  마지막 월간수입: {last_import or '없음'}")
    print(f"  마지막 월간ML  : {last_ml or '없음'}")
    print(f"  판단 → 전체갱신: {'예' if full_due else '아니오(일일만)'} / 월간수입: {'예' if import_due else '아니오'} / 월간ML: {'예' if ml_due else '아니오'}")

    # 1) 일일 또는 전체
    if full_due:
        rc = _run("run_daily_update.py", ["--full"], "전체 갱신 (주기 도래 — 데이터+거시+예측+경보 전부)")
        if rc == 0 and not DRY:
            _mark("last_full.txt")
            _mark("last_import.txt")   # --full은 식약처 수입 포함 → 월간 수입도 충족
    else:
        _run("run_daily_update.py", [], "일일 갱신 (미트박스·한우)")

    # 1-2) 월초 수입 갱신 (--full이 안 돈 경우에만 — 전월 수입 KMTA→식약처 보완)
    if import_due and not full_due:
        rc = _run("run_daily_update.py", ["--monthly"], "월간 수입 갱신 (전월 — KMTA→식약처 보완)")
        if rc == 0 and not DRY:
            _mark("last_import.txt")

    # 2) 월간 ML·리포트
    if ml_due:
        rc = _run("run_ml.py", [], "월간 ML·시장리포트 (월말 — 예측/랭킹/리포트 갱신)")
        if rc == 0 and not DRY:
            _mark("last_ml.txt")

    print(f"\n{'='*64}\n[완료] 스마트 자동실행 종료. 상세는 위 로그·현황판 참고.\n{'='*64}")


if __name__ == "__main__":
    main()
