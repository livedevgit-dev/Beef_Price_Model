import requests
import pandas as pd
import os
import urllib3 # [추가] 보안 경고 메시지를 제어하는 도구

# ------------------------------------------------------------------
# [설정] 사내망 보안 에러 해결을 위한 설정
# ------------------------------------------------------------------
# "보안 인증서가 이상해요"라는 경고 메시지를 숨깁니다.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://www.meatbox.co.kr/fo/sise/getSiseChartInfoList.json"

payload = {
    'siseSeq': '43084139',   
    'searchPeriod': 'year'   
}
# ------------------------------------------------------------------

def get_meatbox_exact_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.meatbox.co.kr/',
        'Origin': 'https://www.meatbox.co.kr'
    }

    print(f"[요청] 시세번호 [{payload['siseSeq']}] 데이터를 요청 중입니다... (보안 검사 우회)")

    try:
        # [수정] verify=False 옵션을 추가하여 SSL 인증서 검사를 건너뜁니다.
        response = requests.post(url, data=payload, headers=headers, verify=False)

        if response.status_code == 200:
            data_json = response.json()
            
            if 'data' in data_json and 'chartInfoList' in data_json['data']:
                chart_data = data_json['data']['chartInfoList']
                
                df = pd.DataFrame(chart_data)
                
                # 경로 설정
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_dir)
                save_dir = os.path.join(project_root, 'data', '0_raw')
                
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                
                file_name = f"meatbox_sise_{payload['siseSeq']}.xlsx"
                save_path = os.path.join(save_dir, file_name)
                
                df.to_excel(save_path, index=False)
                
                print(f"[완료] 성공! 총 {len(df)}일치의 데이터를 가져왔습니다.")
                print(f"[경로] 저장 위치: {save_path}")
                print("\n[데이터 미리보기]")
                print(df[['siseDate', 'price']].head())
                
            else:
                print("[경고] 데이터 구조가 예상과 다릅니다.")
        else:
            print(f"[실패] 요청 실패: 상태 코드 {response.status_code}")

    except Exception as e:
        print(f"[에러] 에러 발생: {e}")

if __name__ == "__main__":
    get_meatbox_exact_data()