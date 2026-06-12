# [파일 정의서]
# - 파일명: 05_USDA_Analysis.py
# - 역할: 시각화
# - 대상: 미국 USDA 도매가 및 다소스 통합 비교
# - 데이터 소스: usda_plate_usd_kg.csv, processed_usda_cost.csv, dashboard_ready_data.csv,
#                 master_import_volume.csv, beef_stock_data.xlsx, part_crosswalk.csv
# - 주요 기능:
#   1. USDA Plate(우삼겹) 도매 시세 (USD/kg)
#   2. 표준 부위(canonical) 기준 미트박스·USDA·수입·재고 통합 시계열
#   3. 소스 간 품목 매핑(Crosswalk) 조회

import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    BEEF_STOCK_XLSX,
    DASHBOARD_READY_CSV,
    MASTER_IMPORT_VOLUME_CSV,
    PART_CROSSWALK_CSV,
    PROCESSED_USDA_COST_CSV,
    USDA_PLATE_USD_KG_CSV,
    USDA_PRIMAL_HISTORY_CSV,
)
from utils.part_mapping import (
    build_crosswalk_dataframe,
    export_crosswalk,
    get_part,
    list_canonical_parts,
)

st.set_page_config(page_title="USDA 도매가 및 통합 분석", layout="wide")


def _data_mtime() -> float:
    paths = [
        USDA_PLATE_USD_KG_CSV,
        PROCESSED_USDA_COST_CSV,
        DASHBOARD_READY_CSV,
        MASTER_IMPORT_VOLUME_CSV,
        BEEF_STOCK_XLSX,
        PART_CROSSWALK_CSV,
    ]
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


@st.cache_data
def load_plate_usd(_key: float) -> pd.DataFrame | None:
    if not USDA_PLATE_USD_KG_CSV.exists():
        return None
    df = pd.read_csv(USDA_PLATE_USD_KG_CSV)
    df["date"] = pd.to_datetime(df["report_date"])
    return df.sort_values("date")


@st.cache_data
def load_usda_cuts(_key: float) -> pd.DataFrame | None:
    if not PROCESSED_USDA_COST_CSV.exists():
        return None
    usecols = ["Date", "item_description", "grade", "weighted_average_USD_kg", "Exchange_Rate"]
    df = pd.read_csv(str(PROCESSED_USDA_COST_CSV), usecols=usecols, low_memory=False)
    df["date"] = pd.to_datetime(df["Date"])
    df["usda_code"] = df["item_description"].astype(str).apply(
        lambda s: (m.group(1) if (m := re.search(r"\(\s*([0-9]+[A-Z]?)\s+", s)) else "")
    )
    return df


@st.cache_data
def load_usda_primal(_key: float) -> pd.DataFrame | None:
    """USDA 프라이멀 지수 (Choice, 100lbs -> USD/kg 변환)."""
    if not USDA_PRIMAL_HISTORY_CSV.exists():
        return None
    df = pd.read_csv(
        str(USDA_PRIMAL_HISTORY_CSV),
        usecols=["report_date", "primal_desc", "choice_600_900"],
    )
    df["date"] = pd.to_datetime(df["report_date"])
    df["choice_usd_kg"] = pd.to_numeric(df["choice_600_900"], errors="coerce") / 45.3592
    return df.dropna(subset=["choice_usd_kg"])


@st.cache_data
def load_meatbox_us(_key: float) -> pd.DataFrame | None:
    if not DASHBOARD_READY_CSV.exists():
        return None
    df = pd.read_csv(str(DASHBOARD_READY_CSV))
    df["date"] = pd.to_datetime(df["date"])
    return df[df["category"] == "미국"].copy()


@st.cache_data
def load_import_monthly(_key: float) -> pd.DataFrame | None:
    if not MASTER_IMPORT_VOLUME_CSV.exists():
        return None
    df = pd.read_csv(str(MASTER_IMPORT_VOLUME_CSV), encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["std_date"])
    id_vars = ["date", "구분"]
    val_vars = [c for c in df.columns if c.startswith("부위별_") and "계_합계" not in c]
    long_df = df.melt(id_vars=id_vars, value_vars=val_vars, var_name="raw", value_name="volume")
    long_df["kmta_part"] = long_df["raw"].str.replace("부위별_", "").str.replace("_합계", "")
    return long_df


