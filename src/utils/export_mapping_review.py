# [파일 정의서]
# - 파일명: export_mapping_review.py
# - 역할: 산출물 생성 (External LLM Review Package)
# - 대상: 공통 (미트박스·KMTA·USDA 품목 매핑)
# - 데이터 소스: utils.part_mapping.CANONICAL_PARTS, master_price_data.csv(미트박스 미국·호주),
#                master_import_volume.csv, beef_stock_data.xlsx, usda_beef_history.csv
# - 주요 기능: 다른 LLM(GPT, Gemini 등)이 매핑 정확성을 더블체크할 수 있도록
#              data/3_reports/mapping_review/ 아래에 CSV 4종 + README 1종을 생성

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    BEEF_STOCK_XLSX,
    DASHBOARD_READY_CSV,
    MAPPING_REVIEW_DIR,
    MASTER_PRICE_CSV,
    MASTER_IMPORT_VOLUME_CSV,
    USDA_BEEF_HISTORY_CSV,
)
from utils.part_mapping import (
    CANONICAL_PARTS,
    USDA_CODE_TO_CANONICAL,
    kmta_to_canonical,
    meatbox_to_canonical,
    meatbox_usda_compare,
    split_meatbox_part_name,
)

MEATBOX_ORIGIN_SOURCE = {"미국": "meatbox_us", "호주": "meatbox_au"}
ACTIVE_DAYS = 120

USDA_CODE_PATTERN = re.compile(r"\(\s*([0-9]+[A-Z]?)\s+")


def _extract_code(description: str) -> str:
    m = USDA_CODE_PATTERN.search(str(description))
    return m.group(1).strip() if m else ""


def build_canonical_summary() -> pd.DataFrame:
    rows = []
    for spec in CANONICAL_PARTS:
        rows.append({
            "canonical_id": spec.canonical_id,
            "canonical_name_ko": spec.name_ko,
            "kmta_part": spec.kmta_part,
            "meatbox_parts": " | ".join(spec.meatbox_parts) if spec.meatbox_parts else "",
            "meatbox_count": len(spec.meatbox_parts),
            "usda_codes": ", ".join(spec.usda_codes) if spec.usda_codes else "",
            "usda_code_count": len(spec.usda_codes),
            "usda_primal": spec.usda_primal or "",
            "ml_target": spec.ml_target,
            "has_meatbox": bool(spec.meatbox_parts),
            "has_usda_cut": bool(spec.usda_codes),
            "has_usda_primal": bool(spec.usda_primal),
            "chain_completeness": (
                "FULL"
                if spec.meatbox_parts and (spec.usda_codes or spec.usda_primal) and spec.kmta_part
                else "PARTIAL"
            ),
            "notes_ko": spec.notes,
            "review_question": (
                f"이 매핑이 적절한가? 한국 부위 '{spec.name_ko}'를 "
                f"미트박스 [{', '.join(spec.meatbox_parts) or '없음'}], "
                f"KMTA '{spec.kmta_part}', "
                f"USDA [{', '.join(spec.usda_codes) or spec.usda_primal or '없음'}] "
                "에 연결한 것이 정확한지 확인 요청."
            ),
        })
    return pd.DataFrame(rows)


