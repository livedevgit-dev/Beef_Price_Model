"""
Chrome WebDriver 생성: Selenium 4 Manager로 설치된 Chrome 버전에 맞는 드라이버를 우선 사용.
사내망 등에서 자동 다운로드가 불가하면 환경변수 USE_LOCAL_CHROMEDRIVER=1 과 src/chromedriver.exe 사용.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service


def build_chrome_driver(
    chrome_options: ChromeOptions,
    local_driver_path: Optional[Path] = None,
) -> webdriver.Chrome:
    """
    local_driver_path가 None이면 config.CHROMEDRIVER_PATH를 사용한다.
    USE_LOCAL_CHROMEDRIVER=1 (또는 true/yes)이면 로컬 exe만 사용 (다운로드 없음).
    그 외에는 Service()로 Selenium Manager 자동 매칭 후, 실패 시 로컬 exe로 재시도.
    """
    from config import CHROMEDRIVER_PATH

    path = local_driver_path if local_driver_path is not None else CHROMEDRIVER_PATH
    force_local = os.environ.get("USE_LOCAL_CHROMEDRIVER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    if force_local:
        if not path.exists():
            raise FileNotFoundError(
                f"USE_LOCAL_CHROMEDRIVER=1 이지만 파일이 없습니다: {path}"
            )
        print("[시스템] USE_LOCAL_CHROMEDRIVER=1: 로컬 chromedriver.exe 사용")
        return webdriver.Chrome(
            service=Service(executable_path=str(path)), options=chrome_options
        )

    print("[시스템] Selenium Manager로 Chrome 드라이버 자동 매칭 (설치된 Chrome 버전에 맞춤)")
    try:
        return webdriver.Chrome(service=Service(), options=chrome_options)
    except Exception as e:
        if path.exists():
            print(f"[안내] 자동 매칭 실패 ({e}), 로컬 chromedriver.exe로 재시도...")
            return webdriver.Chrome(
                service=Service(executable_path=str(path)), options=chrome_options
            )
        print(
            "[에러] Chrome을 시작할 수 없습니다. Chrome 설치 여부를 확인하거나 "
            "src/chromedriver.exe를 브라우저 버전에 맞게 교체하세요."
        )
        raise
