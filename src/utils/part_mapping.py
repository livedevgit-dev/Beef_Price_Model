# [파일 정의서]
# - 파일명: part_mapping.py
# - 역할: 가공
# - 대상: 공통 (미트박스·재고·수입·USDA 간 품목 매핑)
# - 데이터 소스: KMTA 부위 체계, 미트박스 part, USDA LM_XB403 코드, master_price_data(원산지 관측)
# - 주요 기능:
#   1. canonical(표준) 부위 정의 — ML·BI 통합 분석의 기준 키
#   2. 미트박스 / KMTA(수입·재고) / USDA 코드 간 교차 매핑
#   3. 미트박스 품목별 원산지·USDA 비교 방식(direct/proxy/none) 판정
#   4. part_crosswalk.csv 산출

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MASTER_PRICE_CSV, PART_CROSSWALK_CSV, ensure_dirs


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
#    같은 프라이멀이라도 USDA cut 코드가 따로 보고되는 주력 품목은 분리한다 (우둔 168/169 vs 홍두깨 171C).
# 2. KMTA(수입·재고)는 해상도가 낮아 여러 canonical이 같은 kmta_part를 공유할 수 있다.
#    kmta_to_canonical()은 같은 kmta_part 중 '먼저 정의된'(대표) canonical을 돌려준다.
# 3. usda_codes가 비어 있으면 BI에서 usda_primal 지수로 대체한다.
# 4. meatbox_parts는 원산지 구분 없는 미트박스 품목명(part_name의 '-원산지' 앞부분)이다.
#    원산지는 master_price_data에서 관측해 crosswalk의 meatbox_origins / usda_compare 열로 내보낸다.
#    호주산은 USDA 가격과 '직접' 비교 대상이 아니며 proxy(동일 부위 미국 시세)로만 쓴다
#    -> meatbox_usda_compare(part, origin) 참고.
# 5. ml_target=False: 미트박스 거래 없음/이력 부족(타깃 없음), USDA 소스 없음, 또는 부산물 — ML 제외.
CANONICAL_PARTS: tuple[PartSpec, ...] = (
    # ---------- 갈비 (KMTA '갈비' 공유) ----------
    PartSpec(
        "la_galbi",
        "LA갈비",
        kmta_part="갈비",
        meatbox_parts=("LA갈비", "갈비살/늑간살", "황제늑간", "숏립앤드", "양지갈비"),
        usda_codes=("123A",),
        usda_primal="Primal Plate",
        notes=(
            "USDA Short Plate short rib(123A). 늑간살(rib finger)은 갈비뼈 사이 살 — LA갈비와 동일 원료 축. "
            "숏립앤드(short rib end)=숏립 정형 끝단. "
            "양지갈비(호주)=양지 쪽 갈비뼈(plate/brisket rib) 추정 — 뼈 비중 높은 저가품, 확인 필요"
        ),
    ),
    PartSpec(
        "chuck_galbi",
        "척갈비",
        kmta_part="갈비",
        meatbox_parts=("앞/척갈비", "척리블렛", "척빽립", "척스페어립", "척갈비살/늑간살", "일반갈비"),
        usda_codes=("130",),
        usda_primal="Primal Chuck",
        notes=(
            "USDA Chuck short rib(130). 척리블렛·척빽립·척스페어립은 척갈비 부산 컷(뼈 위주), "
            "척갈비살/늑간살은 척 쪽 rib finger. 일반갈비(호주)=찜갈비용 척갈비 추정"
        ),
    ),
    PartSpec(
        "back_rib",
        "등갈비/백립",
        kmta_part="갈비",
        meatbox_parts=("등갈비/백립", "BBQ등갈비", "백립(조각백립)", "등갈비/백립(#2스펙)", "스페어립"),
        usda_codes=(),
        usda_primal="Primal Rib",
        notes=(
            "USDA back rib(124)는 LM_XB403 수집 데이터에 없음 — Primal Rib 지수 대체. "
            "스페어립(호주)=rib set에서 큐브롤 분리 후 남는 등쪽 갈비뼈(back rib 상당)"
        ),
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
        meatbox_parts=("알목심", "목심"),
        usda_codes=("116A", "916A"),
        usda_primal="Primal Chuck",
        notes=(
            "USDA Chuck Roll(116A/916A). 목심(호주)=AUS-MEAT chuck roll, "
            "알목심=chuck eye roll(116D 상당, LM_XB403 미보고 -> 116A로 대응)"
        ),
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
        meatbox_parts=("등심", "윗등심", "아랫등심", "립캡"),
        usda_codes=("109E", "112A"),
        usda_primal="Primal Rib",
        ml_target=False,
        notes=(
            "USDA Ribeye(109E/112A). 미트박스 '등심'은 별도 품목 '채끝등심'(striploin)과 구분되는 "
            "꽃등심·윗/아랫등심 계열 = ribeye roll(AUS-MEAT cube roll). 2026-10-20부터 호주산만 거래 — "
            "이력 부족으로 ML 타깃 보류. 립캡(미국)=rib cap/blade meat(109B 계열) — Rib 프라이멀 축이나 저가 정형육"
        ),
    ),
    PartSpec(
        "striploin",
        "채끝",
        kmta_part="채끝",
        meatbox_parts=("센터컷", "채끝등심"),
        usda_codes=("180", "175"),
        usda_primal="Primal Loin",
        notes=(
            "USDA Strip loin(180/175) = 채끝(미트박스 '채끝등심'). '센터컷'은 스트립로인 센터컷으로 가정했으나 "
            "시세(약 1.1만원/kg)가 채끝 수준보다 크게 낮아 재확인 필요 (2026-07-24 이후 거래 없음)"
        ),
    ),
    # ---------- 앞다리 (KMTA '앞다리' 공유) ----------
    PartSpec(
        "chuck",
        "앞다리",
        kmta_part="앞다리",
        meatbox_parts=("알전각/볼라전각", "앞다리/전각"),
        usda_codes=("114", "114A", "114E", "116B"),
        usda_primal="Primal Chuck",
        notes=(
            "USDA Shoulder clod(114/114A/114E)·Chuck tender(116B). "
            "알전각/볼라(bolar)·앞다리/전각(호주 clod)은 전각(clod) 컷"
        ),
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
        meatbox_parts=("안심",),
        usda_codes=("189A",),
        usda_primal="Primal Loin",
        ml_target=False,
        notes="USDA Tenderloin(189A). 미트박스 거래는 호주산 단발(2025-10~2026-03)뿐 — 피처 전용",
    ),
    # ---------- 안창/토시 ----------
    PartSpec(
        "hanger",
        "안창살",
        kmta_part="기타",
        meatbox_parts=("안창살", "안창살(조각)", "양지안창"),
        usda_codes=(),
        usda_primal="Primal Plate",
        ml_target=False,
        notes=(
            "USDA hanging tender·skirt(121C/121D)는 LM_XB403 미보고 — USDA 가격 없음. KMTA 분류 불명(기타 추정). "
            "안창살(조각)=안창살 조각 규격, 양지안창=inside skirt(121D) 추정 (2026-10-27 신규, 저가)"
        ),
    ),
    PartSpec(
        "sirloin_flap",
        "토시살",
        kmta_part="기타",
        meatbox_parts=("토시살",),
        usda_codes=("185A",),
        usda_primal="Primal Loin",
        notes="USDA Bottom sirloin flap(185A). 한국 수입 '토시살'의 다수가 sirloin flap meat",
    ),
    # ---------- 우둔 / 홍두깨 / 설도 ----------
    PartSpec(
        "round",
        "우둔",
        kmta_part="우둔",
        meatbox_parts=("우둔",),
        usda_codes=("168", "169", "169A"),
        usda_primal="Primal Round",
        notes=(
            "USDA Top inside round(168/169/169A) = 우둔(AUS-MEAT topside/inside). "
            "미트박스는 호주산만 거래(2025-12~) — USDA 비교는 proxy"
        ),
    ),
    PartSpec(
        "eye_round",
        "홍두깨",
        kmta_part="우둔",
        meatbox_parts=("홍두깨",),
        usda_codes=("171C",),
        usda_primal="Primal Round",
        notes=(
            "USDA Eye of round(171C) = 홍두깨(AUS-MEAT eye round). 한국 분류상 우둔에 속해 KMTA는 '우둔' 공유. "
            "미트박스는 호주산만 거래 — USDA 비교는 proxy"
        ),
    ),
    PartSpec(
        "seoldo",
        "설도",
        kmta_part="설도",
        meatbox_parts=("설도", "설깃", "설깃살", "삼각살"),
        usda_codes=("167A", "170", "171B", "184", "184B", "185B", "185C", "185D"),
        usda_primal="Primal Round",
        notes=(
            "USDA Knuckle(167A=도가니살)·Gooseneck(170)·Outside(171B=설깃)·Top butt(184=보섭)·"
            "Ball tip/Tri-tip(185B-D=삼각). 184/185계는 USDA Loin이나 한국 분류는 설도. "
            "미트박스 '도가니'(무릎 연골, 부산물)는 도가니살(167A)과 다른 품목"
        ),
    ),
    # ---------- 사태 ----------
    PartSpec(
        "shank",
        "사태",
        kmta_part="사태",
        meatbox_parts=("아롱사태", "스지", "스지(뒷스지)", "사태", "앞사태", "뒷사태"),
        usda_codes=(),
        usda_primal=None,
        ml_target=False,
        notes="USDA shank(fore/hind)는 LM_XB403 boxed beef에 미보고 — USDA 소스 없음",
    ),
    # ---------- 기타 / 부산물 ----------
    PartSpec(
        "etc_offal",
        "부산물",
        kmta_part="부산물",
        meatbox_parts=(
            "목뼈", "홍창/소막창", "양(깐양)", "곱창", "대창", "꼬리",
            "사골(뒷왕사골)", "사골(앞왕사골)", "사골(앞쪽사골)", "사골(뒤쪽사골)", "학본",
            "도가니", "뽈살", "헤드미트",
        ),
        usda_codes=(),
        usda_primal=None,
        ml_target=False,
        notes=(
            "뼈·부산물·두부육(양·곱창·대창·꼬리·사골·학본·도가니·뽈살·헤드미트). "
            "'부산물'은 재고 전용 카테고리(수입 통계에는 없음), USDA boxed beef 대응 없음 — ML 제외"
        ),
    ),
)