@st.cache_data
def load_stock_monthly(_key: float) -> pd.DataFrame | None:
    if not BEEF_STOCK_XLSX.exists():
        return None
    df = pd.read_excel(str(BEEF_STOCK_XLSX))
    col_map = {}
    for col in df.columns:
        if "기준년월" in col:
            col_map[col] = "date"
        elif "부위별" in col:
            col_map[col] = "kmta_part"
        elif "조사재고량" in col:
            col_map[col] = "inventory"
    df = df.rename(columns=col_map)
    if "inventory" not in df.columns:
        return None
    df = df[~df["inventory"].astype(str).str.contains("없습니다|자료가", na=False)]
    df["inventory"] = df["inventory"].astype(str).str.replace(",", "").astype(float)
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "kmta_part", "inventory"]]


@st.cache_data
def load_crosswalk(_key: float) -> pd.DataFrame:
    if not PART_CROSSWALK_CSV.exists():
        export_crosswalk()
    if PART_CROSSWALK_CSV.exists():
        return pd.read_csv(str(PART_CROSSWALK_CSV), encoding="utf-8-sig")
    return build_crosswalk_dataframe()


def _filter_period(df: pd.DataFrame, months: int | None, date_col: str = "date") -> pd.DataFrame:
    if df is None or df.empty or months is None:
        return df
    end = df[date_col].max()
    start = end - pd.DateOffset(months=months)
    return df[df[date_col] >= start]


def _monthly_mean(df: pd.DataFrame, value_col: str, date_col: str = "date") -> pd.DataFrame:
    out = df.copy()
    out["month"] = out[date_col].dt.to_period("M").dt.to_timestamp()
    return out.groupby("month", as_index=False)[value_col].mean()


def build_integrated_series(canonical_id: str, cache_key: float) -> dict[str, pd.DataFrame]:
    """표준 부위 기준으로 소스별 시계열을 월 단위로 정렬한다."""
    spec = get_part(canonical_id)
    if spec is None:
        return {}

    result: dict[str, pd.DataFrame] = {}

    mb = load_meatbox_us(cache_key)
    if mb is not None and spec.meatbox_parts:
        sub = mb[mb["part"].isin(spec.meatbox_parts)]
        if not sub.empty:
            daily = sub.groupby("date", as_index=False)["wholesale_price"].mean()
            result["meatbox_krw_kg"] = _monthly_mean(daily, "wholesale_price")

    cuts = load_usda_cuts(cache_key)
    if cuts is not None and spec.usda_codes:
        sub = cuts[cuts["usda_code"].isin(spec.usda_codes)].dropna(subset=["weighted_average_USD_kg"])
        if not sub.empty:
            daily = sub.groupby("date", as_index=False)["weighted_average_USD_kg"].mean()
            result["usda_usd_kg"] = _monthly_mean(daily, "weighted_average_USD_kg")
            daily_krw = sub.copy()
            daily_krw["krw_kg"] = daily_krw["weighted_average_USD_kg"] * daily_krw["Exchange_Rate"]
            krw = daily_krw.groupby("date", as_index=False)["krw_kg"].mean()
            result["usda_krw_kg"] = _monthly_mean(krw, "krw_kg")
    elif spec.usda_primal:
        # cut 코드가 없는 부위(예: 삼겹양지)는 프라이멀 지수로 대체
        primal = load_usda_primal(cache_key)
        if primal is not None:
            sub = primal[primal["primal_desc"] == spec.usda_primal]
            if not sub.empty:
                daily = sub.groupby("date", as_index=False)["choice_usd_kg"].mean()
                daily = daily.rename(columns={"choice_usd_kg": "weighted_average_USD_kg"})
                result["usda_usd_kg"] = _monthly_mean(daily, "weighted_average_USD_kg")

    imp = load_import_monthly(cache_key)
    if imp is not None:
        sub = imp[imp["kmta_part"] == spec.kmta_part]
        if not sub.empty:
            monthly = sub.groupby("date", as_index=False)["volume"].sum()
            monthly = monthly.rename(columns={"date": "month", "volume": "import_ton"})
            result["import_ton"] = monthly

    stk = load_stock_monthly(cache_key)
    if stk is not None:
        sub = stk[stk["kmta_part"] == spec.kmta_part]
        if not sub.empty:
            monthly = sub.groupby("date", as_index=False)["inventory"].sum()
            monthly = monthly.rename(columns={"date": "month", "inventory": "stock_ton"})
            result["stock_ton"] = monthly

    return result


