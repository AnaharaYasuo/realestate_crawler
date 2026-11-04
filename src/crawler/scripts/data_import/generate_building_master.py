# -*- coding: utf-8 -*-
"""
既存クロール物件データからの建物棟マスタ（BuildingMaster）自動抽出・集約インポート
(scripts/data_import/generate_building_master.py)

クロール済みの各ポータル（三井、住友、東急、野村、大京、長谷工、みずほ等）の分譲マンション・一棟アパート
データから、正規化された建物名・住所・建築年・構造・総戸数・階数を棟単位で集約（GroupBy）し、
DB（BuildingMaster）に一括登録・洗い替え（upsert）します。
"""
import logging
import os
import sys
from collections import defaultdict
from django.apps import apps

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from django.db import connection
from package.models.building_master import BuildingMaster

logger = logging.getLogger(__name__)

TARGET_MODELS = [
    "MitsuiMansion", "SumifuMansion", "TokyuMansion", "NomuraMansion",
    "DaikyoMansion", "HasekoMansion", "MizuhoMansion", "TotateMansion",
    "DaiwaMansion", "SumirinMansion", "AthomeMansion", "HomesMansion",
    "MitsuiInvestmentApartment", "SumifuInvestmentApartment",
    "TokyuInvestmentApartment", "NomuraInvestmentApartment"
]


def generate_and_sync_building_master(chunk_limit_per_model: int = 2000) -> int:
    """
    対象ポータルモデルから建物名および住所をキーとして棟単位に集約し、BuildingMaster に登録する。
    """
    logger.info("Starting aggregation of BuildingMaster from crawled properties...")
    
    unique_buildings = {}

    for m_name in TARGET_MODELS:
        try:
            model = apps.get_model("package", m_name)
        except LookupError:
            continue

        fields = [f.name for f in model._meta.get_fields()]
        name_field = "propertyName" if "propertyName" in fields else "name"
        addr_field = "address" if "address" in fields else None
        
        if not addr_field or name_field not in fields:
            continue

        req_fields = [name_field, addr_field]
        if "chikunengetsu" in fields:
            req_fields.append("chikunengetsu")
        if "kouzou" in fields:
            req_fields.append("kouzou")
        if "soukosu" in fields:
            req_fields.append("soukosu")

        logger.info("Scanning %s for unique buildings...", m_name)
        qs = (
            model.objects.exclude(**{f"{name_field}__isnull": True})
            .exclude(**{name_field: ""})
            .values(*req_fields)[:chunk_limit_per_model]
        )

        for item in qs:
            raw_name = str(item.get(name_field) or "").strip()
            raw_addr = str(item.get(addr_field) or "").strip()
            if not raw_name or not raw_addr:
                continue

            # 簡単な正規化（全角半角、余分なスペース除去）
            norm_name = raw_name.replace("　", " ").strip()
            norm_addr = raw_addr.replace("　", " ").strip()

            key = (norm_name, norm_addr)
            if key not in unique_buildings:
                built_date = item.get("chikunengetsu")
                byear = built_date.year if built_date else None
                bmonth = built_date.month if built_date else None
                
                unique_buildings[key] = {
                    "raw_name": raw_name,
                    "normalized_name": norm_name,
                    "raw_address": raw_addr,
                    "normalized_address": norm_addr,
                    "built_year": byear,
                    "built_month": bmonth,
                    "structure_type": str(item.get("kouzou") or "")[:20],
                    "total_units": int(item.get("soukosu") or 0) if item.get("soukosu") else None,
                }

    logger.info("Aggregated %d unique buildings. Bulk upserting into BuildingMaster...", len(unique_buildings))

    items = list(unique_buildings.values())
    chunk_size = 2000
    total_upserted = 0

    with connection.cursor() as cursor:
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            val_clauses = []
            params = []
            for b in chunk:
                val_clauses.append("(%s, %s, %s, %s, %s, %s, %s, %s, '', '', '', '', '', '', '', '', '', '', NOW(), NOW())")
                params.extend([
                    b["raw_name"],
                    b["normalized_name"],
                    b["raw_address"],
                    b["normalized_address"],
                    b["built_year"],
                    b["built_month"],
                    b["structure_type"],
                    b["total_units"],
                ])
            
            table_name = BuildingMaster._meta.db_table
            sql = f"""
                INSERT INTO {table_name} (
                    raw_name, normalized_name, raw_address, normalized_address,
                    built_year, built_month, structure_type, total_units,
                    developer_brand, developer_tier, contractor_name, contractor_tier,
                    earthquake_resistance, hallway_type, management_company,
                    management_type, manager_working_style, shared_facilities_json,
                    created_at, updated_at
                )
                VALUES {','.join(val_clauses)}
                ON DUPLICATE KEY UPDATE
                    raw_name = VALUES(raw_name),
                    raw_address = VALUES(raw_address),
                    built_year = VALUES(built_year),
                    built_month = VALUES(built_month),
                    structure_type = VALUES(structure_type),
                    total_units = VALUES(total_units),
                    updated_at = NOW();
            """
            cursor.execute(sql, params)
            total_upserted += len(chunk)
            logger.info("Upserted %d / %d buildings...", total_upserted, len(items))

    total = BuildingMaster.objects.count()
    logger.info("✅ BuildingMaster sync complete: Total=%d (Upserted=%d)", total, total_upserted)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    generate_and_sync_building_master()
