import pandas as pd
import os

# [파일 정의서]
# - 파일명: anal_compare_missing_v3.py
# - 역할: 분석 (최종 검증)
# - 기능: 정제된 이력 파일(History)과 ID 리스트를 비교하여, 관리 대상 중 ID가 없는 품목 추출

def compare_history_vs_id_list():
    # ------------------------------------------------------------------
    # [1] 파일 경로 설정
    # ------------------------------------------------------------------
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    # 기준 데이터: 정제된 이력 파일 (Processed)
    history_file = os.path.join(project_root, 'data', '1_processed', 'beef_price_history.xlsx')
    
    # 비교 대상: ID 리스트 (Raw)
    id_list_file = os.path.join(project_root, 'data', '0_raw', 'meatbox_id_list.xlsx')
    
    print("📊 [검증 시작] '정제된 이력 데이터' vs 'ID 리스트' 비교\n")

    if not os.path.exists(history_file):
        print(f"❌ [에러] 이력 파일이 없습니다: {history_file}")
        print("   -> 아직 한 번도 데이터 수집/정제를 돌리지 않았을 수 있습니다.")
        return
    if not os.path.exists(id_list_file):
        print(f"❌ [에러] ID 리스트 파일이 없습니다: {id_list_file}")
        return

    # ------------------------------------------------------------------
    # [2] 데이터 로드 및 전처리
    # ------------------------------------------------------------------
    df_hist = pd.read_excel(history_file)
    df_id = pd.read_excel(id_list_file)

    # 이력 파일은 날짜별로 데이터가 쌓여있으므로, 품목명 기준으로 중복을 제거해 '유니크 품목'만 남깁니다.
    # (이미 정제된 파일이라 냉동/수입 필터링은 되어 있다고 가정하지만, 혹시 모르니 확인은 합니다.)
    
    # 유니크 리스트 추출 (품목명 + 원산지 조합)
    df_target = df_hist[['품목명', '원산지']].drop_duplicates().copy()
    
    print(f"   ① 관리 대상 품목 (History Unique): {len(df_target)}개")
    print(f"   ② 확보된 ID 개수 (ID List): {len(df_id)}개")
    print("-" * 50)

    # ------------------------------------------------------------------
    # [3] 정밀 비교 로직
    # ------------------------------------------------------------------
    # 비교를 위해 공백 제거
    id_names_clean = [str(x).replace(" ", "") for x in df_id['item_info'].tolist()]
    
    missing_items = []
    matched_count = 0

    print("🔍 대조 작업 진행 중...", end="")

    for idx, row in df_target.iterrows():
        # 이력 파일의 품목명
        target_name_clean = str(row['품목명']).replace(" ", "")
        
        is_found = False
        
        # ID 리스트 텍스트 안에 포함되는지 확인
        for id_text in id_names_clean:
            # 서로 포함 관계 체크 (유연한 매칭)
            if (target_name_clean in id_text) or (id_text in target_name_clean):
                is_found = True
                break
        
        if is_found:
            matched_count += 1
        else:
            missing_items.append(row['품목명'])
            print("!", end="") # 누락 발생 시 느낌표 출력

    print("\n")

    # ------------------------------------------------------------------
    # [4] 결과 리포트
    # ------------------------------------------------------------------
    print("-" * 50)
    print(f"✅ 매칭 성공: {matched_count}개")
    print(f"❌ 매칭 실패(누락): {len(missing_items)}개")
    print("-" * 50)

    if missing_items:
        print("[누락된 품목 리스트 (Top 10)]")
        for i, item in enumerate(missing_items[:10]):
            print(f"   {i+1}. {item}")
        
        if len(missing_items) > 10:
            print("   ... (이하 생략)")
            
        # 파일 저장
        save_path = os.path.join(project_root, 'data', '2_final', 'missing_check_result.xlsx')
        pd.DataFrame(missing_items, columns=['누락_품목명']).to_excel(save_path, index=False)
        print(f"\n📂 누락 리스트 저장 완료: {save_path}")
        print("💡 팁: 누락된 품목들은 '품절'이거나 '상품명이 변경'되었을 가능성이 높습니다.")
    else:
        print("🎉 [완벽함] 관리 중인 모든 품목의 ID가 정상적으로 확보되었습니다!")
        print("   이제 과거 데이터 수집(Batch Crawling)을 진행하셔도 좋습니다.")

if __name__ == "__main__":
    compare_history_vs_id_list()