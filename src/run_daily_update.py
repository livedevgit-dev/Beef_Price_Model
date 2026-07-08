# [파일 정의서]
# - 파일명: run_daily_update.py
# - 역할: 수집
# - 대상: 공통
# - 데이터 소스: docs/PROJECT_STRUCTURE_PROPOSAL.md, docs/DATA_COLLECTION_RULES.md, collectors/, utils/
# - 주요 기능:
#   - argparse(--price-only/--full/--monthly)로 일일·월별 수집 및 전처리 파이프라인 순차 실행
#   - 파이프라인 종료 시 데이터 GAP 검증 리포트 출력 (수입 공백 시 식약처 보완 옵션)
#   - 성공 시 data/ 산출물 Git 커밋

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from dateutil.relativedelta import relativedelta

from config import (
    BEEF_STOCK_XLSX,
    DASHBOARD_READY_CSV,
    EXCHANGE_RATE_XLSX,
    HAN_AUCTION_RAW_CSV,
    MACRO_RAW_CSV,
    MASTER_IMPORT_VOLUME_CSV,
    PROJECT_ROOT,
    SRC_DIR,
    USDA_BEEF_HISTORY_CSV,
)

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
    print(f"  스크립트: {script_path.relative_to(SRC_DIR)}")
    start = time.time()
    try:
        subprocess.run(
            [sys.executable, str(script_path)],
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
    return SRC_DIR / "collectors" / name


def _util(name):
    return SRC_DIR / "utils" / name


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
    """파이프라인 산출물만 스테이징 후 커밋. 성공 시 선택적으로 git push."""
    if not do_commit:
        return

    if not (PROJECT_ROOT / ".git").is_dir():
        print("\n[Git] .git 이 없어 커밋을 건너뜁니다.")
        return

    if not _git_available():
        print("\n[Git] git 명령을 찾을 수 없어 커밋을 건너뜁니다.")
        return

    to_add = []
    for rel in GIT_PIPELINE_PATHS:
        p = PROJECT_ROOT / rel
        if p.exists():
            to_add.append(rel)

    if not to_add:
        print("\n[Git] 커밋 대상 경로가 없어 건너뜁니다.")
        return

    try:
        subprocess.run(
            ["git", "add", "--"] + to_add,
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"\n[Git] git add 실패: {e.stderr or e}")
        return

    chk = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=PROJECT_ROOT,
    )
    if chk.returncode == 0:
        print("\n[Git] 변경 사항 없음 — 커밋하지 않습니다.")
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"chore(data): pipeline OK [{mode_label}] {ts}"
    try:
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=PROJECT_ROOT,
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
        cwd=PROJECT_ROOT,
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
    ("미트박스 B2B 도매시세", _collector("crawl_imp_price_meatbox.py")),
    ("USDA 부위별 시세 (LM_XB403)", _collector("api_us_beef_collect_usda.py")),
    ("USDA 프라이멀 시세", _collector("collect_usda_primal.py")),
    ("USD/KRW 환율", _collector("crawl_com_usd_krw.py")),
    ("EKAPE 한우 경락가격·도축두수", _collector("crawl_han_auction_api.py")),
    ("KAMIS 한우 도/소매가 (키 없으면 자동 skip)", _collector("collect_kamis_hanwoo.py")),
    ("KAMIS 돼지 도/소매가 (외식 공급가, 키 없으면 자동 skip)", _collector("collect_kamis_pork.py")),
]

MONTHLY_COLLECTORS = [
    ("KMTA 월별 수입량", _collector("crawl_imp_volume_monthly.py")),
    ("KMTA 월별 재고", _collector("crawl_imp_stock_monthly.py")),
    ("식약처 수입 검역 실적", _collector("crawl_imp_food_safety.py")),
]

