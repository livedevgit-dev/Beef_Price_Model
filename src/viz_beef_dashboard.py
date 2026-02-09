import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import platform
import warnings
import os

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="소고기 수급 분석 (Mobile)", layout="wide")

import os
import matplotlib.font_manager as fm

# OS별 폰트 설정 (클라우드 리눅스 환경 대응)
if platform.system() == 'Darwin': # 맥
    plt.rc('font', family='AppleGothic') 
elif platform.system() == 'Windows': # 윈도우
    plt.rc('font', family='Malgun Gothic')
else: # 리눅스 (Streamlit Cloud)
    # 한글 폰트 설치 여부 확인 후 설정
    try:
        plt.rc('font', family='NanumGothic')
    except:
        pass
        
plt.rc('axes', unicode_minus=False)
warnings.simplefilter(action='ignore', category=FutureWarning)

# ---------------------------------------------------------
# 2. 데이터 로드 설정
# ---------------------------------------------------------
TARGET_FILES = {
    'import1': '미국산소고기_2019_2024_Total.csv',
    'import2': '미국산소고기_202412_202511.csv',
    'stock': 'beef_stock_data.xlsx'
}

def get_data_dir():
    """데이터 폴더 경로 반환"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    return os.path.join(project_root, "data", "0_raw")

def clean_numeric_column(series):
    series = series.astype(str).str.replace(',', '')
    series = pd.to_numeric(series, errors='coerce')
    return series.fillna(0)

@st.cache_data
def load_data_final():
    data_dir = get_data_dir()
    df_import_final = pd.DataFrame()
    temp_list = []
    
    if os.path.exists(data_dir):
        files = [TARGET_FILES['import1'], TARGET_FILES['import2']]
        for fname in files:
            fpath = os.path.join(data_dir, fname)
            if os.path.exists(fpath):
                try:
                    df = pd.read_csv(fpath)
                    w_col = next((c for c in df.columns if '중량' in c), None)
                    d_col = next((c for c in df.columns if '년월' in c or '일자' in c), None)
                    if w_col and d_col:
                        df[w_col] = clean_numeric_column(df[w_col]) / 1000 # Ton 변환
                        df['Date'] = pd.to_datetime(df[d_col])
                        df['부위'] = df['부위'].astype(str).str.strip()
                        df = df.rename(columns={w_col: 'Import_Vol'})
                        temp_list.append(df[['Date', '부위', 'Import_Vol']])
                except: pass

    if temp_list:
        df_all = pd.concat(temp_list, ignore_index=True)
        df_all = df_all.drop_duplicates(subset=['Date', '부위'], keep='last')
        df_import_final = df_all.pivot_table(index='Date', columns='부위', values='Import_Vol', aggfunc='sum').fillna(0)

    df_stock_final = None
    stock_files = [TARGET_FILES['stock'], 'beef_stock_data.csv']
    for fname in stock_files:
        fpath = os.path.join(data_dir, fname)
        if os.path.exists(fpath):
            try:
                if fname.endswith('.xlsx'): df = pd.read_excel(fpath, engine='openpyxl')
                else: df = pd.read_csv(fpath)
                
                cols = df.columns
                s_date = next((c for c in cols if '년월' in str(c) or 'Date' in str(c)), None)
                s_item = next((c for c in cols if '부위' in str(c)), None)
                s_vol = next((c for c in cols if '재고' in str(c)), None)

                if s_date and s_item and s_vol:
                    df = df.rename(columns={s_date: 'Date', s_item: '부위', s_vol: 'Stock_Vol'})
                    df['Date'] = pd.to_datetime(df['Date'])
                    df['Stock_Vol'] = clean_numeric_column(df['Stock_Vol'])
                    df['부위'] = df['부위'].astype(str).str.strip()
                    df_stock_final = df.pivot_table(index='Date', columns='부위', values='Stock_Vol', aggfunc='sum').fillna(0)
                    break
            except: pass
    
    return df_import_final, df_stock_final

# ---------------------------------------------------------
# 3. Y축 포맷팅 함수 (0 제거)
# ---------------------------------------------------------
def y_fmt(x, pos):
    if x == 0: return "" # 0이면 빈 문자열 반환
    return f'{int(x):,}' # 나머지는 콤마 포맷

# ---------------------------------------------------------
# 4. 시각화
# ---------------------------------------------------------
st.title("🥩 미국산 소고기 수급 현황")
st.markdown("---")

imp_data, stk_data = load_data_final()

if not imp_data.empty:
    if stk_data is not None:
        common = sorted(list(set(imp_data.columns) & set(stk_data.columns)))
        others = sorted(list(set(imp_data.columns) - set(stk_data.columns)))
        items = common + others
    else:
        items = sorted(list(imp_data.columns))
        
    selected_item = st.selectbox("분석할 부위를 선택하세요", items)
    
    imp_series = imp_data[selected_item].rename('Import')
    
    fig, ax1 = plt.subplots(figsize=(14, 6))
    
    # 1. 수입량
    ax1.bar(imp_series.index, imp_series, color='#AED6F1', label='수입량 (Ton)', width=20, alpha=0.9, zorder=3)
    
    # 2. 재고량
    has_stock = False
    if stk_data is not None and selected_item in stk_data.columns:
        stk_series = stk_data[selected_item].rename('Stock')
        combined = pd.concat([imp_series, stk_series], axis=1)
        
        if combined['Stock'].sum() > 0:
            has_stock = True
            ax2 = ax1.twinx()
            ax2.plot(combined.index, combined['Stock'], color='#E74C3C', linewidth=3, marker='o', markersize=4, label='재고량 (Ton)', zorder=4)
            ax2.set_ylabel('재고량 (Ton)', fontsize=11, fontweight='bold', color='#C0392B')
            ax2.yaxis.set_major_formatter(FuncFormatter(y_fmt)) # 0 제거 포맷터 적용
            
            l1, lb1 = ax1.get_legend_handles_labels()
            l2, lb2 = ax2.get_legend_handles_labels()
            ax1.legend(l1+l2, lb1+lb2, loc='upper left')
            
            curr_stock = combined['Stock'].dropna().iloc[-1] if not combined['Stock'].dropna().empty else 0
            st.metric("현재 재고량", f"{curr_stock:,.0f} Ton")
        else:
            ax1.legend(loc='upper left')
    else:
        ax1.legend(loc='upper left')

    # 3. 연도 표기 (아래쪽으로 이동)
    years = imp_series.index.year.unique()
    for i, year in enumerate(years):
        if i % 2 == 0:
            start = pd.Timestamp(f"{year}-01-01")
            end = pd.Timestamp(f"{year}-12-31")
            ax1.axvspan(start, end, color='gray', alpha=0.1, zorder=1)
        
        # [핵심] 연도를 X축 아래로 내림 (transform 사용)
        mid_date = pd.Timestamp(f"{year}-07-01")
        # y=-0.13 좌표는 X축 바로 아래를 의미함
        ax1.text(mid_date, -0.13, str(year), transform=ax1.get_xaxis_transform(),
                 ha='center', va='top', fontsize=11, fontweight='bold', color='#555555')

    # 4. 축 설정
    ax1.set_title(f'[{selected_item}] 월별 수급 추이', fontsize=16, pad=20)
    ax1.set_ylabel('수입량 (Ton)', fontsize=11, fontweight='bold', color='#2E86C1')
    ax1.grid(True, axis='y', linestyle='--', alpha=0.5, zorder=2)
    ax1.yaxis.set_major_formatter(FuncFormatter(y_fmt)) # 0 제거 포맷터 적용

    # [핵심] 월(Month) 표기 간소화 (0 제거)
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    # 람다 함수를 써서 '01' -> '1'로 변환
    ax1.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: str(mdates.num2date(x).month)))
    plt.xticks(rotation=0, fontsize=9)
    ax1.set_xlabel('월 (Month)', fontsize=10, labelpad=10)

    # 5. 여백 조정 (연도가 잘리지 않게 하단 여백 확보)
    plt.subplots_adjust(bottom=0.2)
    ax1.set_xlim(imp_series.index[0] - pd.Timedelta(days=15), imp_series.index[-1] + pd.Timedelta(days=15))

    st.pyplot(fig)
    
    with st.expander("📋 상세 데이터 보기 (Ton)"):
        if has_stock:
            view_df = combined[['Import', 'Stock']].sort_index(ascending=False)
            view_df.columns = ['수입량', '재고량']
        else:
            view_df = imp_series.to_frame(name='수입량').sort_index(ascending=False)
        st.dataframe(view_df.style.format("{:,.0f}")) # 소수점 없이 깔끔하게

else:
    st.error(f"데이터 로드 실패: {get_data_dir()}")