def _plot_plate(df: pd.DataFrame, months: int | None) -> go.Figure:
    data = _filter_period(df, months)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["date"], y=data["choice_usd_per_kg"],
        name="Choice USD/kg", line=dict(color="#1565C0"),
    ))
    fig.add_trace(go.Scatter(
        x=data["date"], y=data["select_usd_per_kg"],
        name="Select USD/kg", line=dict(color="#EF6C00"),
    ))
    fig.update_layout(
        title="USDA Primal Plate (우삼겹) 도매가",
        xaxis_title="날짜",
        yaxis_title="USD/kg",
        hovermode="x unified",
        height=420,
    )
    return fig


def _plot_integrated(canonical_id: str, series: dict[str, pd.DataFrame], months: int | None) -> go.Figure:
    spec = get_part(canonical_id)
    titles = [
        "미트박스 도매가 (월평균, 원/kg)",
        "USDA 도매가 (월평균, USD/kg)",
        "수입량 (톤, 월)",
        "재고 (톤, 월)",
    ]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=titles)

    if "meatbox_krw_kg" in series:
        d = series["meatbox_krw_kg"]
        if months:
            d = d[d["month"] >= d["month"].max() - pd.DateOffset(months=months)]
        fig.add_trace(
            go.Scatter(x=d["month"], y=d["wholesale_price"], name="미트박스", line=dict(color="#C62828")),
            row=1, col=1,
        )

    if "usda_usd_kg" in series:
        d = series["usda_usd_kg"]
        if months:
            d = d[d["month"] >= d["month"].max() - pd.DateOffset(months=months)]
        fig.add_trace(
            go.Scatter(x=d["month"], y=d["weighted_average_USD_kg"], name="USDA USD", line=dict(color="#1565C0")),
            row=2, col=1,
        )

    if "import_ton" in series:
        d = series["import_ton"]
        if months:
            d = d[d["month"] >= d["month"].max() - pd.DateOffset(months=months)]
        fig.add_trace(
            go.Bar(x=d["month"], y=d["import_ton"], name="수입", marker_color="#2E7D32"),
            row=3, col=1,
        )

    if "stock_ton" in series:
        d = series["stock_ton"]
        if months:
            d = d[d["month"] >= d["month"].max() - pd.DateOffset(months=months)]
        fig.add_trace(
            go.Scatter(x=d["month"], y=d["stock_ton"], name="재고", line=dict(color="#6A1B9A")),
            row=4, col=1,
        )

    fig.update_layout(
        title=f"통합 분석 — {spec.name_ko} ({spec.canonical_id})",
        height=900,
        showlegend=False,
    )
    return fig


# --------------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------------
st.title("USDA 도매가 및 다소스 통합 분석")
st.caption(
    "미트박스(일별) · USDA(일별) · 수입·재고(KMTA 월별)를 "
    "표준 부위(canonical)로 연결합니다. ML 피처 설계의 기준 매핑은 품목 Crosswalk 탭을 참고하세요."
)

cache_key = _data_mtime()
ml_parts = list_canonical_parts(ml_only=True)

st.sidebar.header("조회 설정")
period_map = {"12개월": 12, "36개월": 36, "전체": None}
period_label = st.sidebar.radio("조회 기간", list(period_map.keys()), index=0)
period_months = period_map[period_label]

tab_plate, tab_integrated, tab_crosswalk, tab_method = st.tabs([
    "USDA Plate 시세",
    "통합 비교 (표준 부위)",
    "품목 Crosswalk",
    "매핑 방법론",
])

with tab_plate:
    plate_df = load_plate_usd(cache_key)
    if plate_df is None:
        st.error("usda_plate_usd_kg.csv 가 없습니다. run_daily_update.py --full 을 실행하세요.")
    else:
        latest = plate_df["date"].max().strftime("%Y-%m-%d")
        st.markdown(f"**최신일:** {latest} | Primal Plate Choice / Select (USD/kg)")
        st.plotly_chart(_plot_plate(plate_df, period_months), use_container_width=True)

        with st.expander("원본 데이터 미리보기"):
            st.dataframe(
                plate_df.tail(20)[["date", "choice_usd_per_kg", "select_usd_per_kg"]],
                hide_index=True,
                use_container_width=True,
            )

