# -*- coding: utf-8 -*-
import os
import sys
import requests
import logging
from collections import defaultdict

# Django環境のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.models.evaluation import LandPricePotential

# 国土交通省 不動産取引価格情報取得APIエンドポイント
MLIT_API_URL = "https://www.land.mlit.go.jp/webland/api/TradeListSearch"

def sync_land_prices_from_mlit(pref_code="13", year_quarter="20241", json_path=None):
    """
    国土交通省の取引価格情報APIまたはローカルJSONからデータを取得し、市区町村別の平均地価マスタを動的に構築・同期する。
    """
    trade_list = []
    try:
        if json_path:
            import json
            logging.info(f"Loading real estate trade data from local JSON file: {json_path}...")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                trade_list = data.get("data", [])
        else:
            logging.info(f"Fetching real estate trade data from MLIT API for prefecture={pref_code}, quarter={year_quarter}...")
            params = {
                "from": year_quarter,
                "to": year_quarter,
                "area": pref_code
            }
            response = requests.get(MLIT_API_URL, params=params, timeout=45)
            if response.status_code != 200:
                logging.error(f"MLIT API returned HTTP status {response.status_code}")
                return False
            data = response.json()
            trade_list = data.get("data", [])
            
        if not trade_list:
            logging.warning("No trade data returned.")
            return False
            
        logging.info(f"Successfully loaded {len(trade_list)} trade records. Commencing aggregation...")
        
        # 市区町村×用途区分ごとの (平米単価の合計, レコード数) を集計
        # key: (prefecture, city, land_use)
        stats = defaultdict(lambda: [0.0, 0])
        
        pref_name_map = {
            "11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県", "23": "愛知県"
        }
        pref_name = pref_name_map.get(pref_code, "東京都")
        
        for trade in trade_list:
            # 市区町村
            city = trade.get("City", "").strip()
            if not city:
                continue
                
            # 用途区分 (住宅地 / 商業地)
            raw_use = trade.get("Use", "")
            if "住宅" in raw_use:
                land_use = "residential"
            elif "商業" in raw_use or "店舗" in raw_use or "事務所" in raw_use:
                land_use = "commercial"
            else:
                continue
                
            # 取引価格
            price_str = trade.get("TradePrice", "0")
            # 面積
            area_str = trade.get("Area", "0")
            
            try:
                price = float(price_str)
                # 面積に「㎡」等の文字が含まれる場合があるため、数値部分のみ抽出
                import re
                area_match = re.search(r'([0-9\.]+)', str(area_str))
                if not area_match:
                    continue
                area = float(area_match.group(1))
                if area <= 0:
                    continue
                    
                # 平米単価 (円/㎡)
                unit_price = price / area
                
                # 異常値の除外（極端な単価は集計バグや特殊取引のため除外）
                if unit_price < 10000 or unit_price > 10000000:
                    continue
                    
                key = (pref_name, city, land_use)
                stats[key][0] += unit_price
                stats[key][1] += 1
            except Exception as e:
                # パースエラーは無視して続行
                continue
                
        # データベースにマスタとして保存・洗い替え
        saved_count = 0
        for (pref, city_name, use), (total_unit_price, count) in stats.items():
            if count == 0:
                continue
            
            # 平均平米単価の算出
            avg_unit_price = int(total_unit_price / count)
            
            # 8割を路線価、7割を固定資産税評価額として推定
            rosenka = int(avg_unit_price * 0.8)
            fixed_asset = int(avg_unit_price * 0.7)
            
            # update_or_create でマスタに同期
            obj, created = LandPricePotential.objects.update_or_create(
                prefecture=pref,
                city=city_name,
                land_use=use,
                defaults={
                    "average_land_price": avg_unit_price,
                    "estimated_rosenka_price": rosenka,
                    "estimated_fixed_asset_price": fixed_asset
                }
            )
            saved_count += 1
            
        print(f"MLIT API Sync: Successfully updated {saved_count} municipality land price records in database.")
        return True
        
    except Exception as e:
        logging.error(f"Failed to sync land prices from MLIT API: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # デフォルトで東京都 (13) の直近データを取得
    # 国交省のAPIは前四半期のデータを取得可能。ここでは "20241" (2024年第1四半期) などを基準にする
    import argparse
    parser = argparse.ArgumentParser(description="Sync land prices from MLIT API.")
    parser.add_argument("--area", default="13", help="Prefecture code (e.g., 13 for Tokyo, 14 for Kanagawa)")
    parser.add_argument("--quarter", default="20241", help="Year and Quarter (e.g., 20241)")
    parser.add_argument("--json", default=None, help="Path to local MLIT JSON file")
    args = parser.parse_args()
    
    sync_land_prices_from_mlit(pref_code=args.area, year_quarter=args.quarter, json_path=args.json)
