# [파일 정의서]
# - 파일명: extract_data_schema.py
# - 역할: 분석
# - 대상: 공통
# - 데이터 소스: 로컬 데이터 폴더 (DATA_RAW, DATA_PROCESSED, DATA_DASHBOARD)
# - 주요 기능: CSV 및 Excel 파일의 구조(컬럼, 타입, 샘플 등)를 분석하여
#              docs/DATA_DICTIONARY.md의 부록 섹션을 자동 갱신

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_RAW, DATA_PROCESSED, DATA_DASHBOARD

MARKER_START = "<!-- AUTO-GENERATED-SCHEMA:START -->"
MARKER_END = "<!-- AUTO-GENERATED-SCHEMA:END -->"


def _build_schema_markdown():
    """데이터 폴더를 스캔하여 자동생성 스키마 마크다운을 반환합니다."""
    target_folders = [DATA_RAW, DATA_PROCESSED, DATA_DASHBOARD]
    lines = []
    lines.append("<!-- 이 영역은 extract_data_schema.py가 자동으로 갱신합니다. 수동 편집하지 마세요. -->")
    lines.append("")
    lines.append("## 부록: 자동생성 컬럼 스키마")
    lines.append("")
    lines.append(f"> 마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("> `python src/utils/extract_data_schema.py` 또는 `python src/run_daily_update.py` 파이프라인에서 자동 갱신")
    lines.append("")

    for folder in target_folders:
        if not folder.exists():
            continue

        lines.append(f"### 폴더: `{folder.name}/`")
        lines.append("")

        valid_extensions = ['.csv', '.xlsx']
        files = sorted(
            [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions],
            key=lambda x: x.name
        )

        if not files:
            lines.append("해당 폴더에 분석할 파일이 없습니다.")
            lines.append("")
            continue

        for file_path in files:
            try:
                if file_path.suffix.lower() == '.csv':
                    df = pd.read_csv(file_path, nrows=5)
                    try:
                        total_rows = sum(1 for _ in open(file_path, 'r', encoding='utf-8', errors='ignore')) - 1
                    except Exception:
                        total_rows = "측정 불가"
                else:
                    df = pd.read_excel(file_path, nrows=5)
                    try:
                        total_rows = len(pd.read_excel(file_path, usecols=[0]))
                    except Exception:
                        total_rows = "측정 불가"

                lines.append(f"#### `{file_path.name}`")
                lines.append(f"- **총 행(Row) 수**: 약 {total_rows}행")
                lines.append("")
                lines.append("| 컬럼명 | 데이터 타입 | 샘플 데이터 1 | 샘플 데이터 2 |")
                lines.append("|---|---|---|---|")

                for col in df.columns:
                    dtype = str(df[col].dtype)
                    sample1 = str(df[col].iloc[0]) if len(df) > 0 else "N/A"
                    sample2 = str(df[col].iloc[1]) if len(df) > 1 else "N/A"
                    sample1 = sample1.replace('|', '/').replace('\n', ' ')
                    sample2 = sample2.replace('|', '/').replace('\n', ' ')
                    lines.append(f"| {col} | {dtype} | {sample1} | {sample2} |")

                lines.append("")

            except Exception as e:
                lines.append(f"#### `{file_path.name}`")
                lines.append(f"- 파일 분석 중 에러 발생: {str(e)}")
                lines.append("")

    return "\n".join(lines)


def extract_schema_to_dictionary():
    """docs/DATA_DICTIONARY.md의 부록 섹션을 자동생성 스키마로 갱신합니다."""
    project_root = DATA_RAW.parent.parent
    docs_folder = project_root / "docs"
    docs_folder.mkdir(exist_ok=True)
    dict_path = docs_folder / "DATA_DICTIONARY.md"

    schema_content = _build_schema_markdown()

    if dict_path.exists():
        existing = dict_path.read_text(encoding='utf-8')

        start_idx = existing.find(MARKER_START)
        end_idx = existing.find(MARKER_END)

        if start_idx != -1 and end_idx != -1:
            before = existing[:start_idx + len(MARKER_START)]
            after = existing[end_idx:]
            new_content = f"{before}\n{schema_content}\n{after}"
        else:
            new_content = existing.rstrip() + f"\n\n{MARKER_START}\n{schema_content}\n{MARKER_END}\n"
    else:
        new_content = f"{MARKER_START}\n{schema_content}\n{MARKER_END}\n"

    dict_path.write_text(new_content, encoding='utf-8')

    print("=" * 60)
    print("[완료] 데이터 스키마가 DATA_DICTIONARY.md 부록에 갱신되었습니다.")
    print(f"저장 위치: {dict_path}")
    print("=" * 60)


if __name__ == "__main__":
    extract_schema_to_dictionary()
