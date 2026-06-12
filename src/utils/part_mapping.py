# [파일 정의서]
# - 파일명: part_mapping.py
# - 역할: 가공
# - 대상: 공통 (미트박스·재고·수입·USDA 간 품목 매핑)
# - 데이터 소스: KMTA 부위 체계, 미트박스 part, USDA LM_XB403 코드
# - 주요 기능:
#   1. canonical(표준) 부위 정의 — ML·BI 통합 분석의 기준 키
#   2. 미트박스 / KMTA(수입·재고) / USDA 코드 간 교차 매핑
#   3. part_crosswalk.csv 산출

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PART_CROSSWALK_CSV, ensure_dirs


@dataclass(frozen=True)
class PartSpec:
    """단일 표준 부위와 소스별 명칭/코드 매핑."""

    canonical_id: str
    name_ko: str
    kmta_part: str
    meatbox_parts: tuple[str, ...] = ()
    usda_codes: tuple[str, ...] = ()
    usda_primal: str | None = None
    ml_target: bool = True
    notes: str = ""


# KMTA 부위명 = 수입(master_import_volume) = 재고(beef_stock) 공통 체계
CANONICAL_PARTS: tuple[PartSpec, ...] = (
    PartSpec(
        "galbi",
        "갈비",
        kmta_part="갈비",
        meatbox_parts=(
            "LA갈비",
            "앞/척갈비",
            "등갈비/백립",
            "BBQ등갈비",
            "백립(조각백립)",
            "등갈비/백립(#2스펙)",
            "황제늑간",
            "갈비살/늑간살",
        ),
        usda_codes=("123A", "130", "124"),
        usda_primal="Primal Plate",
        notes="USDA Short Plate / Short Rib. 수입·재고는 KMTA '갈비' 단일 부위",
    ),
    # 양지는 KMTA 기준 단일 부위지만 USDA는 Brisket / Plate 별도 프라이멀.
    # 가격 신호가 다르므로 canonical을 분리하고, 수입·재고는 둘 다 KMTA '양지'를 공유한다.
    PartSpec(
        "brisket_yangji",
        "차돌양지",
        kmta_part="양지",
        meatbox_parts=("차돌양지", "차돌박이"),
        usda_codes=("120", "120A"),
        usda_primal="Primal Brisket",
        notes="USDA Brisket(120/120A). 수입·재고는 KMTA '양지' 합산 — 삼겹양지와 공유",
    ),
    PartSpec(
        "plate_yangji",
        "삼겹양지",
        kmta_part="양지",
        meatbox_parts=("삼겹양지", "삼겹양지(조각)"),
        usda_codes=(),
        usda_primal="Primal Plate",
        notes="USDA Short Plate(Navel) — boxed cut 코드 없음, Primal Plate 지수 사용. 수입·재고는 KMTA '양지' 합산 — 차돌양지와 공유",
    ),
    PartSpec(
        "chuck_roll",
        "목심",
        kmta_part="목심",
        meatbox_parts=("알목심", "척리블렛", "알전각/볼라전각"),
        usda_codes=("116A", "916A"),
        usda_primal="Primal Chuck",
        notes="USDA Chuck Roll",
    ),
    PartSpec(
        "ribeye",
        "등심",
        kmta_part="등심",
        meatbox_parts=("센터컷", "살치살"),
        usda_codes=("109E", "112A", "180", "175"),
        usda_primal="Primal Rib",
        notes="USDA Ribeye / Strip Loin 일부. 미트박스 센터컷은 Strip 대응",
    ),
    PartSpec(
        "chuck_flap",
        "채끝",
        kmta_part="채끝",
        meatbox_parts=(),
        usda_codes=(),
        usda_primal="Primal Chuck",
        ml_target=False,
        notes="KMTA 채끝. 미트박스·USDA cut 매핑 미정 — ML 제외",
    ),
    PartSpec(
        "round",
        "우둔",
        kmta_part="우둔",
        meatbox_parts=("설도", "설깃"),
        usda_codes=(),
        usda_primal="Primal Round",
        ml_target=False,
        notes="USDA Round 세부 cut은 validate_mapping에서 분석 제외",
    ),
    PartSpec(
        "shank",
        "사태",
        kmta_part="사태",
        meatbox_parts=("아롱사태", "스지", "스지(뒷스지)"),
        usda_codes=(),
        usda_primal=None,
        ml_target=False,
    ),
    PartSpec(
        "chuck",
        "앞다리",
        kmta_part="앞다리",
        meatbox_parts=(),
        usda_codes=("114D",),
        usda_primal="Primal Chuck",
        notes="USDA Top Blade -> 부채살(미트박스)은 별도 canonical",
    ),
    PartSpec(
        "top_blade",
        "부채살",
        kmta_part="앞다리",
        meatbox_parts=("부채살", "토시살"),
        usda_codes=("114D",),
        usda_primal="Primal Chuck",
        notes="미트박스 부채살. KMTA는 앞다리 합산 — 수입·재고 해상도 한계",
    ),
    PartSpec(
        "tenderloin",
        "안심",
        kmta_part="안심",
        meatbox_parts=("안창살",),
        usda_codes=("121C", "121D"),
        usda_primal="Primal Loin",
        ml_target=False,
        notes="안창살은 미트박스 명칭. KMTA 안심과 근접",
    ),
)


