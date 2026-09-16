# -*- coding: utf-8 -*-
import os
import sys
import logging

# Django環境のロード
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from package.models.evaluation import LandPricePotential

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_estimated_prices():
    """
    既存のすべての公示地価マスタデータに対して、
    相続税路線価 (80%) と固定資産税評価額 (70%) を自動算出してアップデートする。
    """
    logging.info("Starting batch calculation for estimated Rosenka and Fixed Asset prices...")
    
    qs = LandPricePotential.objects.all()
    count = qs.count()
    logging.info(f"Found {count} records in LandPricePotential.")
    
    updated_count = 0
    for lp in qs:
        avg_price = lp.average_land_price
        
        # 鑑定割合を適用
        lp.estimated_rosenka_price = int(avg_price * 0.8)
        lp.estimated_fixed_asset_price = int(avg_price * 0.7)
        lp.save()
        
        updated_count += 1
        if updated_count % 100 == 0:
            logging.info(f"Processed {updated_count}/{count} records...")
            
    logging.info(f"Batch calculation completed. Updated {updated_count} records.")

if __name__ == "__main__":
    calculate_estimated_prices()