# 거시경제 지표 (Macro) — 키 없으면 각 수집기가 자동 skip
MACRO_COLLECTORS = [
    ("FRED 미국 거시지표 (옥수수·대두·WTI·Food PPI, 키 없으면 skip)", _collector("collect_macro_fred.py")),
    ("ECOS 국내 거시지표 (기준금리·CPI·PPI·심리지수, 키 없으면 skip)", _collector("collect_macro_ecos.py")),
    ("KMA 기후 지표 (기온·강수, 키 없으면 skip)", _collector("collect_macro_kma.py")),
    ("FAS 미국 소고기 수출 (중국·한국, 덤핑 조기경보, 키 없으면 skip)", _collector("collect_fas_export_sales.py")),
    ("NASS Cattle on Feed (미국 사육두수, 공급 선행, 키 없으면 skip)", _collector("collect_cattle_on_feed.py")),
]

MACRO_PROCESSORS = [
    ("거시지표 전처리 (raw → daily ffill → macro_dashboard_ready)", _util("preprocess_macro.py")),
    ("FAS 공급경보 전처리 (중국행 급감/한국행 과잉 → 다이버전 경보)", _util("preprocess_fas_signal.py")),
]

# 삼겹양지 분석·예측·시그널 (수집·전처리 이후 실행)
ANALYSIS_PROCESSORS = [
    ("거래 활성 품목 선정 (동적 universe)", _util("select_universe.py")),
    ("삼겹양지 통합 시계열 (미트박스 + 도매상)", _util("build_samgyup_series.py")),
    ("삼겹양지 피처·예측·변수영향력", _util("build_samgyup_model.py")),
    ("품목 전환(상대가치) 시그널", _util("build_switch_signal.py")),
]

USDA_PROCESSORS = [
    ("USDA 원가 산출 (환율 반영)", _util("process_usda_data.py")),
    ("USDA Plate USD/kg 변환", _util("preprocess_primal.py")),
]

HANWOO_PROCESSORS = [
    ("한우 통합 전처리 (EKAPE + KAMIS → hanwoo_dashboard_ready)", _util("preprocess_hanwoo.py")),
]

COMMON_PROCESSORS = [
    ("미트박스 전처리 → dashboard_ready", _util("preprocess_meat_data.py")),
]

SCHEMA_UPDATER = [
    ("DATA_DICTIONARY 스키마 갱신", _util("extract_data_schema.py")),
]

MEATBOX_SCRIPT = _collector("crawl_imp_price_meatbox.py")
IMPORT_VOLUME_SCRIPT = _collector("crawl_imp_volume_monthly.py")
STOCK_SCRIPT = _collector("crawl_imp_stock_monthly.py")
FOOD_SAFETY_SCRIPT = _collector("crawl_imp_food_safety.py")

MONTHLY_RETRY_DAYS = {10, 20}


def _expected_previous_month() -> str:
    """월별 데이터 완료 기준: 전월 (YYYY-MM)."""
    anchor = datetime.now().replace(day=1) - relativedelta(days=1)
    return anchor.strftime("%Y-%m")


def _month_key_to_int(ym: str) -> int:
    year, month = map(int, str(ym).split("-")[:2])
    return year * 12 + month


def _find_month_holes(months: list[str]) -> list[str]:
    """정렬된 YYYY-MM 목록에서 빠진 연속 월을 반환한다."""
    if not months:
        return []
    ints = sorted(_month_key_to_int(m) for m in months)
    holes = []
    for i in range(ints[0], ints[-1]):
        if i not in ints:
            y, m = divmod(i, 12)
            if m == 0:
                y -= 1
                m = 12
            holes.append(f"{y:04d}-{m:02d}")
    return holes


def _read_import_months() -> list[str]:
    if not MASTER_IMPORT_VOLUME_CSV.exists():
        return []
    df = pd.read_csv(MASTER_IMPORT_VOLUME_CSV, encoding="utf-8-sig", usecols=["std_date"])
    return sorted(df["std_date"].dropna().astype(str).unique())


