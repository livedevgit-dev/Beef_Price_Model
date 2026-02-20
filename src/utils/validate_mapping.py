import pandas as pd
import os

# [파일 정의서]
# - 파일명: src/utils/validate_mapping.py
# - 역할: 매핑 정합성 검증 및 결과 파일 생성
# - 저장: data/1_processed/validation_mapping_result.csv

def validate_mapping():
    print("🔍 [Validation] 데이터 매핑 정합성 검사를 시작합니다...\n")
    
    # 1. 경로 설정
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raw_dir = os.path.join(base_dir, 'data', '0_raw')
    processed_dir = os.path.join(base_dir, 'data', '1_processed')
    
    beef_path = os.path.join(raw_dir, 'usda_choice_cuts_history.csv')
    master_path = os.path.join(processed_dir, 'master_price_data.csv')

    # 2. 데이터 로드
    if not os.path.exists(beef_path):
        print("❌ USDA Raw 데이터가 없습니다.")
        return
    
    df_beef = pd.read_csv(beef_path)
    
    # Master 파일 로드
    master_parts = set()
    if os.path.exists(master_path):
        df_master = pd.read_csv(master_path)
        name_col = next((c for c in df_master.columns if 'part' in c or '품목' in c), None)
        if name_col:
            master_parts = set(df_master[name_col].unique())
            print(f"✅ Master 데이터 로드 완료 ({len(master_parts)}개 품목 기준)")

    # 3. 매핑 규칙 정의
    mapping_rules = [
        ('116A', '알목심-미국'),      # Chuck Roll
        ('123A', 'LA갈비-미국'),      # Short Rib
        ('112A', '꽃등심-미국'),      # Ribeye
        ('180',  '채끝-미국'),        # Strip Loin
        ('120',  '차돌양지-미국'),    # Brisket
        ('114D', '부채살-미국'),      # Top Blade
        ('124',  '등갈비/백립-미국'), # Back Ribs
        ('167A', '도가니살-미국'),    # Knuckle
        ('121C', '안창살-미국'),      # Outside Skirt
        ('121D', '안창살-미국'),      # Inside Skirt
    ]

    def apply_mapping(desc):
        for code, name in mapping_rules:
            if code in str(desc):
                return name, code
        return 'Unmapped', None

    # 4. 매핑 적용
    print("🔄 매핑 시뮬레이션 중...")
    df_beef[['korean_name', 'matched_code']] = df_beef['item_description'].apply(
        lambda x: pd.Series(apply_mapping(x))
    )

    # 5. 상세 분석 리포트 생성 (중복 제거된 품목 단위)
    # USDA 원본 품목명 기준으로 유니크한 리스트 생성
    unique_items = df_beef[['matched_code', 'korean_name', 'item_description']].drop_duplicates(subset=['item_description']).copy()
    
    # 검증 로직 추가
    results = []
    for _, row in unique_items.iterrows():
        k_name = row['korean_name']
        orig_desc = row['item_description']
        code = row['matched_code']
        
        status = ""
        note = ""

        if k_name == 'Unmapped':
            status = "⚠️ 매핑 제외"
            note = "분석 대상 아님 (필요 시 규칙 추가)"
        else:
            # Master 파일에 존재하는지 확인
            is_found = False
            if master_parts:
                if any(k_name in str(m_part) for m_part in master_parts):
                    is_found = True
            
            if is_found:
                status = "✅ 정상 (Ready)"
                note = "Master 파일과 연결 가능"
            else:
                status = "❌ 이름 불일치"
                note = f"'{k_name}'이 Master 파일에 없음"

        results.append({
            'USDA_Code': code,
            'Korean_Name': k_name,
            'Status': status,
            'Original_Description': orig_desc,
            'Note': note
        })

    # 6. CSV 저장
    df_result = pd.DataFrame(results)
    
    # 보기 좋게 정렬 (매핑된 것 먼저, 그 다음 제외된 것)
    df_result = df_result.sort_values(by=['Status', 'Korean_Name'], ascending=[True, True])
    
    save_path = os.path.join(processed_dir, 'validation_mapping_result.csv')
    df_result.to_csv(save_path, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 60)
    print(f"📊 [검증 결과 저장 완료]")
    print(f"📂 파일 경로: {save_path}")
    print("=" * 60)
    print("👉 엑셀로 열어서 'Status' 컬럼을 확인하세요.")
    print("   1. '❌ 이름 불일치'가 있으면 매핑 규칙 수정 필요")
    print("   2. '⚠️ 매핑 제외' 중 중요한 부위가 있는지 확인")

if __name__ == "__main__":
    validate_mapping()