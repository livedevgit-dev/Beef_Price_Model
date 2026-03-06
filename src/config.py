"""
프로젝트 경로 및 설정 일원화

모든 모듈은 이 config를 import하여 경로를 사용합니다.
실행 위치와 무관하게 프로젝트 루트를 기준으로 동작합니다.
"""
import os
from pathlib import Path

# 프로젝트 루트 (Beef_Price_Model/)
_this_file = Path(__file__).resolve()
SRC_DIR = _this_file.parent
PROJECT_ROOT = _this_file.parent.parent

# 데이터 폴더
DATA_RAW = PROJECT_ROOT / "data" / "0_raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "1_processed"
DATA_DASHBOARD = PROJECT_ROOT / "data" / "2_dashboard"

# 주요 파일 경로 (편의용)
MASTER_PRICE_CSV = DATA_PROCESSED / "master_price_data.csv"
DASHBOARD_READY_CSV = DATA_DASHBOARD / "dashboard_ready_data.csv"
MASTER_IMPORT_VOLUME_CSV = DATA_RAW / "master_import_volume.csv"
BEEF_STOCK_XLSX = DATA_RAW / "beef_stock_data.xlsx"
EXCHANGE_RATE_XLSX = DATA_RAW / "exchange_rate_data.xlsx"
USDA_BEEF_HISTORY_CSV = DATA_RAW / "usda_beef_history.csv"
USDA_PRIMAL_HISTORY_CSV = DATA_RAW / "usda_primal_history.csv"
PROCESSED_USDA_COST_CSV = DATA_PROCESSED / "processed_usda_cost.csv"
USDA_PLATE_USD_KG_CSV = DATA_PROCESSED / "usda_plate_usd_kg.csv"
MANUAL_KOR_PRICE_CSV = DATA_RAW / "manual_kor_price.csv"

# Chromedriver (collectors에서 사용)
CHROMEDRIVER_PATH = SRC_DIR / "chromedriver.exe"

# 미트미플 크롤링에 활용용
RAW_CAFE_CRAWLING_CSV = DATA_RAW / "raw_cafe_b2b_crawling.csv"

def ensure_dirs():
    """필수 데이터 폴더가 없으면 생성"""
    for d in (DATA_RAW, DATA_PROCESSED, DATA_DASHBOARD):
        d.mkdir(parents=True, exist_ok=True)
