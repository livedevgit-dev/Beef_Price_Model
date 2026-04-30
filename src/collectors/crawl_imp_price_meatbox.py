# [파일 정의서]
# - 파일명: crawl_imp_price_meatbox.py
# - 역할: 수집
# - 대상: 수입육
# - 데이터 소스: 미트박스
# - 주요 기능: StaleElement 에러를 방지하며 일일 B2B 도매가를 수집하는 로직

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
import time
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from io import StringIO

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED
from utils.selenium_chrome import build_chrome_driver

URL = "https://www.meatbox.co.kr/fo/sise/siseListPage.do"


_CLICK_CLOSE_IN_OVERLAY_JS = """
// "닫기"는 페이지 곳곳에 있을 수 있어, 큰 fixed/absolute 레이어(모달) 안의 것만 클릭
function meatboxClickCloseInOverlay() {
    var xpath = "//*[self::button or self::a][normalize-space()='닫기']";
    var result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    for (var i = 0; i < result.snapshotLength; i++) {
        var el = result.snapshotItem(i);
        var cs = window.getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') < 0.05) continue;
        var r = el.getBoundingClientRect();
        if (r.width < 2 || r.height < 2) continue;
        var p = el.parentElement, depth = 0;
        while (p && depth < 14) {
            var pcs = window.getComputedStyle(p);
            var pr = p.getBoundingClientRect();
            if ((pcs.position === 'fixed' || pcs.position === 'absolute') &&
                pr.width > 260 && pr.height > 120) {
                el.click();
                return true;
            }
            p = p.parentElement;
            depth++;
        }
    }
    return false;
}
return meatboxClickCloseInOverlay();
"""

_BCLOSE_IN_POPUP_JS = """
if (!window.jQuery) return false;
var $hosts = jQuery('.popup_of:visible, .mypop:visible, .notice_pop:visible, .grade_pop:visible')
    .filter(function () { return jQuery(this).outerWidth() > 200; });
if (!$hosts.length) return false;
var $btn = $hosts.find('.b-close:visible').first();
if ($btn.length) { $btn.trigger('click'); return true; }
return false;
"""

def dismiss_meatbox_overlays(driver, rounds: int = 3, send_escape: bool = True) -> None:
    """
    광고·프로모션(Braze 인앱), dim 레이어, bPopup 계열이 시세 테이블을 가리는 경우 제거/닫기.

    .b-close는 팝업 박스(.popup_of 등) 안에서만 클릭한다. 전역 .b-close 클릭은 시세 UI를 망가뜨릴 수 있음.
    send_escape=False이면 ESC 미전송(페이지 넘긴 뒤 반복 호출 시 포커스·UI 간섭 방지).
    """
    close_selectors = (
        "#btnCloseJoinBanner",
        "button.banner_close",
        ".banner_close:not(script)",
        ".search_area .search_con .search_bottom .close",
        ".grade_confirm",
    )
    strip_overlay_js = """
        document.querySelectorAll(
            '.ab-iam-root, .ab-iam-root-v3, iframe[src*="braze"], iframe[src*="appboy"]'
        ).forEach(function(el) { el.remove(); });
        document.body.classList.remove('ab-pause-scrolling');
        document.documentElement.classList.remove('ab-pause-scrolling');
        document.querySelectorAll('.dim-layer').forEach(function(el) { el.remove(); });
    """
    for _ in range(rounds):
        try:
            driver.execute_script(strip_overlay_js)
        except Exception:
            pass
        for sel in close_selectors:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
            except Exception:
                continue
        try:
            driver.execute_script(_BCLOSE_IN_POPUP_JS)
        except Exception:
            pass
        try:
            driver.execute_script(_CLICK_CLOSE_IN_OVERLAY_JS)
        except Exception:
            pass
        if send_escape:
            try:
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
        time.sleep(0.25)


MIN_EXPECTED_PAGES = 20
# 20페이지 미만 구간에서만: 테이블 파싱 실패·다음페이지 미탐지 시 최대 대기(초)
STALL_MAX_SEC = 30
POLL_INTERVAL_SEC = 1.0


def _parse_meatbox_tables_from_html(html: str):
    """미트박스 시세 테이블 후보만 추출. 없으면 None."""
    try:
        dfs = pd.read_html(StringIO(html))
    except Exception:
        return None
    cols_join = lambda df: " ".join([str(c) for c in df.columns])
    candidates = [
        df for df in dfs
        if len(df) > 1 and ("품목" in cols_join(df) or "보관" in cols_join(df))
    ]
    if not candidates:
        return None
    return max(candidates, key=len)