def build_usda_codes_detail() -> pd.DataFrame:
    df = pd.read_csv(
        str(USDA_BEEF_HISTORY_CSV),
        usecols=["item_description"],
        low_memory=False,
    )
    items = df["item_description"].dropna().astype(str).unique()

    rows = []
    canonical_lookup = {spec.canonical_id: spec for spec in CANONICAL_PARTS}
    for desc in sorted(items):
        code = _extract_code(desc)
        canonical_id = USDA_CODE_TO_CANONICAL.get(code, "")
        spec = canonical_lookup.get(canonical_id)
        rows.append({
            "usda_code": code,
            "usda_description": desc,
            "primal_group": desc.split(",")[0].strip(),
            "mapped_canonical_id": canonical_id,
            "mapped_canonical_name_ko": spec.name_ko if spec else "",
            "mapped_kmta_part": spec.kmta_part if spec else "",
            "mapped_meatbox_examples": (
                " | ".join(spec.meatbox_parts) if spec and spec.meatbox_parts else ""
            ),
            "status": "MAPPED" if spec else ("UNMAPPED" if code else "NO_CODE"),
            "notes_ko": spec.notes if spec else "",
            "review_question": (
                f"USDA 코드 '{code}' ({desc})는 한국 부위 "
                f"'{spec.name_ko if spec else '(미매핑)'}'에 해당하는가? "
                "다른 부위로 보는 것이 더 적절하다면 어디인지 제안 요청."
            ),
        })
    return pd.DataFrame(rows).sort_values(["primal_group", "usda_code"])


def _meatbox_inventory_rows() -> list[dict]:
    """미트박스 (품목, 원산지)별 매핑 결과. master_price_data 우선, 없으면 대시보드 데이터."""
    if MASTER_PRICE_CSV.exists():
        mb = pd.read_csv(str(MASTER_PRICE_CSV), usecols=["date", "part_name"], encoding="utf-8-sig")
        mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
        split = mb["part_name"].astype(str).map(split_meatbox_part_name)
        mb["part"], mb["origin"] = split.str[0], split.str[1]
    elif DASHBOARD_READY_CSV.exists():
        mb = pd.read_csv(str(DASHBOARD_READY_CSV))
        mb["date"] = pd.to_datetime(mb["date"], errors="coerce")
        mb["origin"] = mb["category"]
    else:
        return []

    mb = mb.dropna(subset=["date", "part"])
    active_cutoff = mb["date"].max() - pd.Timedelta(days=ACTIVE_DAYS)
    inv = (
        mb.groupby(["origin", "part"])
        .agg(
            rows_total=("date", "size"),
            rows_recent=("date", lambda d: int((d > active_cutoff).sum())),
            last_date=("date", "max"),
        )
        .reset_index()
    )

    rows = []
    for r in inv.itertuples(index=False):
        cid = meatbox_to_canonical(r.part)
        spec = next((s for s in CANONICAL_PARTS if s.canonical_id == cid), None)
        name = spec.name_ko if spec else "(미매핑)"
        rows.append({
            "source": MEATBOX_ORIGIN_SOURCE.get(r.origin, f"meatbox_{r.origin}"),
            "source_item": r.part,
            "origin": r.origin,
            "rows_total": r.rows_total,
            f"rows_last_{ACTIVE_DAYS}d": r.rows_recent,
            "last_date": r.last_date.date().isoformat(),
            "mapped_canonical_id": cid or "",
            "mapped_canonical_name_ko": spec.name_ko if spec else "",
            "usda_compare": meatbox_usda_compare(r.part, r.origin),
            "status": "MAPPED" if cid else "UNMAPPED",
            "review_question": (
                f"미트박스 {r.origin}산 '{r.part}'을(를) '{name}'로 분류한 것이 정확한가?"
            ),
        })
    return rows


