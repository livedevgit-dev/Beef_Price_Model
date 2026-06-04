import requests
import pandas as pd
import urllib3
import json

# [파일 정의서]
# - 파일명: preview_primal_data.py
# - 역할: 분석 (데이터 구조 파악)
# - 주요 기능: 기획자님이 찾아낸 정확한 섹션명(Composite Primal Values)으로 샘플 데이터 수집

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def preview_data():
    print("=" * 60)
    print("[프리뷰] USDA Composite Primal Values 데이터 스캔")
    print("=" * 60)

    # 기획자님이 찾아주신 정확한 방 이름으로 URL 수정
    base_url = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports/2453/Composite%20Primal%20Values"
    
    # 확실한 과거 날짜 세팅
    start_str = "01/01/2024"
    end_str = "01/10/2024"
    
    query_url = f"{base_url}?q=report_date={start_str}:{end_str}"
    print(f" - 요청 주소: {query_url}")
    print(f" - 요청 기간: {start_str} ~ {end_str}\n")

    try:
        response = requests.get(query_url, timeout=10, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and len(data['results']) > 0:
                df = pd.DataFrame(data['results'])
                
                print("유레카! 성공적으로 데이터를 가져왔습니다.\n")
                
                print("[1] 제공되는 전체 컬럼(항목) 목록:")
                print(f"  {df.columns.tolist()}\n")
                
                print("[2] 실제 데이터 샘플 (최상단 2줄):")
                sample_dict = df.head(2).to_dict(orient='records')
                print(json.dumps(sample_dict, indent=2, ensure_ascii=False))
                
                # Primal 명칭 확인
                if 'primal_name' in df.columns:
                    print(f"\n[3] 포함된 거시 부위 종류: {df['primal_name'].unique().tolist()}")
                elif 'item_desc' in df.columns:
                    print(f"\n[3] 포함된 거시 부위 종류: {df['item_desc'].unique().tolist()}")

            else:
                print("데이터는 없지만 통신은 성공했습니다.")
        else:
            print(f"API 에러: {response.status_code}")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        
    print("=" * 60)

if __name__ == "__main__":
    preview_data()