"""
[파일 정의서]
- 파일명: io_safe.py
- 역할: 공통 유틸 (안전 저장 · 실행 잠금)
- 주요 기능:
    1. atomic_to_csv / atomic_to_excel: 같은 폴더의 임시 파일에 쓴 뒤 os.replace 로 교체.
       쓰기 도중 중단·예외가 나도 기존 파일은 그대로 남는다(잘린 파일 방지).
    2. pipeline_lock: 파이프라인 동시 실행 방지용 잠금 파일(data/.run_state/pipeline.lock).
       스케줄 실행과 수동 실행이 겹쳐 같은 날 데이터를 서로 덮어쓰던 문제(2026-10-07) 대응.
"""

import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def _atomic_write(path, write_fn, suffix):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=suffix, dir=str(path.parent))
    os.close(fd)
    try:
        write_fn(tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def atomic_to_csv(df, path, **kwargs):
    """DataFrame.to_csv 의 원자적 버전. kwargs 는 to_csv 에 그대로 전달."""
    _atomic_write(path, lambda tmp: df.to_csv(tmp, **kwargs), ".csv.tmp")


def atomic_to_excel(df, path, **kwargs):
    """DataFrame.to_excel 의 원자적 버전 (openpyxl 은 확장자로 형식을 판단하므로 임시 파일도 .xlsx)."""
    _atomic_write(path, lambda tmp: df.to_excel(tmp, **kwargs), ".tmp.xlsx")


class PipelineLocked(RuntimeError):
    pass


@contextmanager
def pipeline_lock(lock_path, wait_sec=0, stale_sec=3 * 3600):
    """잠금 파일을 배타적으로 생성해 동시 실행을 막는다.
    - 이미 잠겨 있으면 wait_sec 동안 기다린 뒤 PipelineLocked 를 던진다.
    - stale_sec 보다 오래된 잠금(비정상 종료 잔재)은 지우고 진행한다.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_sec
    announced = False
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except OSError:
                continue
            if age > stale_sec:
                print(f"[잠금] {age/60:.0f}분 된 잠금 파일을 비정상 종료 잔재로 보고 제거합니다: {lock_path}")
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                holder = ""
                try:
                    holder = lock_path.read_text(encoding="utf-8").strip()
                except OSError:
                    pass
                raise PipelineLocked(f"다른 파이프라인이 실행 중입니다 ({holder}). 끝난 뒤 다시 실행하세요.")
            if not announced:
                print(f"[잠금] 다른 파이프라인 실행이 끝나기를 기다립니다 (최대 {wait_sec // 60}분)...", flush=True)
                announced = True
            time.sleep(10)
    try:
        yield
    finally:
        try:
            os.remove(lock_path)
        except OSError:
            pass