def get_price_data(min_expected_pages: int = MIN_EXPECTED_PAGES) -> bool:
    master_file = DATA_PROCESSED / "master_price_data.csv"
    backup_file = DATA_PROCESSED / "master_price_data_backup_full.csv"
    
    today_date = datetime.now().strftime("%Y-%m-%d")
    target_cols = ['date', 'part_name', 'country', 'wholesale_price', 'brand']

    print("="*60)
    print("[시스템] 미트박스 시세 수집")
    print("="*60)

    # 1. 파일 최적화
    if master_file.exists():
        try:
            shutil.copy(str(master_file), str(backup_file))
            df_master = pd.read_csv(str(master_file))
            for col in target_cols:
                if col not in df_master.columns:
                    df_master[col] = '-' if col == 'brand' else ""
            df_master = df_master[target_cols] 
            cond_empty = df_master['part_name'].isna() | (df_master['part_name'] == '')
            cond_today = df_master['date'] == today_date
            df_master = df_master[~(cond_empty | cond_today)]
            print(f"[파일 정리] 기존 파일 최적화 완료 (잔여 {len(df_master)}행)")
        except Exception as e:
            df_master = pd.DataFrame(columns=target_cols) 
    else:
        df_master = pd.DataFrame(columns=target_cols)

    # 2. 크롤링
    chrome_options = Options()
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--log-level=3")
    # document.complete 대기로 멈춤 방지(분석·추적 스크립트가 끝나지 않는 사이트 대응)
    try:
        chrome_options.page_load_strategy = "eager"
    except Exception:
        pass

    driver = build_chrome_driver(chrome_options)
    driver.set_page_load_timeout(120)
    driver.maximize_window()
    # implicit 대기는 find_elements에도 적용되어, 없는 배너·닫기 셀렉터마다 최대 N초씩 묶임 → 0으로 두고 명시 대기만 사용
    driver.implicitly_wait(0)

    print("[시스템] 미트박스 시세 페이지 로딩...", flush=True)
    try:
        driver.get(URL)
    except TimeoutException:
        print("[경고] page load 타임아웃, 현재 DOM으로 계속합니다.", flush=True)
    time.sleep(1.5)
    print("[시스템] 광고·레이어 정리 중...", flush=True)
    dismiss_meatbox_overlays(driver, rounds=3, send_escape=True)
    print("[시스템] 수집 루프 시작", flush=True)

    raw_dfs = []
    current_page = 1
    crawled_pages = 0
    
    try:
        wait = WebDriverWait(driver, 20)

        while True:
            # 20페이지 미만일 때만: 30초까지 테이블·다음페이지 미준비 상태를 허용하고 재시도
            under_min_pages = current_page < min_expected_pages
            stall_deadline = time.monotonic() + STALL_MAX_SEC if under_min_pages else time.monotonic() + 3.0

            # 초기 진입 후에는 ESC·과한 닫기 클릭을 줄여 시세 테이블·페이지네이션 유지
            dismiss_meatbox_overlays(driver, rounds=1, send_escape=False)

            target_df = None
            print(f"[수집] {current_page}페이지... ", end="", flush=True)
            crawled_pages = current_page

            while time.monotonic() < stall_deadline:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody tr")))
                except TimeoutException:
                    if not under_min_pages:
                        break
                    time.sleep(POLL_INTERVAL_SEC)
                    dismiss_meatbox_overlays(driver, rounds=1, send_escape=False)
                    continue

                time.sleep(1)
                html = driver.page_source
                target_df = _parse_meatbox_tables_from_html(html)
                if target_df is not None:
                    break
                if not under_min_pages:
                    break
                time.sleep(POLL_INTERVAL_SEC)
                dismiss_meatbox_overlays(driver, rounds=1, send_escape=False)

            if target_df is not None:
                raw_dfs.append(target_df)
                print(f"OK ({len(target_df)}건)", flush=True)
            else:
                if under_min_pages:
                    print(f"Skip (시세 테이블 미확인, 최대 {STALL_MAX_SEC}초 대기)", flush=True)
                else:
                    print("Skip", flush=True)

            time.sleep(1.5)
            next_page = current_page + 1
            moved = False
            nav_deadline = time.monotonic() + STALL_MAX_SEC if under_min_pages else time.monotonic() + 5.0

            while time.monotonic() < nav_deadline:
                for attempt in range(3):
                    target_btn = None
                    try:
                        target_btn = driver.find_element(By.XPATH, f"//a[normalize-space()='{next_page}']")
                    except Exception:
                        try:
                            target_btn = driver.find_element(By.XPATH, "//a[contains(@class, 'next')]")
                        except Exception:
                            target_btn = None

                    if target_btn:
                        try:
                            driver.execute_script("arguments[0].click();", target_btn)
                            moved = True
                            break
                        except StaleElementReferenceException:
                            time.sleep(1)
                            continue
                    time.sleep(1)

                if moved:
                    break
                if not under_min_pages:
                    break
                time.sleep(POLL_INTERVAL_SEC)
                dismiss_meatbox_overlays(driver, rounds=1, send_escape=False)

            if moved:
                current_page += 1
            else:
                break
            
    except Exception as e:
        print(f"\n[에러] 크롤링 중단: {e}")
    finally:
        driver.quit()
        
    if crawled_pages < min_expected_pages:
        print(
            f"\n[오류] 페이지 수집 부족: {crawled_pages}페이지 "
            f"(최소 기대 {min_expected_pages}페이지)",
            flush=True,
        )
        print("[오류] 이번 실행을 실패로 처리합니다.", flush=True)
        return False

    # 3. 데이터 저장
    if raw_dfs:
        full_df = pd.concat(raw_dfs, ignore_index=True)
        try:
            clean_df = full_df.iloc[:, [1, 3, 4]].copy()
            clean_df.columns = ['품목명', '보관', '도매시세_raw']
            clean_df['품목명'] = clean_df['품목명'].astype(str).str.replace('관심상품 등록하기', '', regex=False).str.strip()
            clean_df = clean_df[clean_df['보관'].astype(str).str.contains("냉동")]
            clean_df['원산지'] = clean_df['품목명'].apply(lambda x: '미국' if '미국' in str(x) else ('호주' if '호주' in str(x) else '기타'))
            clean_df = clean_df[clean_df['원산지'] != '기타']
            
            def extract_price(text):
                digits = re.sub(r'[^0-9]', '', str(text).split('원')[0])
                return int(digits) if digits else 0
            
            clean_df['도매시세'] = clean_df['도매시세_raw'].apply(extract_price)
            clean_df = clean_df[clean_df['도매시세'] > 0].reset_index(drop=True)

            final_df = pd.DataFrame({
                'date': [today_date] * len(clean_df),
                'part_name': clean_df['품목명'].tolist(),
                'country': clean_df['원산지'].tolist(),
                'wholesale_price': clean_df['도매시세'].tolist(),
                'brand': ['-'] * len(clean_df)
            })
            # 날짜·품목·시세 등 모든 컬럼이 동일한 행은 한 건만 유지 (다중 페이지·재시도로 인한 완전 중복 제거)
            _n_final = len(final_df)
            final_df = final_df.drop_duplicates(keep="first").reset_index(drop=True)
            if len(final_df) < _n_final:
                print(
                    f"[파일 정리] 금일 수집분 내 완전 동일 행 {_n_final - len(final_df)}건 제거",
                    flush=True,
                )

            new_master_df = pd.concat([df_master, final_df], ignore_index=True).sort_values(
                by=["date", "country", "part_name"]
            )
            _n_master = len(new_master_df)
            new_master_df = new_master_df.drop_duplicates(keep="first").reset_index(drop=True)
            if len(new_master_df) < _n_master:
                print(
                    f"[파일 정리] 마스터 병합 후 완전 동일 행 {_n_master - len(new_master_df)}건 제거 "
                    f"(잔여 {len(new_master_df)}행)",
                    flush=True,
                )
            new_master_df.to_csv(str(master_file), index=False, encoding="utf-8-sig")

            print(f"\n[성공] 데이터 저장 완료! (오늘 수집: {len(final_df)}건)")
            return True

        except Exception as e:
            print(f"[오류] 데이터 저장 실패: {e}")
            return False

    print("\n[오류] 수집된 원본 데이터가 없어 저장을 건너뜁니다.")
    return False

if __name__ == "__main__":
    ok = get_price_data()
    raise SystemExit(0 if ok else 1)