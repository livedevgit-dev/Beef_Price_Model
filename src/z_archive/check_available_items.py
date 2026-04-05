import os
import requests
import pandas as pd
import urllib3
from dotenv import load_dotenv

# [파일 정의서]
# - 파일명: check_available_items.py
# - 역할: 탐색 (Discovery)
# - 목적: 필터링 없이 USDA Choice Cuts의 '모든 품목'을 조회하여 전체 리스트 확보

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

def get_api_key():
    return os.getenv("USDA_API_KEY")

def show_full_menu(slug_id="2453"):
    api_key = get_api_key()
    
    # Choice Cuts 섹션 (모든 부분육이 들어있는 곳)
    url = f"https://mpr.datamart.ams.usda.gov/services/v1.1/reports/{slug_id}/Choice Cuts"
    
    print("USDA 전체 메뉴판(Choice Cuts) 조회 중...")
    
    try:
        response = requests.get(url, auth=(api_key, ''), verify=False)
        data = response.json()
        results = data.get('results', [])
        
        if not results:
            print("데이터가 없습니다.")
            return

        df = pd.DataFrame(results)
        
        # 품목명 컬럼 찾기 (보통 item_description)
        desc_col = next((col for col in df.columns if 'desc' in col.lower()), None)
        
        if desc_col:
            # 중복 제거 후 정렬
            full_menu = sorted(df[desc_col].unique())
            
            print(f"\n[OK] 조회 성공! 총 {len(full_menu)}개의 부위가 발견되었습니다.\n")
            print("=" * 60)
            print(f"{'No.':<4} | 품목명 (Item Description)")
            print("=" * 60)
            
            for i, item in enumerate(full_menu):
                print(f"{i+1:<4} | {item}")
                
            print("=" * 60)
            print("-> 위 목록에서 모니터링하고 싶은 부위 번호나 이름을 알려주세요.")
            
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    show_full_menu()