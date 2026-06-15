# 품목 매핑 검토 패키지 (External LLM Review)

이 폴더의 CSV들은 **GPT, Gemini 등 다른 LLM이 매핑 정확성을 검토**할 수 있도록 생성된 자료입니다.
원본 매핑 정의는 `src/utils/part_mapping.py`의 `CANONICAL_PARTS`에 있습니다.

## 배경

한 ML 가격예측 프로젝트에서 4개의 소고기 데이터 소스를 연결해야 합니다.

| 소스 | 내용 | 단위 | 부위 체계 |
|------|------|------|-----------|
| **미트박스** | 한국 B2B 도매가격 (미국산 부분육) | 일별, 원/kg | 한국 식육 유통명 (LA갈비, 차돌양지 등) |
| **KMTA 수입** | 한국육류유통수출협회 부위별 수입량 | 월별, 톤 | 11개 대분류 (갈비·등심·목심·…) |
| **KMTA 재고** | 한국육류유통수출협회 부위별 재고 | 월별, 톤 | 12개 대분류 (수입과 거의 동일 + 부산물) |
| **USDA** | 미국 LM_XB403 Boxed Beef 가격 | 일별, USD/cwt | IMPS/NAMP cut code (109E, 116A 등) |

서로 분류 체계가 달라서 **canonical (표준 부위)** 라는 중간 키를 두고 각 소스를 연결했습니다.
예: `la_galbi` -> 미트박스 'LA갈비' + KMTA '갈비' + USDA 123A

## 검토 요청 사항

1. **canonical 정의가 한국·미국 도축 분류 기준에 비추어 타당한가?**
2. **USDA 코드 -> 한국 부위 매핑이 정확한가?** (특히 Chuck 계열, Loin 계열)
3. **소스 간 1:N, N:1 매핑이 적절히 처리되었는가?**
4. **부적절한 매핑이나 누락된 매핑이 있다면 무엇인가?**

## 파일 안내

### 1. `canonical_summary.csv` (17행)
17개 canonical(표준 부위)의 전체 매핑 정보를 한 행씩 정리.

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

### 2. `usda_codes_detail.csv` (42행)
USDA 원본 데이터에 나타난 모든 item_description과 그 매핑 결과.

| 컬럼 | 의미 |
|------|------|
| `usda_code` | IMPS 코드 |
| `usda_description` | USDA 원본 영문 설명 |
| `primal_group` | Brisket, Chuck, Loin, Plate, Rib, Round, Flank |
| `mapped_canonical_id`/`_name_ko` | 매핑된 한국 부위 |
| `status` | MAPPED / UNMAPPED / NO_CODE |
| `review_question` | 코드별 검토 질문 |

### 3. `source_inventory.csv` (50행)
미트박스·KMTA 수입·KMTA 재고에 등장하는 모든 부위명과 매핑 결과.

### 4. `open_questions.csv` (7행)
현재 매핑에서 **불확실한 7개 항목**의 배경과 질문. LLM이 우선 답변하면 좋은 항목.

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
| 목심 | Chuck (Chuck roll) | 목 부위 |
| 등심 (꽃등심) | Rib (Ribeye) | 한국 미트박스 미취급 |
| 채끝 | Loin (Strip loin) | 미트박스 '센터컷' |
| 안심 | Loin (Tenderloin) | 미트박스 미취급 |
| 앞다리 (부채살) | Chuck (Top blade 114D) | 한국 분류 모호 |
| 앞다리 (전각) | Chuck (Shoulder clod 114) | |
| 설도 | Round + Loin top butt | 한국 분류는 후지 |
| 우둔 | Round (Top inside) | 미트박스 미취급 |
| 사태 | Shank (USDA boxed beef 미보고) | - |