with tab_integrated:
    part_options = {f"{p.name_ko} ({p.canonical_id})": p.canonical_id for p in ml_parts}
    selected_label = st.selectbox("표준 부위", list(part_options.keys()))
    canonical_id = part_options[selected_label]
    spec = get_part(canonical_id)

    st.markdown(
        f"**{spec.name_ko}** — KMTA `{spec.kmta_part}` | "
        f"미트박스 {len(spec.meatbox_parts)}종 | USDA 코드 {', '.join(spec.usda_codes) or '없음'}"
    )
    if spec.notes:
        st.info(spec.notes)

    series = build_integrated_series(canonical_id, cache_key)
    if not series:
        st.warning("선택 부위에 대해 표시할 시계열이 없습니다. 매핑 또는 원본 데이터를 확인하세요.")
    else:
        st.plotly_chart(_plot_integrated(canonical_id, series, period_months), use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**소스별 최신 월**")
            summary = []
            for key, df in series.items():
                if df.empty:
                    continue
                col = [c for c in df.columns if c != "month"][0]
                row = df.sort_values("month").iloc[-1]
                summary.append({"소스": key, "월": row["month"].strftime("%Y-%m"), "값": round(row[col], 2)})
            if summary:
                st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)

        with c2:
            st.markdown("**미트박스 매핑 품목**")
            st.write(", ".join(spec.meatbox_parts) if spec.meatbox_parts else "(없음)")

with tab_crosswalk:
    cw = load_crosswalk(cache_key)
    st.markdown("소스별 품목명이 **canonical_id** 로 연결됩니다. `part_crosswalk.csv` 와 동기화됩니다.")

    filter_name = st.selectbox(
        "표준 부위 필터",
        ["전체"] + sorted(cw["canonical_name_ko"].unique()),
    )
    show = cw if filter_name == "전체" else cw[cw["canonical_name_ko"] == filter_name]

    st.dataframe(
        show[
            [
                "canonical_id",
                "canonical_name_ko",
                "kmta_part",
                "source",
                "source_key",
                "source_label",
                "usda_primal",
                "ml_target",
                "notes",
            ]
        ],
        hide_index=True,
        use_container_width=True,
        height=480,
    )
    if st.button("Crosswalk CSV 재생성"):
        path = export_crosswalk()
        st.success(f"저장 완료: {path}")
        st.cache_data.clear()

with tab_method:
    st.markdown("""
### 품목 매핑 방법론 (ML 선행 작업)

데이터 소스마다 부위 명칭·해상도가 다릅니다. 머신러닝 피처를 만들려면 **표준 부위(canonical)** 를
중간 키로 두고 각 소스를 연결해야 합니다.

| 계층 | 역할 | 예시 (갈비) |
|------|------|-------------|
| **canonical** | ML·BI 통합 키 | `galbi` / 갈비 |
| **meatbox** | 국내 B2B 도매가 (미국산, 일별) | LA갈비, 앞/척갈비, 등갈비/백립 … |
| **kmta** | 수입량·재고 (월별, **동일 명칭**) | 갈비 |
| **usda_cut** | 미국 도매가 (일별, LM_XB403 코드) | 123A, 130 |
| **usda_primal** | 프라이멀 지수 (Plate 등) | Primal Plate |

#### 규칙

1. **수입 = 재고**: KMTA 부위 체계를 공유하므로 `kmta_part` 하나로 두 소스를 동시에 연결합니다.
2. **미트박스는 1:N**: 한 표준 부위에 여러 미트박스 품목이 매핑될 수 있습니다. 통합 시 **월평균 산술평균**을 사용합니다.
3. **USDA는 코드 단위**: `item_description` 에서 추출한 코드(예: 123A)로 연결합니다. `validate_mapping.py` 와 동일 출처입니다.
4. **해상도 불일치**: 부채살(미트박스)은 KMTA `앞다리` 합산에 포함 — 수입·재고와 1:1이 아닐 수 있습니다. `ml_target=False` 로 표시된 부위는 ML에서 제외하거나 별도 모델을 권장합니다.
5. **시계열 정렬**: 가격(일별)은 **월평균**으로 리샘플해 수입·재고(월별)와 비교합니다.

#### 코드 위치

- 매핑 정의: `src/utils/part_mapping.py` (`CANONICAL_PARTS`)
- USDA 코드 검증: `src/utils/validate_mapping.py`
- 산출 CSV: `data/1_processed/part_crosswalk.csv`

#### ML 피처 설계 시 권장

- 타깃: `meatbox` 월평균 도매가 (미국산, canonical 부위)
- 설명변수: lag된 `usda_usd_kg`, `import_ton`, `stock_ton`, `Exchange_Rate`
- categorical: `canonical_id` (부위별 모델 분리 또는 global 모델 + 부위 더미)
""")