ORIGIN_US = "미국"
ORIGIN_AU = "호주"


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
            if mb in out:
                raise ValueError(f"미트박스 품목 '{mb}'이 {out[mb]}·{spec.canonical_id}에 중복 매핑됨")
            out[mb] = spec.canonical_id
    return out


def _kmta_lookup() -> dict[str, str]:
    # 같은 kmta_part를 공유하는 canonical이 여러 개면 먼저 정의된 대표 canonical을 쓴다
    out: dict[str, str] = {}
    for spec in CANONICAL_PARTS:
        out.setdefault(spec.kmta_part, spec.canonical_id)
    return out


def _usda_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for spec in CANONICAL_PARTS:
        for code in spec.usda_codes:
            out[code] = spec.canonical_id
    return out


MEATBOX_TO_CANONICAL = _meatbox_lookup()
KMTA_TO_CANONICAL = _kmta_lookup()
USDA_CODE_TO_CANONICAL = _usda_lookup()


def split_meatbox_part_name(part_name: str) -> tuple[str, str]:
    """'삼겹양지-미국 | IBP(278)' -> ('삼겹양지', '미국'). 원산지 접미가 없으면 ('삼겹양지', '')."""
    base = str(part_name).split("|")[0].strip()
    if "-" in base:
        part, origin = base.rsplit("-", 1)
        return part.strip(), origin.strip()
    return base, ""


