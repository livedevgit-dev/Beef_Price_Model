import os

# 1. 우리가 만들기로 한 폴더 목록 (계층 구조 포함)
folders = [
    "data/0_raw",        # 원본 데이터 저장소
    "data/1_processed",  # 가공된 데이터 저장소
    "data/2_final",      # 최종 결과물 저장소
    "src",               # 소스 코드 폴더
    "notebooks",         # 테스트용 노트북 폴더
    "docs"               # 문서 저장소
]

# 2. 우리가 만들기로 한 필수 파일 목록
files = [
    ".env",              # API 키 등 비밀번호 저장
    "requirements.txt",  # 설치할 라이브러리 목록
    "README.md",         # 프로젝트 설명서
    "src/data_collector.py", # (미리 생성) 데이터 수집기
    "docs/data_definition.md" # (미리 생성) 데이터 정의서
]

def create_project_structure():
    print(f"🚀 프로젝트 폴더 생성을 시작합니다... (위치: {os.getcwd()})")
    print("-" * 30)

    # 폴더 생성 반복문
    for folder in folders:
        try:
            # exist_ok=True: 이미 폴더가 있어도 에러 내지 말라는 뜻
            os.makedirs(folder, exist_ok=True)
            print(f"✅ 폴더 생성 완료: {folder}")
        except Exception as e:
            print(f"❌ 폴더 생성 실패 ({folder}): {e}")

    # 파일 생성 반복문
    for file in files:
        try:
            # 파일이 없을 때만 생성 (덮어쓰기 방지)
            if not os.path.exists(file):
                with open(file, 'w', encoding='utf-8') as f:
                    pass # 내용은 비워둠
                print(f"✅ 파일 생성 완료: {file}")
            else:
                print(f"ℹ️ 파일 이미 있음 (건너뜀): {file}")
        except Exception as e:
            print(f"❌ 파일 생성 실패 ({file}): {e}")
            
    print("-" * 30)
    print("✨ 모든 준비가 완료되었습니다!")

if __name__ == "__main__":
    create_project_structure()