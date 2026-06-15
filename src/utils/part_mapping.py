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
#
# [설계 원칙]
# 1. USDA 프라이멀이 다른 품목은 canonical을 분리한다 (가격 신호가 다름).
#    예: 양지 -> 차돌양지(Brisket) / 삼겹양지(Plate), 갈비 -> LA갈비(Plate) / 척갈비(Chuck) / 등갈비(Rib)
# 2. KMTA(수입·재고)는 해상도가 낮아 여러 canonical이 같은 kmta_part를 공유할 수 있다.
# 3. usda_codes가 비어 있으면 BI에서 usda_primal 지수로 대체한다.
# 4. ml_target=False: 미트박스 미취급(타깃 없음) 또는 소스 해상도 문제로 ML 제외.
CANONICAL_PARTS: tuple[PartSpec, ...] = (
    # ---------- 갈비 (KMTA '갈비' 공유) ----------
    PartSpec(
        "la_galbi",
        "LA갈비",
        kmta_part="갈비",
        meatbox_parts=("LA갈비", "갈비살/늑간살", "황제늑간"),
        usda_codes=("123A",),
        usda_primal="Primal Plate",
        notes="USDA Short Plate short rib(123A). 늑간살(rib finger)은 갈비뼈 사이 살 — LA갈비와 동일 원료 축",
    ),
    PartSpec(
        "chuck_galbi",
        "척갈비",
        kmta_part="갈비",
        meatbox_parts=("앞/척갈비", "척리블렛"),
        usda_codes=("130",),
        usda_primal="Primal Chuck",
        notes="USDA Chuck short rib(130). 척리블렛은 척갈비 부산 컷",
    ),
    PartSpec(
        "back_rib",
        "등갈비/백립",
        kmta_part="갈비",
        meatbox_parts=("등갈비/백립", "BBQ등갈비", "백립(조각백립)", "등갈비/백립(#2스펙)"),
        usda_codes=(),
        usda_primal="Primal Rib",
        notes="USDA back rib(124)는 LM_XB403 수집 데이터에 없음 — Primal Rib 지수 대체",
    ),
    # ---------- 양지 (KMTA '양지' 공유, USDA는 Brisket/Plate 별도 프라이멀) ----------
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
    # ---------- 목심 ----------
    PartSpec(
        "chuck_roll",
        "목심",
        kmta_part="목심",
        meatbox_parts=("알목심",),
        usda_codes=("116A", "916A"),
        usda_primal="Primal Chuck",
        notes="USDA Chuck Roll(116A/916A)",
    ),
    PartSpec(
        "chuck_flap",
        "살치살",
        kmta_part="목심",
        meatbox_parts=("살치살",),
        usda_codes=("116G",),
        usda_primal="Primal Chuck",
        notes="USDA Chuck flap(116G). 척롤 복합부위에서 분리 — KMTA 분류는 목심 추정 (앞다리 가능성 있음)",
    ),
    # ---------- 등심 / 채끝 ----------
    PartSpec(
        "ribeye",
        "등심",
        kmta_part="등심",
        meatbox_parts=(),
        usda_codes=("109E", "112A"),
        usda_primal="Primal Rib",
        ml_target=False,
        notes="USDA Ribeye. 미트박스 미취급(꽃등심 품목 없음) — ML 타깃 불가, 피처(선행지표)로만 사용",
    ),
    PartSpec(
        "striploin",
        "채끝",
        kmta_part="채끝",
        meatbox_parts=("센터컷",),
        usda_codes=("180", "175"),
        usda_primal="Primal Loin",
        notes="USDA Strip loin(180/175) = 채끝. 미트박스 '센터컷'은 스트립로인 센터컷",
    ),
    # ---------- 앞다리 (KMTA '앞다리' 공유) ----------
    PartSpec(
        "chuck",
        "앞다리",
        kmta_part="앞다리",
        meatbox_parts=("알전각/볼라전각",),
        usda_codes=("114", "114A", "114E", "116B"),
        usda_primal="Primal Chuck",
        notes="USDA Shoulder clod(114/114A/114E)·Chuck tender(116B). 알전각/볼라(bolar)는 전각(clod) 컷",
    ),
    PartSpec(
        "top_blade",
        "부채살",
        kmta_part="앞다리",
        meatbox_parts=("부채살",),
        usda_codes=("114D",),
        usda_primal="Primal Chuck",
        notes="USDA Top blade(114D). KMTA는 앞다리 합산 — 수입·재고 해상도 한계",
    ),
    # ---------- 안심 ----------
    PartSpec(
        "tenderloin",
        "안심",
        kmta_part="안심",
        meatbox_parts=(),
        usda_codes=("189A",),
        usda_primal="Primal Loin",
        ml_target=False,
        notes="USDA Tenderloin(189A). 미트박스 미취급 — 피처 전용",
    ),
    # ---------- 안창/토시 (횡격막계 — KMTA 기타 추정) ----------
    PartSpec(
        "skirt",
        "안창살/토시살",
        kmta_part="기타",
        meatbox_parts=("안창살", "토시살"),
        usda_codes=(),
        usda_primal="Primal Plate",
        ml_target=False,
        notes="USDA skirt(121C/121D)·hanging tender는 수집 데이터에 없음. KMTA 분류 불명(기타 추정) — ML 제외",
    ),
    # ---------- 우둔 / 설도 ----------
    PartSpec(
        "round",
        "우둔",
        kmta_part="우둔",
        meatbox_parts=(),
        usda_codes=("168", "169", "169A", "171C"),
        usda_primal="Primal Round",
        ml_target=False,
        notes="USDA Top inside round(168/169/169A)·Eye of round(171C=홍두깨). 미트박스 미취급 — 피처 전용",
    ),
    PartSpec(
        "seoldo",
        "설도",
        kmta_part="설도",
        meatbox_parts=("설도", "설깃"),
        usda_codes=("167A", "170", "171B", "184", "184B", "185B", "185C", "185D"),
        usda_primal="Primal Round",
        notes="USDA Knuckle(167A=도가니)·Gooseneck(170)·Outside(171B=설깃)·Top butt(184=보섭)·Ball tip/Tri-tip(185B-D=삼각). 184/185계는 USDA Loin이나 한국 분류는 설도",
    ),
    # ---------- 사태 ----------
    PartSpec(
        "shank",
        "사태",
        kmta_part="사태",
        meatbox_parts=("아롱사태", "스지", "스지(뒷스지)"),
        usda_codes=(),
        usda_primal=None,
        ml_target=False,
        notes="USDA shank는 LM_XB403 boxed beef에 미보고 — USDA 소스 없음",
    ),
    # ---------- 기타 / 부산물 ----------
    PartSpec(
        "etc_offal",
        "부산물",
        kmta_part="부산물",
        meatbox_parts=("목뼈", "홍창/소막창"),
        usda_codes=(),
        usda_primal=None,
        ml_target=False,
        notes="뼈·부산물류. '부산물'은 재고 전용 카테고리(수입 통계에는 없음) — ML 제외",
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
