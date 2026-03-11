# [파일 정의서]
# - 파일명: extract_data_schema.py
# - 역할: 분석
# - 대상: 공통
# - 데이터 소스: 로컬 데이터 폴더 (DATA_RAW, DATA_PROCESSED)
# - 주요 기능: CSV 및 Excel 파일의 구조(컬럼, 타입, 샘플 등)를 분석하여 마크다운 문서로 요약

import pandas as pd
import os
from pathlib import Path
import sys

# [핵심 수정] 파이썬이 모듈을 찾는 경로를 현재 파일 기준 1칸 위('src' 폴더)로 지정합니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, DATA_PROCESSED

def extract_schema_to_markdown():
    target_folders = [DATA_RAW, DATA_PROCESSED]
    
    # 문서 저장 경로 설정 (docs 폴더가 없으면 생성)
    project_root = DATA_RAW.parent.parent
    docs_folder = project_root / "docs"
    docs_folder.mkdir(exist_ok=True)
    
    output_file = docs_folder / "data_schema_summary.md"
    
    markdown_content = ["# 프로젝트 데이터 스키마 요약\n"]
    markdown_content.append("이 문서는 데이터 폴더 내 파일들의 구조를 자동으로 분석한 결과입니다.\n\n")
    
    for folder in target_folders:
        if not folder.exists():
            continue
            
        markdown_content.append(f"## 폴더: {folder.name}\n")
        
        # 폴더 내 csv, xlsx 파일 검색
        valid_extensions = ['.csv', '.xlsx']
        files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions]
        
        if not files:
            markdown_content.append("해당 폴더에 분석할 파일이 없습니다.\n\n")
            continue
            
        for file_path in files:
            try:
                if file_path.suffix.lower() == '.csv':
                    df = pd.read_csv(file_path, nrows=5)
                    try:
                        total_rows = sum(1 for _ in open(file_path, 'r', encoding='utf-8', errors='ignore')) - 1
                    except:
                        total_rows = "측정 불가"
                else:
                    df = pd.read_excel(file_path, nrows=5)
                    try:
                        total_rows = len(pd.read_excel(file_path, usecols=[0]))
                    except:
                        total_rows = "측정 불가"
                
                markdown_content.append(f"### 파일명: `{file_path.name}`\n")
                markdown_content.append(f"- **총 행(Row) 수**: 약 {total_rows}행\n\n")
                
                # 컬럼 정보 테이블 생성
                markdown_content.append("| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |\n")
                markdown_content.append("|---|---|---|---|\n")
                
                for col in df.columns:
                    dtype = str(df[col].dtype)
                    sample1 = str(df[col].iloc[0]) if len(df) > 0 else "N/A"
                    sample2 = str(df[col].iloc[1]) if len(df) > 1 else "N/A"
                    
                    # 마크다운 표 깨짐 방지
                    sample1 = sample1.replace('|', '/').replace('\n', ' ')
                    sample2 = sample2.replace('|', '/').replace('\n', ' ')
                    
                    markdown_content.append(f"| {col} | {dtype} | {sample1} | {sample2} |\n")
                
                markdown_content.append("\n---\n\n")
                
            except Exception as e:
                markdown_content.append(f"### 파일명: `{file_path.name}`\n")
                markdown_content.append(f"- 파일 분석 중 에러 발생: {str(e)}\n\n")
                markdown_content.append("\n---\n\n")

    # 결과 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(markdown_content)
        
    print("============================================================")
    print(f"[완료] 데이터 스키마 요약 문서가 생성되었습니다.")
    print(f"저장 위치: {output_file}")
    print("============================================================")

if __name__ == "__main__":
    extract_schema_to_markdown()