def _read_stock_months() -> list[str]:
    if not BEEF_STOCK_XLSX.exists():
        return []
    df = pd.read_excel(BEEF_STOCK_XLSX)
    if "기준년월" not in df.columns:
        return []
    valid = df["기준년월"].astype(str).str.match(r"^\d{4}-\d{2}$", na=False)
    return sorted(df.loc[valid, "기준년월"].astype(str).unique())


def _read_meatbox_latest_date():
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(DASHBOARD_READY_CSV, usecols=["date"])
    return pd.to_datetime(df["date"], errors="coerce").max()


def _read_usda_latest_date():
    if not USDA_BEEF_HISTORY_CSV.exists():
        return None
    df = pd.read_csv(
        USDA_BEEF_HISTORY_CSV,
        usecols=["report_date"],
        low_memory=False,
    )
    return pd.to_datetime(df["report_date"], format="%m/%d/%Y", errors="coerce").max()


def _read_exchange_latest_date():
    if not EXCHANGE_RATE_XLSX.exists():
        return None
    df = pd.read_excel(EXCHANGE_RATE_XLSX, usecols=["Date"])
    return pd.to_datetime(df["Date"], errors="coerce").max()


def _read_hanwoo_latest_date():
    if not HAN_AUCTION_RAW_CSV.exists():
        return None
    df = pd.read_csv(HAN_AUCTION_RAW_CSV, usecols=["auction_end_ymd"], low_memory=False)
    return pd.to_datetime(
        df["auction_end_ymd"].astype(str), format="%Y%m%d", errors="coerce"
    ).max()


def _read_macro_latest_date():
    """거시지표 raw 의 최신 date. 파일 없으면 None (키 미설정/미수집)."""
    if not MACRO_RAW_CSV.exists():
        return None
    try:
        df = pd.read_csv(MACRO_RAW_CSV, usecols=["date"], low_memory=False)
    except Exception:
        return None
    return pd.to_datetime(df["date"], errors="coerce").max()


