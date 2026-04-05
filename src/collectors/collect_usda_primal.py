import requests
import pandas as pd
import os
import time
import urllib3
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import USDA_PRIMAL_HISTORY_CSV, ensure_dirs

# [파일 정의서]
# - 파일명: collect_usda_primal.py
# - 역할: 수집
# - 대상: 수입육 거시 지표 (Composite Primal Values) 전체 데이터
# - 데이터 소스: USDA AMS Datamart API (Slug 2453)
# - 주요 기능: 2019년부터 현재까지의 거시 부위별(Short Plate 포함) 초이스/셀렉트 가치 일괄 수집

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ensure_dirs()
OUTPUT_FILE = USDA_PRIMAL_HISTORY_CSV

def collect_all_primal_data():
    print("=" * 60)
    print("[수집 시작] USDA Composite Primal Values 전체 과거 데이터")
    print("=" * 60)

    # 기획자님이 찾아낸 100% 정확한 엔드포인트
    base_url = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/Composite%20Primal%20Values"
    
    current_year = pd.Timestamp.today().year
    years = range(2019, current_year + 1)
    all_data = []

    for year in years:
        start_date = f"01/01/{year}"
        end_date = f"12/31/{year}"
        
        if year == current_year:
            end_date = pd.Timestamp.today().strftime('%m/%d/%Y')

        query_url = f"{base_url}?q=report_date={start_date}:{end_date}"
        print(f" - [{year}년] 데이터 추출 중... ({start_date} ~ {end_date})")
        
        try:
            response = requests.get(query_url, timeout=30, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and len(data['results']) > 0:
                    all_data.extend(data['results'])
                    print(f"   └ 성공: {len(data['results'])}건 수집 완료")
                else:
                    print("   └ 해당 기간 데이터 없음")
            else:
                print(f"   └ [에러] 상태 코드 {response.status_code}")
        except Exception as e:
            print(f"   └ [예외 발생] {e}")
        
        time.sleep(2) # USDA 서버 밴 방지용 휴식

    if not all_data:
        print("\n[실패] 수집된 데이터가 없습니다.")
        return

    # DataFrame으로 변환 후 CSV 저장
    df = pd.DataFrame(all_data)
    df.to_csv(str(OUTPUT_FILE), index=False, encoding='utf-8-sig')
    print("=" * 60)
    print(f"[수집 완료] 총 {len(df)}건의 Primal 데이터 적재 성공!")
    print(f"[저장 위치] {OUTPUT_FILE.resolve()}")
    print("=" * 60)
    
    # 우리가 가장 기다렸던 Short Plate 데이터가 잘 들어왔는지 최종 검증
    plate_data = df[df['primal_desc'].str.contains('plate', case=False, na=False)]
    print(f"\n[최종 검증] 데이터 내 'Short Plate(우삼겹)' 관련 행 개수: {len(plate_data)}건 확인 완료!")

if __name__ == "__main__":
    collect_all_primal_data()