def build_source_inventory() -> pd.DataFrame:
    rows = []

    rows.extend(_meatbox_inventory_rows())

    if MASTER_IMPORT_VOLUME_CSV.exists():
        imp = pd.read_csv(str(MASTER_IMPORT_VOLUME_CSV), encoding="utf-8-sig")
        kmta_parts = sorted(
            c.replace("부위별_", "").replace("_합계", "")
            for c in imp.columns
            if c.startswith("부위별_") and not c.endswith("계_합계")
        )
        for part in kmta_parts:
            cid = kmta_to_canonical(part)
            spec = next((s for s in CANONICAL_PARTS if s.canonical_id == cid), None)
            rows.append({
                "source": "kmta_import",
                "source_item": part,
                "mapped_canonical_id": cid or "",
                "mapped_canonical_name_ko": spec.name_ko if spec else "",
                "status": "MAPPED" if cid else "UNMAPPED",
                "review_question": (
                    f"KMTA 수입통계 부위 '{part}'을(를) '{spec.name_ko if spec else '(미매핑)'}'와 "
                    "동일 부위로 보는 것이 맞는가?"
                ),
            })

    if BEEF_STOCK_XLSX.exists():
        stk = pd.read_excel(str(BEEF_STOCK_XLSX))
        stk_parts = sorted(
            p for p in stk.iloc[:, 1].dropna().astype(str).unique() if p != "합계"
        )
        for part in stk_parts:
            cid = kmta_to_canonical(part)
            spec = next((s for s in CANONICAL_PARTS if s.canonical_id == cid), None)
            rows.append({
                "source": "kmta_stock",
                "source_item": part,
                "mapped_canonical_id": cid or "",
                "mapped_canonical_name_ko": spec.name_ko if spec else "",
                "status": "MAPPED" if cid else "UNMAPPED",
                "review_question": (
                    f"KMTA 재고통계 부위 '{part}'을(를) "
                    f"'{spec.name_ko if spec else '(미매핑)'}'로 분류해도 되는가?"
                ),
            })

    df = pd.DataFrame(rows)
    for col in ("rows_total", f"rows_last_{ACTIVE_DAYS}d"):
        if col in df.columns:
            df[col] = df[col].astype("Int64")
    return df