def meatbox_to_canonical(meatbox_part: str) -> str | None:
    return MEATBOX_TO_CANONICAL.get(str(meatbox_part).strip())


def kmta_to_canonical(kmta_part: str) -> str | None:
    return KMTA_TO_CANONICAL.get(str(kmta_part).strip())


def usda_code_to_canonical(code: str) -> str | None:
    return USDA_CODE_TO_CANONICAL.get(str(code).strip())


def meatbox_usda_compare(meatbox_part: str, origin: str) -> str:
    """미트박스 (품목, 원산지) 한 건을 USDA 시세와 어떻게 비교할지.

    - direct : 미국산 + USDA cut 코드 있음 -> USDA cut 가격과 직접 비교
    - proxy  : 호주산이거나 USDA cut 없이 primal 지수만 있음 -> 방향성 참고용
    - none   : USDA 대응 없음(사태·부산물 등)
    - unmapped : canonical 미매핑
    """
    spec = get_part(meatbox_to_canonical(meatbox_part) or "")
    if spec is None:
        return "unmapped"
    if not spec.usda_codes and not spec.usda_primal:
        return "none"
    if str(origin).strip() == ORIGIN_US and spec.usda_codes:
        return "direct"
    return "proxy"


def load_meatbox_part_origins(path: Path | None = None) -> dict[str, dict[str, int]]:
    """master_price_data에서 관측된 미트박스 품목별 원산지 행 수. 파일이 없으면 빈 dict."""
    src = path or MASTER_PRICE_CSV
    if not Path(src).exists():
        return {}
    df = pd.read_csv(str(src), usecols=["part_name"], encoding="utf-8-sig")
    split = df["part_name"].dropna().astype(str).map(split_meatbox_part_name)
    counts = pd.DataFrame(split.tolist(), columns=["part", "origin"]).value_counts()
    out: dict[str, dict[str, int]] = {}
    for (part, origin), n in counts.items():
        out.setdefault(part, {})[origin] = int(n)
    return out


