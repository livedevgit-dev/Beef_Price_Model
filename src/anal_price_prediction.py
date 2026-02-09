import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import RadioButtons
import matplotlib.dates as mdates
import seaborn as sns
import os
import sys
import tkinter as tk
from tkinter import filedialog
import warnings

# ---------------------------------------------------------
# 1. 환경 설정
# ---------------------------------------------------------
plt.rc('font', family='Malgun Gothic') 
plt.rc('axes', unicode_minus=False)
warnings.simplefilter(action='ignore', category=FutureWarning)

def get_search_paths():
    """파일을 찾을 경로 후보군 생성 (프로젝트 데이터 폴더)"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_dir = os.path.join(project_root, "data", "0_raw")
    return [data_dir]

def select_file_manually(title_text):
    """파일 선택 팝업창"""
    print(f"\n[요청] {title_text}")
    print(" -> 윈도우 탐색기 창이 뜨면 파일을 선택해주세요...")
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        file_path = filedialog.askopenfilename(
            title=title_text,
            filetypes=[("Data Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")]
        )
        root.destroy()
        return file_path
    except:
        return None

def clean_numeric_column(series):
    """숫자 컬럼 세탁 (콤마 제거, 한글/특수문자 0 처리)"""
    series = series.astype(str).str.replace(',', '')
    series = pd.to_numeric(series, errors='coerce') # 숫자가 아니면 NaN
    return series.fillna(0) # NaN을 0으로 변환

def load_integrated_data():
    search_paths = get_search_paths()
    print(f"[시스템] 검색 경로: {search_paths}")
    
    # -----------------------------------------------------
    # (1) 수입 데이터 로드 (Import Data)
    # -----------------------------------------------------
    import_files = ['미국산소고기_2019_2024_Total.csv', '미국산소고기_202412_202511.csv']
    df_import_list = []
    
    print("\n--- [1] 수입 데이터 로드 ---")
    
    # 자동 탐색
    for f in import_files:
        for path_dir in search_paths:
            full_path = os.path.join(path_dir, f)
            if os.path.exists(full_path):
                try:
                    temp = pd.read_csv(full_path)
                    # 컬럼 자동 찾기
                    w_col = next((c for c in temp.columns if '중량' in c), None)
                    d_col = next((c for c in temp.columns if '년월' in c or '일자' in c), None)
                    
                    if w_col and d_col:
                        temp[w_col] = clean_numeric_column(temp[w_col])
                        temp['Date'] = pd.to_datetime(temp[d_col])
                        temp = temp.rename(columns={w_col: 'Import_Vol'})
                        df_import_list.append(temp[['Date', '부위', 'Import_Vol']])
                        print(f" -> 성공: {f} (위치: {path_dir})")
                        break # 찾았으면 다음 파일로
                except:
                    pass

    # 자동 실패 시 수동 선택
    if not df_import_list:
        print(" -> [경고] 수입 파일을 자동으로 찾지 못했습니다.")
        manual_path = select_file_manually("수입 데이터 파일(CSV)을 선택해주세요")
        if manual_path:
            try:
                temp = pd.read_csv(manual_path)
                w_col = next((c for c in temp.columns if '중량' in c), None)
                d_col = next((c for c in temp.columns if '년월' in c or '일자' in c), None)
                if w_col and d_col:
                    temp[w_col] = clean_numeric_column(temp[w_col])
                    temp['Date'] = pd.to_datetime(temp[d_col])
                    temp = temp.rename(columns={w_col: 'Import_Vol'})
                    df_import_list.append(temp[['Date', '부위', 'Import_Vol']])
            except Exception as e:
                print(f"오류: {e}")

    if not df_import_list:
        return None, None

    df_import_all = pd.concat(df_import_list, ignore_index=True)
    pivot_import = df_import_all.pivot_table(index='Date', columns='부위', values='Import_Vol', aggfunc='sum').fillna(0)

    # -----------------------------------------------------
    # (2) 재고 데이터 로드 (Stock Data)
    # -----------------------------------------------------
    print("\n--- [2] 재고 데이터 로드 ---")
    stock_candidates = ['beef_stock_data.xlsx', 'beef_stock_data.csv', 'beef_stock_data.xlsx - Sheet1.csv']
    df_stock = None
    
    # 자동 탐색
    for fname in stock_candidates:
        for path_dir in search_paths:
            full_path = os.path.join(path_dir, fname)
            if os.path.exists(full_path):
                try:
                    if '.xlsx' in fname:
                        df_stock = pd.read_excel(full_path, engine='openpyxl')
                    else:
                        df_stock = pd.read_csv(full_path)
                    print(f" -> 성공: {fname} (위치: {path_dir})")
                    break
                except:
                    continue
        if df_stock is not None: break

    # 수동 선택
    if df_stock is None:
        print(" -> [경고] 재고 파일을 자동으로 찾지 못했습니다.")
        manual_path = select_file_manually("재고 데이터 파일(beef_stock_data)을 선택해주세요")
        if manual_path:
            try:
                if manual_path.endswith('.xlsx'):
                    df_stock = pd.read_excel(manual_path, engine='openpyxl')
                else:
                    df_stock = pd.read_csv(manual_path)
            except Exception as e:
                print(f"[에러] 읽기 실패: {e}")
                return pivot_import, None
        else:
            return pivot_import, None

    # 재고 데이터 전처리
    cols = df_stock.columns
    s_date = next((c for c in cols if '년월' in str(c) or 'Date' in str(c)), None)
    s_item = next((c for c in cols if '부위' in str(c)), None)
    s_vol = next((c for c in cols if '재고' in str(c)), None)

    if not (s_date and s_item and s_vol):
        print(f"[에러] 컬럼 인식 실패: {list(cols)}")
        return pivot_import, None

    df_stock = df_stock.rename(columns={s_date: 'Date', s_item: '부위', s_vol: 'Stock_Vol'})
    df_stock['Date'] = pd.to_datetime(df_stock['Date'])
    # [핵심] 한글/노이즈 제거 후 숫자 변환
    df_stock['Stock_Vol'] = clean_numeric_column(df_stock['Stock_Vol'])

    pivot_stock = df_stock.pivot_table(index='Date', columns='부위', values='Stock_Vol', aggfunc='sum').fillna(0)
    
    return pivot_import, pivot_stock

# ---------------------------------------------------------
# 3. 시각화 (Dashboard)
# ---------------------------------------------------------
class SupplyChainDashboard:
    def __init__(self, df_import, df_stock):
        self.df_import = df_import
        self.df_stock = df_stock
        
        # 공통 부위 위주로 표시
        if df_stock is not None:
            self.items = list(set(df_import.columns) & set(df_stock.columns))
            self.items.sort()
        else:
            self.items = list(df_import.columns)
            
        self.current_item = self.items[0] if self.items else None

        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(15, 9), height_ratios=[1.5, 1], sharex=True)
        plt.subplots_adjust(left=0.20, bottom=0.1, right=0.9, hspace=0.15)

        if self.current_item:
            self.plot_analysis(self.current_item)
        
        ax_radio = plt.axes([0.02, 0.4, 0.15, 0.4], facecolor='#f8f9fa')
        self.radio = RadioButtons(ax_radio, self.items, active=0)
        self.radio.on_clicked(self.update)

        self.fig.suptitle("미국산 소고기 수급 분석 (Desktop Mode)", fontsize=18, fontweight='bold', y=0.98)
        plt.show()

    def plot_analysis(self, item):
        self.ax1.clear()
        self.ax2.clear()
        
        imp = self.df_import[item].rename('Import')
        
        if self.df_stock is not None and item in self.df_stock.columns:
            stk = self.df_stock[item].rename('Stock')
            combined = pd.concat([imp, stk], axis=1).dropna()
            
            # 차트1: 수입량(Bar) vs 재고량(Line)
            ax1_dup = self.ax1.twinx()
            self.ax1.bar(combined.index, combined['Import'], color='#AED6F1', label='수입량(Flow)', width=20, alpha=0.7)
            ax1_dup.plot(combined.index, combined['Stock'], color='#E74C3C', linewidth=2.5, marker='o', label='재고량(Stock)')
            ax1_dup.fill_between(combined.index, combined['Stock'], color='#E74C3C', alpha=0.1)
            
            self.ax1.set_ylabel('수입량 (kg)', color='#2E86C1', fontweight='bold')
            ax1_dup.set_ylabel('재고량 (Ton)', color='#C0392B', fontweight='bold')
            self.ax1.set_title(f'[{item}] 수입량과 재고량의 상관관계', fontsize=14, fontweight='bold')
            
            lines, labels = self.ax1.get_legend_handles_labels()
            lines2, labels2 = ax1_dup.get_legend_handles_labels()
            ax1_dup.legend(lines + lines2, labels + labels2, loc='upper left')

            # 차트2: 재고 월수 (재고/3개월평균수입)
            avg_imp = combined['Import'].rolling(3).mean().replace(0, 1)
            combined['Months'] = combined['Stock'] / avg_imp
            combined['Months'] = combined['Months'].clip(upper=20) # 이상치 제한

            self.ax2.plot(combined.index, combined['Months'], color='green', linewidth=2)
            self.ax2.axhline(2.0, color='gray', linestyle='--')
            
            self.ax2.fill_between(combined.index, combined['Months'], 4.0, where=(combined['Months']>=4), color='red', alpha=0.3)
            self.ax2.fill_between(combined.index, combined['Months'], 1.0, where=(combined['Months']<=1), color='orange', alpha=0.3)
            
            self.ax2.set_ylabel('재고 월수 (개월)')
            self.ax2.set_ylim(0, 10)
            
            curr = combined.iloc[-1]
            status = "[과잉]" if curr['Months'] >= 4 else "[부족]" if curr['Months'] <= 1.5 else "[안정]"
            info = f"재고월수: {curr['Months']:.1f}개월\n상태: {status}"
            self.ax1.text(1.15, 0.5, info, transform=self.ax1.transAxes, bbox=dict(boxstyle="round", fc="white"))
            
        else:
            self.ax1.bar(imp.index, imp, color='#AED6F1')
            self.ax1.set_title(f"[{item}] 수입량 데이터 (재고 정보 없음)")

        self.ax1.grid(True, alpha=0.3)
        self.ax2.grid(True, alpha=0.3)
        self.ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    def update(self, label):
        self.plot_analysis(label)
        self.fig.canvas.draw_idle()

if __name__ == "__main__":
    imp_data, stk_data = load_integrated_data()
    if imp_data is not None:
        SupplyChainDashboard(imp_data, stk_data)