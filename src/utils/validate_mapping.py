# [파일 정의서]
# - 파일명: validate_mapping.py
# - 역할: 가공
# - 대상: 수입육
# - 데이터 소스: PROJECT_GUIDE.md, DATA_DICTIONARY.md
# - 주요 기능: USDA 시세 원본 명칭(Original_Description)과 한국 부위 명칭(Korean_Name) 간의 매핑을 검증하고, 결과를 validation_mapping_result.csv로 출력

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATA_PROCESSED, MASTER_PRICE_CSV, USDA_BEEF_HISTORY_CSV, ensure_dirs
from utils.part_mapping import build_usda_code_to_korean_map

OUTPUT_COLUMNS = [
    "USDA_Code",
    "Original_Description",
    "Korean_Name",
    "Status",
    "Note",
]

# USDA 품목 코드 -> 미트박스 표준 품목명 (part_mapping.CANONICAL_PARTS 기준)
USDA_CODE_TO_KOREAN = build_usda_code_to_korean_map()

# 코드 추출 실패 시 영문 설명 키워드로 보조 매핑
KEYWORD_RULES = [
    (("brisket",), "차돌양지-미국"),
    (("short plate", "short rib"), "LA갈비-미국"),
    (("chuck", "short rib"), "앞/척갈비-미국"),
    (("chuck", "roll"), "알목심-미국"),
    (("chuck", "top blade"), "부채살-미국"),
    (("rib", "ribeye"), "꽃등심-미국"),
    (("strip loin",), "센터컷-미국"),
    (("strip,", "bnls"), "센터컷-미국"),
]

# 분석 대상에서 제외할 USDA 코드 (우둔·안심·플랭크 등)
EXCLUDED_CODES = {
    "113C", "114", "114A", "114E", "114F", "116B", "116G",
    "160", "161", "167A", "168", "169", "169A", "170", "171B", "171C",
    "174", "184", "184B", "185A", "185B", "185C", "185D",
    "189A", "191A", "193",
}

USDA_CODE_PATTERN = re.compile(r"\(\s*([0-9]+[A-Z]?)\s+\d+\)")


def extract_usda_code(description: str) -> str:
    match = USDA_CODE_PATTERN.search(str(description))
    return match.group(1) if match else ""


def _match_keyword_rule(description: str) -> str:
    desc_lower = str(description).lower()
    for keywords, korean_name in KEYWORD_RULES:
        if all(keyword in desc_lower for keyword in keywords):
            return korean_name
    return ""


def apply_mapping(description: str) -> tuple[str, str]:
    code = extract_usda_code(description)

    if code and code in USDA_CODE_TO_KOREAN:
        return USDA_CODE_TO_KOREAN[code], code

    korean_by_keyword = _match_keyword_rule(description)
    if korean_by_keyword:
        return korean_by_keyword, code

    return "", code


def _load_master_part_bases() -> set[str]:
    if not MASTER_PRICE_CSV.exists():
        return set()

    df_master = pd.read_csv(str(MASTER_PRICE_CSV), encoding="utf-8-sig")
    if "part_name" not in df_master.columns:
        return set()

    bases = set()
    for part_name in df_master["part_name"].dropna().astype(str):
        base = part_name.split("|")[0].strip()
        if base.endswith("-미국"):
            base = base[: -len("-미국")]
        bases.add(base)
    return bases


def _korean_base_name(korean_name: str) -> str:
    if not korean_name:
        return ""
    return korean_name.replace("-미국", "").strip()


def _is_in_master(korean_name: str, master_bases: set[str]) -> bool:
    base = _korean_base_name(korean_name)
    if not base:
        return False
    if base in master_bases:
        return True
    return any(base in master_base or master_base in base for master_base in master_bases)


def _is_excluded(code: str, description: str) -> bool:
    if code in EXCLUDED_CODES:
        return True
    # 코드가 비어 있고 Round/Loin/Flank 등 비핵심 프라이멀만 언급된 경우
    if not code:
        desc_lower = str(description).lower()
        excluded_primals = ("round,", "loin,", "flank,")
        return any(primal in desc_lower for primal in excluded_primals)
    return False


