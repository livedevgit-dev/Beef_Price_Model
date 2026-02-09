import os

def rename_my_files():
    # 현재 이 파이썬 파일이 실행되는 위치를 기준으로 잡습니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 변경할 파일들이 있는 폴더 (이 파일과 같은 위치에 있으므로 current_dir 사용)
    folder_path = current_dir
    
    name_map = {
        "01_crawl_imports.py": "crawl_imp_volume_monthly.py",
        "02_crawl_imports_web_daily.py": "crawl_imp_volume_daily.py",
        "05_crawl_stocks.py": "crawl_imp_stock_monthly.py",
        "06_crawl_prices.py": "crawl_imp_price_meatbox.py",
        "09_crawl_exchange_rate.py": "crawl_com_usd_krw.py",
        "10_crawl_meatbox_sise.py": "crawl_imp_price_history.py",
        "21_create_monthly_master.py": "proc_merge_master_data.py",
        "beef_analysis.py": "anal_price_prediction.py",
        "beef_dashboard.py": "viz_beef_dashboard.py",
        "data_collector.py": "crawl_han_auction_api.py"
    }

    print(f"현재 작업 폴더: {folder_path}")
    print("파일 이름 변경을 시작합니다...")

    for old_name, new_name in name_map.items():
        old_file = os.path.join(folder_path, old_name)
        new_file = os.path.join(folder_path, new_name)

        if os.path.exists(old_file):
            os.rename(old_file, new_file)
            print(f"[완료] 완료: {old_name} -> {new_name}")
        else:
            # 진단용: 파일이 왜 없는지 경로를 출력해봅니다.
            print(f"[없음] 없음: {old_name} (찾은 위치: {old_file})")

if __name__ == "__main__":
    rename_my_files()