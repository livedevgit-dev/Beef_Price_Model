import requests
import pandas as pd
import xml.etree.ElementTree as ET
import os

def get_beef_primal_cut_prices():
    # 1. API 접속 정보 설정 (가이드 문서 v1.1 기준) 
    url = "http://data.ekape.or.kr/openapi-data/service/user/grade/auct/beefGrade"
    
    # 재발급받으신 인증키를 입력하세요.
    service_key = "a8f4ac5762418c8d94aaccf7d88141b9999ad37f1a157f0ef83cf140c58fab09"
    
    # 2. 요청 파라미터 설정 [cite: 15, 20]
    params = {
        'serviceKey': service_key,
        'startYmd': '20240101',      # 경매 시작일
        'endYmd': '20240110',        # 경매 종료일
        'abattCd': '1005',           # 김해축공 (선택 사항)
        'sexCd': '1'                 # 1: 암, 2: 수, 3: 거세 (선택 사항)
    }

    # 방화벽 차단 방지를 위한 헤더 설정
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        print(f"--- 부분육 경락가격 수집 시도 (기간: {params['startYmd']} ~ {params['endYmd']}) ---")
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # 응답 결과 확인 
            result_code = root.find('.//resultCode').text
            result_msg = root.find('.//resultMsg').text
            
            if result_code == '00':
                items = root.findall('.//item')
                if not items:
                    print("데이터가 없습니다. 조건(날짜, 시장코드 등)을 확인해주세요.")
                    return None
                
                # 데이터 파싱 
                data_list = []
                for item in items:
                    row = {child.tag: child.text for child in item}
                    data_list.append(row)
                
                df = pd.DataFrame(data_list)
                print(f"[완료] 성공: {len(df)}건의 부위별 데이터를 수집했습니다.")
                return df
            else:
                print(f"[에러] API 에러: {result_msg} (코드: {result_code})")
        else:
            print(f"[에러] 통신 에러: HTTP {response.status_code}")

    except Exception as e:
        print(f"오류 발생: {e}")
    
    return None

if __name__ == "__main__":
    primal_cut_df = get_beef_primal_cut_prices()
    
    if primal_cut_df is not None:
        # 모델링에 중요한 주요 컬럼만 우선 확인 
        # hanAvg0: 1++등급, hanAvg1: 1+등급, hanAvg2: 1등급 가격
        cols = ['cutmeatName', 'hanAvg0', 'hanAvg1', 'hanAvg2', 'hanBoxCnt']
        display_cols = [c for c in cols if c in primal_cut_df.columns]
        
        print("\n--- 수집 데이터 샘플 (상위 5건) ---")
        print(primal_cut_df[display_cols].head())
        
        # 엑셀 파일 저장
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        save_dir = os.path.join(project_root, "data", "0_raw")
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        save_path = os.path.join(save_dir, "beef_primal_cut_prices.xlsx")
        primal_cut_df.to_excel(save_path, index=False)
        print(f"\n'{save_path}' 파일로 저장되었습니다.")