def check_data_gaps(*, check_monthly: bool, check_usda: bool) -> list[dict]:
    """
    데이터 최신성 GAP 목록을 반환한다.
    각 항목: name, latest, expected, status(OK|GAP|WARN|MISSING), severity(info|warn), action
    """
    findings: list[dict] = []
    today = datetime.now().date()
    expect_month = _expected_previous_month()

    if check_monthly:
        imp_months = _read_import_months()
        if not imp_months:
            findings.append({
                "name": "수입량",
                "latest": "-",
                "expected": expect_month,
                "status": "MISSING",
                "severity": "warn",
                "action": "python src/collectors/crawl_imp_volume_monthly.py 실행",
            })
        else:
            imp_max = imp_months[-1]
            imp_holes = _find_month_holes(imp_months)
            if _month_key_to_int(imp_max) < _month_key_to_int(expect_month):
                findings.append({
                    "name": "수입량",
                    "latest": imp_max,
                    "expected": expect_month,
                    "status": "GAP",
                    "severity": "warn",
                    "action": "KMTA 수집 후 공백이면 crawl_imp_food_safety.py (--remediate-import)",
                })
            elif imp_holes:
                findings.append({
                    "name": "수입량 (중간 월 누락)",
                    "latest": imp_max,
                    "expected": ", ".join(imp_holes[-3:]),
                    "status": "GAP",
                    "severity": "warn",
                    "action": "누락 월 수동 백필 또는 volume_monthly 재실행",
                })
            else:
                findings.append({
                    "name": "수입량",
                    "latest": imp_max,
                    "expected": expect_month,
                    "status": "OK",
                    "severity": "info",
                    "action": "-",
                })

        stk_months = _read_stock_months()
        if not stk_months:
            findings.append({
                "name": "재고",
                "latest": "-",
                "expected": expect_month,
                "status": "MISSING",
                "severity": "warn",
                "action": "python src/collectors/crawl_imp_stock_monthly.py (--with-stock, 소요 시간 큼)",
            })
        else:
            stk_max = stk_months[-1]
            stk_holes = _find_month_holes(stk_months)
            if _month_key_to_int(stk_max) < _month_key_to_int(expect_month):
                findings.append({
                    "name": "재고",
                    "latest": stk_max,
                    "expected": expect_month,
                    "status": "GAP",
                    "severity": "warn",
                    "action": "협회 게시 확인 후 crawl_imp_stock_monthly.py (--with-stock)",
                })
            elif stk_holes:
                findings.append({
                    "name": "재고 (중간 월 누락)",
                    "latest": stk_max,
                    "expected": ", ".join(stk_holes[-3:]),
                    "status": "GAP",
                    "severity": "warn",
                    "action": "누락 월 KMTA 등록 여부 확인 후 재수집",
                })
            else:
                findings.append({
                    "name": "재고",
                    "latest": stk_max,
                    "expected": expect_month,
                    "status": "OK",
                    "severity": "info",
                    "action": "-",
                })

    meatbox_dt = _read_meatbox_latest_date()
    if meatbox_dt is None or pd.isna(meatbox_dt):
        findings.append({
            "name": "미트박스 시세",
            "latest": "-",
            "expected": str(today),
            "status": "MISSING",
            "severity": "warn",
            "action": "run_daily_update.py (price-only) 실행",
        })
    else:
        lag_days = (today - meatbox_dt.date()).days
        status = "OK" if lag_days <= 3 else "GAP"
        findings.append({
            "name": "미트박스 시세",
            "latest": meatbox_dt.strftime("%Y-%m-%d"),
            "expected": "당일 또는 전 영업일",
            "status": status,
            "severity": "info" if status == "OK" else "warn",
            "action": "-" if status == "OK" else "미트박스 수집기 재실행",
        })

    if check_usda:
        usda_dt = _read_usda_latest_date()
        if usda_dt is None or pd.isna(usda_dt):
            findings.append({
                "name": "USDA 시세",
                "latest": "-",
                "expected": "전 영업일",
                "status": "MISSING",
                "severity": "warn",
                "action": "api_us_beef_collect_usda.py 실행",
            })
        else:
            lag_days = (today - usda_dt.date()).days
            status = "OK" if lag_days <= 5 else "GAP"
            findings.append({
                "name": "USDA 시세",
                "latest": usda_dt.strftime("%Y-%m-%d"),
                "expected": "전 영업일",
                "status": status,
                "severity": "info" if status == "OK" else "warn",
                "action": "-" if status == "OK" else "USDA 수집 + 전처리 실행",
            })

        exch_dt = _read_exchange_latest_date()
        if exch_dt is None or pd.isna(exch_dt):
            findings.append({
                "name": "환율",
                "latest": "-",
                "expected": str(today),
                "status": "MISSING",
                "severity": "warn",
                "action": "crawl_com_usd_krw.py 실행",
            })
        else:
            lag_days = (today - exch_dt.date()).days
            status = "OK" if lag_days <= 3 else "GAP"
            findings.append({
                "name": "환율",
                "latest": exch_dt.strftime("%Y-%m-%d"),
                "expected": "당일 또는 전일",
                "status": status,
                "severity": "info" if status == "OK" else "warn",
                "action": "-" if status == "OK" else "환율 수집기 재실행",
            })

    # 거시지표 (Macro) — full 모드에서만 점검. 키 미설정 시 파일이 없을 수 있어 SKIP(info) 처리.
    # WTI는 일별이지만 옥수수·CPI·PPI는 월별 → 월 지표 발표 지연 감안해 40일 lag 까지 허용.
    if check_usda:
        macro_dt = _read_macro_latest_date()
        if macro_dt is None or pd.isna(macro_dt):
            findings.append({
                "name": "거시지표(Macro)",
                "latest": "-",
                "expected": "FRED/ECOS 키 설정 시",
                "status": "SKIP",
                "severity": "info",
                "action": ".env 에 FRED_API_KEY / ECOS_API_KEY 설정 후 --full 재실행",
            })
        else:
            lag_days = (today - macro_dt.date()).days
            status = "OK" if lag_days <= 40 else "GAP"
            findings.append({
                "name": "거시지표(Macro)",
                "latest": macro_dt.strftime("%Y-%m-%d"),
                "expected": "월 지표 발표 지연 감안(≤40일)",
                "status": status,
                "severity": "info" if status == "OK" else "warn",
                "action": "-" if status == "OK" else "collect_macro_fred/ecos 재실행",
            })

    # 한우 (EKAPE 경락) — 영업일 기준, 미국 USDA와 유사하게 5일 lag 까지 허용
    han_dt = _read_hanwoo_latest_date()
    if han_dt is None or pd.isna(han_dt):
        findings.append({
            "name": "한우 경락",
            "latest": "-",
            "expected": "전 영업일",
            "status": "MISSING",
            "severity": "warn",
            "action": "crawl_han_auction_api.py 실행 (EKAPE_API_KEY 필요)",
        })
    else:
        lag_days = (today - han_dt.date()).days
        status = "OK" if lag_days <= 5 else "GAP"
        findings.append({
            "name": "한우 경락",
            "latest": han_dt.strftime("%Y-%m-%d"),
            "expected": "전 영업일",
            "status": status,
            "severity": "info" if status == "OK" else "warn",
            "action": "-" if status == "OK" else "crawl_han_auction_api.py 재실행",
        })

    return findings


