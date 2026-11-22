"""
[파일 정의서]
- 파일명: indicator_registry.py
- 역할: 공통 (거시·시장 지표 레지스트리 로더)
- 데이터 소스: config/indicators.csv — 수집기(ECOS·FRED·KMA·MLA·YAHOO·NASS)가 공유하는 지표 정의 한 곳
- 주요 기능:
    1. load_registry(): CSV 를 DataFrame 으로 (active=1 만, 기본)
    2. indicators_for(source): 해당 수집기가 기대하는 dict 모양으로 변환해 리스트 반환
       ECOS  → indicator_id, stat_code, item_code, cycle, indicator_name, unit, freq, country
       FRED  → indicator_id, series_id, indicator_name, unit, freq, country
       KMA   → indicator_id, col, name, unit
       MLA   → indicator_id, mla_id(int), indicator_name, unit
       YAHOO → indicator_id, symbol, indicator_name, unit, freq, country
       NASS 등 그 외 → 원본 열 그대로(code1/code2 포함)
    3. publish_lag(): {indicator_id: 발표시차(개월)} — 모델·스크리닝에서 룩어헤드 방지용
    4. labels(): {indicator_id: 한글 짧은 라벨}
- 지표 추가 방법: config/indicators.csv 에 한 줄 추가 → 다음 실행부터 해당 수집기가 자동 수집,
  preprocess_macro 가 일별 확장, indicator_screen.py 가 유용성 점검. 코드 수정 불필요.
- 주의: indicator_id 는 전 소스에서 유일해야 한다(load_registry 가 중복 시 예외).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import PROJECT_ROOT  # noqa: E402

REGISTRY_CSV = PROJECT_ROOT / "config" / "indicators.csv"
_REQUIRED = ["indicator_id", "source", "code1", "code2", "cycle", "indicator_name", "unit", "freq",
             "country", "group", "publish_lag_m", "label_ko", "active"]


def load_registry(active_only: bool = True) -> pd.DataFrame:
    df = pd.read_csv(REGISTRY_CSV, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing = [c for c in _REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"indicators.csv 열 누락: {missing}")
    df["indicator_id"] = df["indicator_id"].str.strip()
    df["source"] = df["source"].str.strip().str.upper()
    dup = df["indicator_id"][df["indicator_id"].duplicated()].tolist()
    if dup:
        raise ValueError(f"indicators.csv indicator_id 중복: {dup}")
    df["publish_lag_m"] = pd.to_numeric(df["publish_lag_m"], errors="coerce").fillna(1).astype(int)
    df["active"] = df["active"].str.strip().isin(["1", "true", "True", "y", "Y"])
    if active_only:
        df = df[df["active"]]
    return df.reset_index(drop=True)


def indicators_for(source: str) -> list[dict]:
    src = source.upper()
    rows = load_registry()
    rows = rows[rows["source"] == src]
    out: list[dict] = []
    for r in rows.itertuples(index=False):
        base = {"indicator_id": r.indicator_id, "indicator_name": r.indicator_name, "unit": r.unit,
                "freq": r.freq or r.cycle, "country": r.country or None}
        if src == "ECOS":
            d = {**base, "stat_code": r.code1, "item_code": r.code2, "cycle": r.cycle or r.freq}
        elif src == "FRED":
            d = {**base, "series_id": r.code1}
        elif src == "KMA":
            d = {"indicator_id": r.indicator_id, "col": r.code1, "name": r.indicator_name, "unit": r.unit}
        elif src == "MLA":
            d = {**base, "mla_id": int(r.code1)}
        elif src == "YAHOO":
            d = {**base, "symbol": r.code1}
        else:
            d = {**base, "code1": r.code1, "code2": r.code2, "cycle": r.cycle}
        if d.get("country") is None:
            d.pop("country", None)
        out.append(d)
    return out


def publish_lag() -> dict[str, int]:
    df = load_registry()
    return dict(zip(df["indicator_id"], df["publish_lag_m"]))


def labels() -> dict[str, str]:
    df = load_registry()
    return dict(zip(df["indicator_id"], df["label_ko"]))


def groups() -> dict[str, str]:
    df = load_registry()
    return dict(zip(df["indicator_id"], df["group"]))


if __name__ == "__main__":
    reg = load_registry()
    print(reg[["indicator_id", "source", "freq", "group", "publish_lag_m", "label_ko"]].to_string(index=False))
    for s in sorted(reg["source"].unique()):
        print(s, len(indicators_for(s)))
