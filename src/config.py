# [파일 정의서]
# - 파일명: config.py
# - 역할: 가공
# - 대상: 공통
# - 데이터 소스: 프로젝트 디렉터리 구조 (data/0_raw, 1_processed, 2_dashboard)
# - 주요 기능: PROJECT_ROOT, DATA_* 경로 및 주요 CSV/XLSX 파일 경로를 일원화하여 모든 모듈이 공유

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
DATA_REPORTS = PROJECT_ROOT / "data" / "3_reports"

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
PART_CROSSWALK_CSV = DATA_PROCESSED / "part_crosswalk.csv"
MAPPING_REVIEW_DIR = PROJECT_ROOT / "data" / "3_reports" / "mapping_review"
MANUAL_KOR_PRICE_CSV = DATA_RAW / "manual_kor_price.csv"
SHORT_PLATE_WHOLESALE_XLSX = DATA_RAW / "beef_Short Plate_wholesale_price.xlsx"

# 한우 (Hanwoo) — 국내 시장
# EKAPE 축산물품질평가원 소도체 등급별 경락가격 + 도축장별 두수 (한 API에 둘 다 포함)
HAN_AUCTION_RAW_CSV = DATA_RAW / "han_auction_raw.csv"          # API 원본(long format)
HAN_AUCTION_DAILY_CSV = DATA_PROCESSED / "han_auction_daily.csv"  # 일자 × 등급 × 도매시장 정규화
# KAMIS 한우 도/소매 가격 (한국농수산식품유통공사)
KAMIS_HANWOO_RAW_CSV = DATA_RAW / "kamis_hanwoo_raw.csv"
# 통합 대시보드용 (가격 + 두수 + 7/30일 MA 등)
HANWOO_DASHBOARD_CSV = DATA_DASHBOARD / "hanwoo_dashboard_ready.csv"

# 거시경제 지표 (Macro) — 금리·물가(CPI)·PPI·옥수수·WTI 등 (FRED / ECOS)
# 환율(USD/KRW)은 EXCHANGE_RATE_XLSX 에 이미 있으므로 macro 에서 중복 수집하지 않음
MACRO_RAW_CSV = DATA_RAW / "macro_indicators_raw.csv"             # API 원본(long format)
MACRO_PROCESSED_CSV = DATA_PROCESSED / "macro_indicators_daily.csv"  # 일별 ffill + ma30/yoy/mom
MACRO_DASHBOARD_CSV = DATA_DASHBOARD / "macro_dashboard_ready.csv"   # 가격 데이터와 date 기준 merge용

# 미국 수출선약 (USDA FAS Export Sales/ESR) — 중국/한국 등 국가별 주간 수출 (덤핑 조기경보)
FAS_EXPORT_SALES_CSV = DATA_RAW / "fas_export_sales_raw.csv"
FAS_SIGNAL_CSV = DATA_DASHBOARD / "fas_supply_signal.csv"   # 월별 중국/한국 수출 + 다이버전 경보

# 미국 Cattle on Feed (USDA NASS QuickStats) — 사육두수, 미국 공급 4~6개월 선행지표
US_CATTLE_ON_FEED_CSV = DATA_RAW / "us_cattle_on_feed.csv"

# Chromedriver (collectors에서 사용)
CHROMEDRIVER_PATH = SRC_DIR / "chromedriver.exe"

# 미트미플 크롤링에 활용용
RAW_CAFE_CRAWLING_CSV = DATA_RAW / "raw_cafe_b2b_crawling.csv"

def ensure_dirs():
    """필수 데이터 폴더가 없으면 생성"""
    for d in (DATA_RAW, DATA_PROCESSED, DATA_DASHBOARD, DATA_REPORTS):
        d.mkdir(parents=True, exist_ok=True)