def _print_gap_report(findings: list[dict]) -> int:
    """GAP 리포트를 출력하고 warn 이상 건수를 반환한다."""
    print(f"\n{'=' * 60}")
    print("  [GAP 검증] 데이터 최신성 리포트")
    print(f"  기준 전월: {_expected_previous_month()}")
    print(f"{'=' * 60}")
    print(f"{'항목':<18} {'최신':<14} {'기대':<18} {'상태':<8} 조치")
    print("-" * 60)
    warn_count = 0
    for row in findings:
        if row["status"] != "OK":
            warn_count += 1
        print(
            f"{row['name']:<18} {str(row['latest']):<14} {str(row['expected']):<18} "
            f"{row['status']:<8} {row['action']}"
        )
    print("-" * 60)
    if warn_count == 0:
        print("[GAP] 이상 없음")
    else:
        print(f"[GAP] 주의 {warn_count}건 — 위 조치 열을 참고하세요.")
    return warn_count


def _import_has_gap() -> bool:
    expect = _expected_previous_month()
    months = _read_import_months()
    if not months:
        return True
    return _month_key_to_int(months[-1]) < _month_key_to_int(expect)


def run_gap_check_only() -> tuple[int, int]:
    """GAP 검증만 수행한다."""
    findings = check_data_gaps(check_monthly=True, check_usda=True)
    warns = _print_gap_report(findings)
    return 1, warns


def run_monthly(include_stock: bool = False, remediate_import: bool = True):
    """
    월별 수집 (매월 10·20일 권장).
    기본: KMTA 수입량만 수집 (재고는 --with-stock 시에만, 소요 시간 큼).
    수입 GAP 시 remediate_import=True 이면 식약처 보완을 시도한다.
    """
    print("=" * 60)
    print("  모드: --monthly (월별 수집 + GAP 검증)")
    if include_stock:
        print("  재고 수집: 포함 (--with-stock)")
    else:
        print("  재고 수집: 제외 (기본 — 소요 시간 큼)")
    print("=" * 60)

    total, success, fail = 0, 0, 0

    total += 1
    if _run_step("[월별] KMTA 수입량", IMPORT_VOLUME_SCRIPT, critical=False):
        success += 1
    else:
        fail += 1

    if include_stock:
        total += 1
        if _run_step("[월별] KMTA 재고", STOCK_SCRIPT, critical=False):
            success += 1
        else:
            fail += 1

    if remediate_import and _import_has_gap():
        print("\n[보완] 수입량이 전월 기준 미달 — 식약처 검역 실적으로 보완 시도")
        total += 1
        if _run_step("[보완] 식약처 수입 검역", FOOD_SAFETY_SCRIPT, critical=False):
            success += 1
        else:
            fail += 1

    return total, success, fail