def build_open_questions() -> pd.DataFrame:
    """현재 매핑에서 불확실한 항목을 LLM에 명시적으로 질문."""
    questions = [
        {
            "topic": "살치살의 KMTA 분류",
            "context": (
                "미트박스 '살치살'은 USDA Chuck flap(116G, 척롤 인접 부위)에 해당. "
                "KMTA 수입·재고 통계에서는 '목심'으로 잡힐 가능성과 '앞다리'로 잡힐 "
                "가능성이 있음. 현재는 '목심'으로 매핑."
            ),
            "question": (
                "한국 수입·재고 통계에서 척플랩(살치살)이 '목심'과 '앞다리' 중 "
                "어디에 집계되는지 확인 요청. 가능하면 근거 자료(KMTA 분류 기준 등)도 함께."
            ),
        },
        {
            "topic": "설도 vs Loin top butt/Tri-tip",
            "context": (
                "USDA 184/184B(top butt=보섭), 185B/C/D(ball-tip·tri-tip=삼각살)는 "
                "Primal Loin으로 분류되지만, 한국 분류 체계상 '설도'에 속함. "
                "현재는 KMTA '설도' canonical에 묶음."
            ),
            "question": (
                "USDA Loin top butt/Tri-tip을 한국 '설도'로 분류한 것이 정확한지 "
                "검증 요청. 학술자료·도축기준상 더 정확한 분류가 있다면 제시."
            ),
        },
        {
            "topic": "삼겹양지의 USDA cut 없음",
            "context": (
                "미트박스 '삼겹양지'는 USDA Short Plate(navel) 부위인데 LM_XB403 "
                "boxed beef 보고에서는 plate navel boxed cut 코드를 수집하지 않음. "
                "현재는 Primal Plate 지수(choice_600_900 / 45.36)를 USDA 대체값으로 사용."
            ),
            "question": (
                "Short Plate navel에 해당하는 다른 USDA 보고(예: 121류, NW_LS441 등)가 "
                "있는지, Primal Plate 지수로 대체하는 것이 가격예측에 적절한지 의견 요청."
            ),
        },
        {
            "topic": "등갈비/백립의 USDA cut 없음",
            "context": (
                "USDA back rib(124)는 본 프로젝트의 LM_XB403 수집 결과에 존재하지 않음. "
                "현재는 Primal Rib 지수로 대체."
            ),
            "question": (
                "USDA 보고서 중 back ribs(124, 124A 등)를 별도로 수집할 수 있는 "
                "API 엔드포인트가 있는지, 없다면 Primal Rib 지수로 대체하는 것이 "
                "충분한 proxy인지 확인."
            ),
        },
        {
            "topic": "안창살·토시살의 USDA cut",
            "context": (
                "안창살(outside skirt 121C), 토시살(hanging tender) 모두 LM_XB403 "
                "수집 데이터에 없음. 현재 Primal Plate 지수로 대체."
            ),
            "question": (
                "USDA에서 outside/inside skirt(121C/121D), hanging tender의 "
                "별도 가격 시계열을 얻을 수 있는 데이터 소스가 있는지 확인."
            ),
        },
        {
            "topic": "차돌양지 vs 삼겹양지 분리",
            "context": (
                "KMTA '양지' 한 부위에 USDA 측에서 차돌양지(Brisket 120/120A)와 "
                "삼겹양지(Short Plate)가 섞임. 가격 신호 보존을 위해 canonical을 "
                "둘로 분리(brisket_yangji, plate_yangji)했고, 수입·재고는 두 canonical이 "
                "동일한 KMTA '양지' 시계열을 공유함."
            ),
            "question": (
                "이 분리 방식이 ML 모델링에 더 적합한가, 아니면 KMTA 해상도에 맞춰 "
                "하나의 '양지' canonical로 유지하고 USDA를 평균내는 편이 더 안정적인가?"
            ),
        },
        {
            "topic": "미트박스 '센터컷'의 실체",
            "context": (
                "미트박스 '센터컷'(엑셀 86K, 2025-01~2026-07)은 채끝(스트립로인 180) 센터컷으로 매핑되어 있으나, "
                "시세가 약 1.1만원/kg으로 같은 시기 미국산 채끝·등심류(2.5만원+)보다 크게 낮고 "
                "삼겹양지(약 1만원) 수준. 미트박스에는 별도 '채끝등심' 품목도 존재."
            ),
            "question": (
                "한국 수입육 유통에서 엑셀 '센터컷'이 스트립로인 센터컷인지, "
                "삼겹양지(플레이트)·차돌양지(브리스킷) 등 다른 부위의 센터컷인지 확인 요청."
            ),
        },
        {
            "topic": "뼈 위주 갈비 품목의 canonical 배정",
            "context": (
                "호주산 '양지갈비'(약 7천원)->LA갈비(123A), '스페어립'(약 7.8천원)->등갈비/백립(Primal Rib), "
                "'일반갈비'->척갈비(130), 미국산 '숏립앤드'->LA갈비(123A), '립캡'->등심(Rib)으로 배정. "
                "가격 수준이 대표 품목과 크게 다른 저가·뼈 위주 품목임."
            ),
            "question": (
                "각 품목의 실제 원료 부위(AUS-MEAT/IMPS 코드)를 확인하고, "
                "더 적절한 canonical 또는 별도 '갈비뼈류' canonical 분리가 필요한지 의견 요청."
            ),
        },
        {
            "topic": "호주산 품목의 USDA 비교 방식",
            "context": (
                "목심·홍두깨·우둔·등심 등은 미트박스에서 호주산만 거래됨. crosswalk의 usda_compare='proxy'로 표시해 "
                "USDA 가격과의 직접 비교 대신 방향성 참고용으로만 쓰도록 함."
            ),
            "question": (
                "호주산 도매가를 USDA cut 가격(미국 시장)으로 설명하는 것이 타당한지, "
                "MLA/NLRS 등 호주 시세를 별도로 붙여야 하는지 의견 요청."
            ),
        },
        {
            "topic": "앞다리 vs 부채살",
            "context": (
                "USDA Top blade(114D)는 미트박스 '부채살'에 해당. 동시에 미트박스 "
                "'알전각/볼라전각'은 Shoulder clod(114/114A/114E)에 해당. "
                "두 canonical(top_blade, chuck) 모두 KMTA '앞다리'를 공유."
            ),
            "question": (
                "부채살(top blade)을 KMTA 앞다리의 일부로 보는 것이 정확한지, "
                "또는 별도 카테고리(예: 한국 분류상 부채살은 척에 속함)로 분리하는 것이 "
                "더 정확한지 검토."
            ),
        },
    ]
    return pd.DataFrame(questions)