def list_canonical_parts(*, ml_only: bool = False) -> list[PartSpec]:
    if ml_only:
        return [p for p in CANONICAL_PARTS if p.ml_target]
    return list(CANONICAL_PARTS)


def get_part(canonical_id: str) -> PartSpec | None:
    for part in CANONICAL_PARTS:
        if part.canonical_id == canonical_id:
            return part
    return None


def _meatbox_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in CANONICAL_PARTS:
        for mb in spec.meatbox_parts:
            out[mb] = spec.canonical_id
    return out


def _kmta_lookup() -> dict[str, str]:
    return {spec.kmta_part: spec.canonical_id for spec in CANONICAL_PARTS}


def _usda_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in CANONICAL_PARTS:
        for code in spec.usda_codes:
            out[code] = spec.canonical_id
    return out


MEATBOX_TO_CANONICAL = _meatbox_lookup()
KMTA_TO_CANONICAL = _kmta_lookup()
USDA_CODE_TO_CANONICAL = _usda_lookup()


def meatbox_to_canonical(meatbox_part: str) -> str | None:
    return MEATBOX_TO_CANONICAL.get(str(meatbox_part).strip())


def kmta_to_canonical(kmta_part: str) -> str | None:
    return KMTA_TO_CANONICAL.get(str(kmta_part).strip())


def usda_code_to_canonical(code: str) -> str | None:
    return USDA_CODE_TO_CANONICAL.get(str(code).strip())


def build_usda_code_to_korean_map() -> dict[str, str]:
    """validate_mapping.py 호환: USDA 코드 -> 미트박스 표준명(-미국 접미)."""
    mapping: dict[str, str] = {}
    for spec in CANONICAL_PARTS:
        if not spec.meatbox_parts:
            continue
        primary = f"{spec.meatbox_parts[0]}-미국"
        for code in spec.usda_codes:
            mapping[code] = primary
    # validate_mapping에만 있던 항목 보강
    extra = {
        "109E": "꽃등심-미국",
        "112A": "꽃등심-미국",
        "180": "센터컷-미국",
        "175": "센터컷-미국",
    }
    for code, name in extra.items():
        mapping.setdefault(code, name)
    return mapping


def build_crosswalk_dataframe() -> pd.DataFrame:
    """BI·ML용 long-format 교차 매핑 테이블."""
    rows: list[dict] = []
    for spec in CANONICAL_PARTS:
        base = {
            "canonical_id": spec.canonical_id,
            "canonical_name_ko": spec.name_ko,
            "kmta_part": spec.kmta_part,
            "usda_primal": spec.usda_primal or "",
            "ml_target": spec.ml_target,
            "notes": spec.notes,
        }
        if spec.meatbox_parts:
            for mb in spec.meatbox_parts:
                rows.append({**base, "source": "meatbox", "source_key": mb, "source_label": mb})
        else:
            rows.append({**base, "source": "meatbox", "source_key": "", "source_label": "(미매핑)"})

        rows.append({
            **base,
            "source": "kmta_import_stock",
            "source_key": spec.kmta_part,
            "source_label": spec.kmta_part,
        })

        if spec.usda_codes:
            for code in spec.usda_codes:
                rows.append({
                    **base,
                    "source": "usda_cut",
                    "source_key": code,
                    "source_label": code,
                })
        elif spec.usda_primal:
            rows.append({
                **base,
                "source": "usda_primal",
                "source_key": spec.usda_primal,
                "source_label": spec.usda_primal,
            })
    return pd.DataFrame(rows)


def export_crosswalk(path: Path | None = None) -> Path:
    ensure_dirs()
    out = path or PART_CROSSWALK_CSV
    df = build_crosswalk_dataframe()
    df.to_csv(str(out), index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    saved = export_crosswalk()
    print(f"[완료] 품목 교차 매핑 저장: {saved}")
    print(build_crosswalk_dataframe().groupby("canonical_name_ko").size())