def _excluded_note(description: str) -> str:
    desc_lower = str(description).lower()
    if desc_lower.startswith("chuck,"):
        return "척 세부 부위 (알목심·LA갈비 외, 분석 제외)"
    if desc_lower.startswith("round,"):
        return "우둔(Round) 세부 부위 (분석 제외)"
    if desc_lower.startswith("loin,"):
        return "등심/채끝(Loin) 세부 부위 (분석 제외)"
    if desc_lower.startswith("flank,"):
        return "플랭크 부위 (분석 제외)"
    return "분석 대상 부위 아님"


def _build_note(code: str, description: str, korean_name: str, status: str) -> str:
    if status == "정상":
        return "Master 품목명과 연결 가능"
    if status == "이름 불일치":
        base = _korean_base_name(korean_name)
        if base == "꽃등심":
            return (
                "리브아이 -> 꽃등심 매핑 적용. "
                "Master에 꽃등심 품목 없음 (등갈비/백립과 별도 부위)"
            )
        return f"'{korean_name}'이 Master 파일에 없음"
    if status == "매핑 제외":
        if code in EXCLUDED_CODES or _is_excluded(code, description):
            return _excluded_note(description)
        return "매핑 규칙 미정의 (필요 시 USDA_CODE_TO_KOREAN에 추가)"
    if status == "확인 필요":
        return "매핑 규칙 또는 Master 대응명 확인 필요"
    return ""


def classify_row(
    code: str,
    description: str,
    korean_name: str,
    master_bases: set[str],
) -> tuple[str, str]:
    if korean_name:
        if _is_in_master(korean_name, master_bases):
            status = "정상"
        else:
            status = "이름 불일치"
        note = _build_note(code, description, korean_name, status)
        return status, note

    status = "매핑 제외"

    note = _build_note(code, description, korean_name, status)
    return status, note


def validate_mapping() -> pd.DataFrame | None:
    print("[Validation] USDA-한국 부위명 매핑 검증을 시작합니다.\n")

    if not USDA_BEEF_HISTORY_CSV.exists():
        print(f"USDA 원본 파일이 없습니다: {USDA_BEEF_HISTORY_CSV}")
        return None

    df_beef = pd.read_csv(str(USDA_BEEF_HISTORY_CSV), usecols=["item_description"])
    desc_col = "item_description"
    df_beef = df_beef[
        df_beef[desc_col].notna()
        & (df_beef[desc_col].astype(str).str.strip() != "")
    ]

    master_bases = _load_master_part_bases()
    if master_bases:
        print(f"Master 품목 기준 로드 완료 ({len(master_bases)}개 부위)")
    else:
        print("Master 파일이 없거나 part_name 컬럼을 찾지 못했습니다. 이름 불일치 검증은 생략됩니다.")

    print("매핑 규칙 적용 중...")
    mapped = df_beef[desc_col].apply(
        lambda desc: pd.Series(apply_mapping(desc), index=["Korean_Name", "USDA_Code"])
    )
    unique_items = (
        pd.concat([df_beef[[desc_col]], mapped], axis=1)
        .drop_duplicates(subset=[desc_col])
        .rename(columns={desc_col: "Original_Description"})
    )

    results = []
    for _, row in unique_items.iterrows():
        code = row["USDA_Code"] or ""
        korean_name = row["Korean_Name"] or ""
        description = row["Original_Description"]
        status, note = classify_row(code, description, korean_name, master_bases)
        results.append(
            {
                "USDA_Code": code,
                "Original_Description": description,
                "Korean_Name": korean_name,
                "Status": status,
                "Note": note,
            }
        )

    df_result = pd.DataFrame(results, columns=OUTPUT_COLUMNS)

    status_order = {"정상": 0, "이름 불일치": 1, "확인 필요": 2, "매핑 제외": 3}
    df_result["_sort"] = df_result["Status"].map(status_order)
    df_result = df_result.sort_values(
        by=["_sort", "Korean_Name", "Original_Description"],
        ascending=[True, True, True],
    ).drop(columns="_sort")

    ensure_dirs()
    save_path = DATA_PROCESSED / "validation_mapping_result.csv"
    df_result.to_csv(str(save_path), index=False, encoding="utf-8-sig")

    print("\n" + "=" * 60)
    print("[검증 결과 저장 완료]")
    print(f"저장 경로: {save_path}")
    print("=" * 60)
    summary = df_result["Status"].value_counts()
    for status_name, count in summary.items():
        print(f"  {status_name}: {count}건")
    print("\nStatus 컬럼으로 필터링하여 '확인 필요', '이름 불일치' 항목을 우선 점검하세요.")

    return df_result


if __name__ == "__main__":
    validate_mapping()