README_TEMPLATE = """# 품목 매핑 검토 패키지 (External LLM Review)

이 폴더의 CSV들은 **GPT, Gemini 등 다른 LLM이 매핑 정확성을 검토**할 수 있도록 생성된 자료입니다.
원본 매핑 정의는 `src/utils/part_mapping.py`의 `CANONICAL_PARTS`에 있습니다.

## 배경

한 ML 가격예측 프로젝트에서 4개의 소고기 데이터 소스를 연결해야 합니다.

| 소스 | 내용 | 단위 | 부위 체계 |
|------|------|------|-----------|
| **미트박스** | 한국 B2B 도매가격 (미국·호주산 부분육·부산물) | 일별, 원/kg | 한국 식육 유통명 (LA갈비, 차돌양지 등) |
| **KMTA 수입** | 한국육류유통수출협회 부위별 수입량 | 월별, 톤 | 11개 대분류 (갈비·등심·목심·…) |
| **KMTA 재고** | 한국육류유통수출협회 부위별 재고 | 월별, 톤 | 12개 대분류 (수입과 거의 동일 + 부산물) |
| **USDA** | 미국 LM_XB403 Boxed Beef 가격 | 일별, USD/cwt | IMPS/NAMP cut code (109E, 116A 등) |

서로 분류 체계가 달라서 **canonical (표준 부위)** 라는 중간 키를 두고 각 소스를 연결했습니다.
예: `la_galbi` -> 미트박스 'LA갈비' + KMTA '갈비' + USDA 123A

미트박스 품목명에는 원산지 구분이 없고(part_name의 '-원산지' 앞부분), 원산지는 `source_inventory.csv`의
`origin`/`usda_compare` 열로 표시합니다. `usda_compare`: direct(미국산+USDA cut) / proxy(호주산 또는
primal 지수만) / none(USDA 대응 없음).

## 검토 요청 사항

1. **canonical 정의가 한국·미국 도축 분류 기준에 비추어 타당한가?**
2. **USDA 코드 -> 한국 부위 매핑이 정확한가?** (특히 Chuck 계열, Loin 계열)
3. **소스 간 1:N, N:1 매핑이 적절히 처리되었는가?**
4. **부적절한 매핑이나 누락된 매핑이 있다면 무엇인가?**

## 파일 안내

### 1. `canonical_summary.csv` ({n_canonical}행)
{n_canonical}개 canonical(표준 부위)의 전체 매핑 정보를 한 행씩 정리.

| 컬럼 | 의미 |
|------|------|
| `canonical_id` | 내부 키 (예: `la_galbi`, `brisket_yangji`) |
| `canonical_name_ko` | 표시명 |
| `kmta_part` | KMTA 수입·재고 통계의 부위명 |
| `meatbox_parts` | 미트박스 품목명(`|`로 구분, 1:N 가능) |
| `usda_codes` | USDA IMPS 코드 (콤마 구분) |
| `usda_primal` | USDA primal 그룹 (Plate, Brisket 등) |
| `ml_target` | ML 가격예측 타깃으로 사용 가능한지 |
| `chain_completeness` | FULL(4소스 모두 연결) / PARTIAL |
| `notes_ko` | 매핑 근거·주의사항 |
| `review_question` | 검토 요청 문장 |

### 2. `usda_codes_detail.csv` ({n_usda}행)
USDA 원본 데이터에 나타난 모든 item_description과 그 매핑 결과.

| 컬럼 | 의미 |
|------|------|
| `usda_code` | IMPS 코드 |
| `usda_description` | USDA 원본 영문 설명 |
| `primal_group` | Brisket, Chuck, Loin, Plate, Rib, Round, Flank |
| `mapped_canonical_id`/`_name_ko` | 매핑된 한국 부위 |
| `status` | MAPPED / UNMAPPED / NO_CODE |
| `review_question` | 코드별 검토 질문 |

### 3. `source_inventory.csv` ({n_source}행)
미트박스(미국·호주, 원산지별)·KMTA 수입·KMTA 재고에 등장하는 모든 부위명과 매핑 결과.
미트박스 행은 전체/최근 {active_days}일 거래 행 수, 최근 거래일, USDA 비교 방식(`usda_compare`) 포함.

### 4. `open_questions.csv` ({n_questions}행)
현재 매핑에서 **불확실한 {n_questions}개 항목**의 배경과 질문. LLM이 우선 답변하면 좋은 항목.

## 검토 결과 회신 형식 (제안)

CSV의 `review_question` 컬럼에 대해 각 행마다:

```
[OK] 매핑이 정확함
[FIX] 잘못됨. 올바른 매핑: ___. 근거: ___
[UNSURE] 확신 없음. 추가 확인 필요: ___
```

`open_questions.csv`는 자유 답변(근거·출처 포함)으로 회신 요청.

## 부록: 한국 부위 ↔ USDA primal 일반 대응

| 한국 분류 | USDA Primal | 비고 |
|-----------|-------------|------|
| 갈비 (LA갈비) | Plate (Short Plate) | 횡경막 아래 늑간 부위 |
| 갈비 (척갈비) | Chuck (Chuck short rib) | 앞쪽 늑간 |
| 갈비 (등갈비/백립) | Rib (back rib) | 등쪽 늑간 |
| 양지 (차돌양지) | Brisket | 가슴 앞쪽 |
| 양지 (삼겹양지) | Plate (Navel) | 가슴 뒤쪽 (Brisket 후방) |
| 목심 | Chuck (Chuck roll 116A) | 미트박스 '알목심'·'목심'(호주) |
| 등심 (꽃등심) | Rib (Ribeye 112A) | 미트박스 '등심'(호주, 2026-10-20~) |
| 채끝 | Loin (Strip loin) | 미트박스 '센터컷'(확인 필요)·'채끝등심' |
| 안심 | Loin (Tenderloin) | 미트박스 호주산 단발 거래 |
| 앞다리 (부채살) | Chuck (Top blade 114D) | 한국 분류 모호 |
| 앞다리 (전각) | Chuck (Shoulder clod 114) | |
| 설도 | Round + Loin top butt | 한국 분류는 후지 |
| 우둔 | Round (Top inside 168/169) | 미트박스 호주산 |
| 홍두깨 | Round (Eye of round 171C) | 미트박스 호주산 |
| 사태 | Shank (USDA boxed beef 미보고) | - |
"""


def export_all() -> dict[str, Path]:
    MAPPING_REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    df_canonical = build_canonical_summary()
    df_usda = build_usda_codes_detail()
    df_source = build_source_inventory()
    df_q = build_open_questions()

    outputs = {
        "canonical_summary.csv": df_canonical,
        "usda_codes_detail.csv": df_usda,
        "source_inventory.csv": df_source,
        "open_questions.csv": df_q,
    }

    saved: dict[str, Path] = {}
    for name, df in outputs.items():
        path = MAPPING_REVIEW_DIR / name
        df.to_csv(str(path), index=False, encoding="utf-8-sig")
        saved[name] = path

    readme = MAPPING_REVIEW_DIR / "README.md"
    readme.write_text(
        README_TEMPLATE.format(
            n_canonical=len(df_canonical),
            n_usda=len(df_usda),
            n_source=len(df_source),
            n_questions=len(df_q),
            active_days=ACTIVE_DAYS,
        ),
        encoding="utf-8",
    )
    saved["README.md"] = readme
    return saved


if __name__ == "__main__":
    saved = export_all()
    print("[완료] 매핑 검토 패키지 생성")
    for name, path in saved.items():
        print(f"  - {name}: {path}")