def build_usda_code_to_korean_map() -> dict[str, str]:
    """validate_mapping.py 호환: USDA 코드 -> 미트박스 대표 품목명(-원산지 접미).

    대표 품목이 호주산만 거래되면 '-호주', 그 외는 '-미국'을 붙인다.
    """
    origins = load_meatbox_part_origins()
    mapping: dict[str, str] = {}
    for spec in CANONICAL_PARTS:
        if not spec.meatbox_parts:
            continue
        primary_part = spec.meatbox_parts[0]
        seen = origins.get(primary_part, {})
        suffix = ORIGIN_AU if seen and ORIGIN_US not in seen else ORIGIN_US
        primary = f"{primary_part}-{suffix}"
        for code in spec.usda_codes:
            mapping[code] = primary
    return mapping


def _origins_label(seen: dict[str, int]) -> str:
    return "|".join(o for o, _ in sorted(seen.items(), key=lambda kv: -kv[1]))


def _usda_compare_label(spec: PartSpec, seen: dict[str, int]) -> str:
    if not spec.usda_codes and not spec.usda_primal:
        return "none"
    if not seen:
        return "no_trade"
    if ORIGIN_US in seen and spec.usda_codes:
        return "direct" if len(seen) == 1 else "direct(미국)/proxy(호주)"
    return "proxy"


def build_crosswalk_dataframe() -> pd.DataFrame:
    """BI·ML용 long-format 교차 매핑 테이블."""
    origins = load_meatbox_part_origins()
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
        blank = {"meatbox_origins": "", "usda_compare": ""}
        if spec.meatbox_parts:
            for mb in spec.meatbox_parts:
                seen = origins.get(mb, {})
                rows.append({
                    **base,
                    "source": "meatbox",
                    "source_key": mb,
                    "source_label": mb,
                    "meatbox_origins": _origins_label(seen),
                    "usda_compare": _usda_compare_label(spec, seen),
                })
        else:
            rows.append({**base, "source": "meatbox", "source_key": "", "source_label": "(미매핑)", **blank})

        rows.append({
            **base,
            "source": "kmta_import_stock",
            "source_key": spec.kmta_part,
            "source_label": spec.kmta_part,
            **blank,
        })

        if spec.usda_codes:
            for code in spec.usda_codes:
                rows.append({
                    **base,
                    "source": "usda_cut",
                    "source_key": code,
                    "source_label": code,
                    **blank,
                })
        elif spec.usda_primal:
            rows.append({
                **base,
                "source": "usda_primal",
                "source_key": spec.usda_primal,
                "source_label": spec.usda_primal,
                **blank,
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