def run_price_only():
    """미트박스 + 한우(EKAPE) 일일 가격 파이프라인.

    - 미트박스: critical (실패 시 중단)
    - 한우(EKAPE) 수집·전처리: non-critical (실패해도 미트박스 결과는 보존)
    - KAMIS는 키가 있을 때만 자동 수집 (수집기 자체가 graceful skip)
    """
    print("=" * 60)
    print("  모드: --price-only (미트박스 + 한우 일일 파이프라인)")
    print("=" * 60)

    total, success, fail = 0, 0, 0

    label, path = DAILY_COLLECTORS[0]
    total += 1
    if not _run_step_with_retry(f"[수집] {label}", path, max_attempts=3, critical=True):
        fail += 1
        return total, success, fail
    success += 1

    for label, path in COMMON_PROCESSORS:
        total += 1
        if not _run_step(f"[전처리] {label}", path, critical=True):
            fail += 1
            return total, success, fail
        success += 1

    # 환율 (매일 제공 — 기본 일일 수집에 포함, non-critical)
    total += 1
    if _run_step("[수집] USD/KRW 환율", _collector("crawl_com_usd_krw.py"), critical=False):
        success += 1
    else:
        fail += 1

    # 한우·돼지 (일별) — non-critical
    for han_label, han_path in (
        ("EKAPE 한우 경락가격·도축두수", _collector("crawl_han_auction_api.py")),
        ("KAMIS 한우 도/소매가 (키 없으면 skip)", _collector("collect_kamis_hanwoo.py")),
        ("KAMIS 돼지 도/소매가 (키 없으면 skip)", _collector("collect_kamis_pork.py")),
    ):
        total += 1
        if _run_step(f"[일별 축산] {han_label}", han_path, critical=False):
            success += 1
        else:
            fail += 1

    for label, path in HANWOO_PROCESSORS:
        total += 1
        if _run_step(f"[전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

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

    print(f"\n{'='*60}")
    print("  [1] 일별 데이터 수집")
    print(f"{'='*60}")
    for label, path in DAILY_COLLECTORS:
        total += 1
        run_ok = (
            _run_step_with_retry(f"[일별 수집] {label}", path, max_attempts=3, critical=False)
            if path == MEATBOX_SCRIPT
            else _run_step(f"[일별 수집] {label}", path, critical=False)
        )
        if run_ok:
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [2] 월별 데이터 수집")
    print(f"{'='*60}")
    for label, path in MONTHLY_COLLECTORS:
        total += 1
        if _run_step(f"[월별 수집] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [2-1] 거시지표 수집 (Macro — FRED·ECOS)")
    print(f"{'='*60}")
    for label, path in MACRO_COLLECTORS:
        total += 1
        if _run_step(f"[Macro 수집] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [3] USDA 전처리")
    print(f"{'='*60}")
    for label, path in USDA_PROCESSORS:
        total += 1
        if _run_step(f"[USDA 전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [4] 미트박스 전처리")
    print(f"{'='*60}")
    for label, path in COMMON_PROCESSORS:
        total += 1
        if _run_step(f"[전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [5] 한우 전처리")
    print(f"{'='*60}")
    for label, path in HANWOO_PROCESSORS:
        total += 1
        if _run_step(f"[전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [5-1] 거시지표 전처리 (Macro)")
    print(f"{'='*60}")
    for label, path in MACRO_PROCESSORS:
        total += 1
        if _run_step(f"[전처리] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [5-2] 삼겹양지 분석·예측·시그널")
    print(f"{'='*60}")
    for label, path in ANALYSIS_PROCESSORS:
        total += 1
        if _run_step(f"[분석] {label}", path, critical=False):
            success += 1
        else:
            fail += 1

    print(f"\n{'='*60}")
    print("  [6] 문서 갱신")
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
  python src/run_daily_update.py                    미트박스 + GAP 리포트 (기본)
  python src/run_daily_update.py --full             전체 수집 + 전처리 + GAP
  python src/run_daily_update.py --monthly          월별 수입 + GAP (재고 제외, 10·20일 권장)
  python src/run_daily_update.py --monthly --with-stock   월별 수입 + 재고 (재고는 시간 소요 큼)
  python src/run_daily_update.py --gap-check          GAP 검증만

성공 시(수집 단계 실패 0) data/, docs/DATA_DICTIONARY.md 가 자동 커밋됩니다.
  --no-commit          커밋 생략
  --no-gap-check       종료 시 GAP 리포트 생략
  --no-remediate-import  --monthly 시 식약처 자동 보완 생략
  --push               커밋 후 origin push
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
    group.add_argument(
        "--monthly",
        action="store_true",
        help="월별 수집 (기본: KMTA 수입만) + GAP 검증. 매월 10·20일 권장",
    )
    group.add_argument(
        "--gap-check",
        action="store_true",
        help="데이터 GAP 검증만 수행 (수집 없음)",
    )
    parser.add_argument(
        "--with-stock",
        action="store_true",
        help="--monthly 시 KMTA 재고 수집 포함 (소요 시간 큼)",
    )
    parser.add_argument(
        "--no-remediate-import",
        action="store_true",
        help="--monthly 시 수입 GAP이어도 식약처 보완을 실행하지 않음",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="모든 단계가 성공해도 Git 커밋하지 않음",
    )
    parser.add_argument(
        "--no-gap-check",
        action="store_true",
        help="파이프라인 종료 시 GAP 검증 리포트를 출력하지 않음",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="커밋 후 git push (또는 PIPELINE_GIT_PUSH=1)",
    )
    args = parser.parse_args()

    pipeline_start = time.time()

    gap_warns = 0

    if args.gap_check:
        total, gap_warns = run_gap_check_only()
        success, fail = 1, 0
        mode_label = "gap-check"
    elif args.monthly:
        day = datetime.now().day
        if day not in MONTHLY_RETRY_DAYS:
            print(
                f"[안내] 오늘은 {day}일입니다. 월별 수집은 매월 10·20일 실행을 권장합니다."
            )
        total, success, fail = run_monthly(
            include_stock=args.with_stock,
            remediate_import=not args.no_remediate_import,
        )
        mode_label = "monthly"
    elif args.full:
        total, success, fail = run_full()
        mode_label = "full"
    else:
        total, success, fail = run_price_only()
        mode_label = "price-only"

    if not args.no_gap_check and mode_label != "gap-check":
        check_monthly = mode_label in ("full", "monthly")
        check_usda = mode_label == "full"
        findings = check_data_gaps(check_monthly=check_monthly, check_usda=check_usda)
        gap_warns = _print_gap_report(findings)

    # 전체 데이터 신선도 현황판 (모든 실행 끝에 항상 출력 — 지표별 최신일자·주기·지연)
    _run_step("[현황] 데이터 신선도 현황판", _util("data_status.py"), critical=False)

    elapsed = time.time() - pipeline_start

    print(f"\n{'=' * 60}")
    print(f"  파이프라인 완료  |  총 {total}단계  |  성공 {success}  |  실패 {fail}  |  {elapsed:.1f}초")
    if gap_warns and not args.no_gap_check:
        print(f"  GAP 주의       |  {gap_warns}건 (리포트 참고)")
    print(f"{'=' * 60}")
    if fail == 0:
        print("모든 수집·전처리 단계가 정상적으로 완료되었습니다.")
        want_push = args.push or os.environ.get("PIPELINE_GIT_PUSH", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        _try_git_commit_and_push(
            mode_label,
            do_commit=not args.no_commit and mode_label != "gap-check",
            do_push=want_push,
        )
    else:
        print(f"[!] {fail}개 단계에서 오류가 발생했습니다. 위 로그를 확인하세요.")
    raise SystemExit(0 if fail == 0 else 1)


if __name__ == "__main__":
    main()
