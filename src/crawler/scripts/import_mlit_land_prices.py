# -*- coding: utf-8 -*-
import os
import sys
import csv
import logging
import argparse

# Django環境のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.models.evaluation import LandPricePotential

def generate_sample_land_price_csv(filepath):
    """
    テスト用の公示地価サンプルCSVを生成する。
    """
    logging.info(f"Generating sample MLIT land price CSV at: {filepath}")
    
    # 都道府県, 市区町村, 平均地価(円/㎡), 用途区分('residential' or 'commercial')
    sample_data = [
        # 千代田区
        ["東京都", "千代田区", "2500000", "residential"],
        ["東京都", "千代田区", "5500000", "commercial"],
        # 港区
        ["東京都", "港区", "1900000", "residential"],
        ["東京都", "港区", "4200000", "commercial"],
        # 渋谷区
        ["東京都", "渋谷区", "1500000", "residential"],
        ["東京都", "渋谷区", "3800000", "commercial"],
        # 中央区
        ["東京都", "中央区", "1400000", "residential"],
        ["東京都", "中央区", "3300000", "commercial"],
        # 世田谷区
        ["東京都", "世田谷区", "680000", "residential"],
        ["東京都", "世田谷区", "1200000", "commercial"],
        # 新宿区
        ["東京都", "新宿区", "850000", "residential"],
        ["東京都", "新宿区", "2800000", "commercial"],
        # 足立区
        ["東京都", "足立区", "310000", "residential"],
        ["東京都", "足立区", "550000", "commercial"],
        # 愛知県名古屋市中区 (住友不動産等の検証エリア用)
        ["愛知県", "名古屋市中区", "450000", "residential"],
        ["愛知県", "名古屋市中区", "1800000", "commercial"],
        ["愛知県", "名古屋市東区", "380000", "residential"],
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["prefecture", "city", "average_land_price", "land_use"]) # ヘッダー
        writer.writerows(sample_data)


def import_land_prices(csv_path):
    """
    地価公示CSVを読み込み、平均地価テーブルに同期（洗い替え）する。
    """
    if not os.path.exists(csv_path):
        logging.error(f"CSV file not found: {csv_path}")
        return False
        
    logging.info(f"Importing average land price data from CSV: {csv_path}...")
    
    processed = 0
    created_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pref = row.get("prefecture", "").strip()
            city = row.get("city", "").strip()
            price_str = row.get("average_land_price", "0").strip()
            use = row.get("land_use", "").strip()
            growth_str = row.get("land_price_growth_rate", "0.0").strip()
            
            if not pref or not city or use not in ['residential', 'commercial']:
                continue
                
            try:
                price = int(price_str)
            except ValueError:
                price = 0
                
            try:
                from decimal import Decimal
                growth = Decimal(growth_str)
            except:
                growth = Decimal("0.0")
                
            # 重複時は update_or_create で最新値に洗い替える
            obj, created = LandPricePotential.objects.update_or_create(
                prefecture=pref,
                city=city,
                land_use=use,
                defaults={
                    "average_land_price": price,
                    "estimated_rosenka_price": int(price * 0.8),
                    "estimated_fixed_asset_price": int(price * 0.7),
                    "land_price_growth_rate": growth
                }
            )
            processed += 1
            if created:
                created_count += 1
                
    print(f"MLIT Land Price Import: Processed {processed} records (Created {created_count} new).")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    parser = argparse.ArgumentParser(description="Import land prices from MLIT CSV.")
    parser.add_argument("--csv", help="Path to the land price CSV file.")
    args = parser.parse_args()
    
    csv_file = args.csv
    if not csv_file:
        csv_file = "/app/src/crawler/package/ml/data/mlit_land_prices_kanto.csv"
        
    try:
        import_land_prices(csv_file)
    except Exception as e:
        logging.error(f"Failed to import land prices: {e}")
