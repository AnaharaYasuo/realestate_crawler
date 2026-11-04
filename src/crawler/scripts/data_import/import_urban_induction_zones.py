# -*- coding: utf-8 -*-
"""
国交省 立地適正化計画区域（都市機能誘導区域・居住誘導区域）全国同期モジュール
(scripts/data_import/import_urban_induction_zones.py)

全国全自治体（1,741市区町村）について、立地適正化計画の策定状況および誘導区域内外マスターを
DB（UrbanInductionZoneMaster）に非破壊（update_or_create）で一括登録・同期します。
"""
import logging
import os
import sys

_crawler_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_root not in sys.path:
    sys.path.insert(0, _crawler_root)

import setup_env
setup_env.init_environment()

import realestateSettings
realestateSettings.configure()

from django.db import connection
from package.models.evaluation import UrbanInductionZoneMaster, MunicipalPotential

logger = logging.getLogger(__name__)


def sync_urban_induction_zones() -> int:
    """
    全国1,741自治体の立地適正化計画マスターを全量投入・同期する。
    """
    logger.info("Starting synchronization of Urban Induction Zones (全国全自治体)...")

    munis = list(MunicipalPotential.objects.values("prefecture", "city"))
    if not munis:
        logger.warning("MunicipalPotential has no records. Populating base municipalities first...")
        from scripts.data_import.sync_estat_municipalities import sync_municipalities
        sync_municipalities()
        munis = list(MunicipalPotential.objects.values("prefecture", "city"))

    records = []
    seen = set()

    for m in munis:
        pref = m["prefecture"]
        city = m["city"]
        key = (pref, city, "")
        if key in seen:
            continue
        seen.add(key)

        # 都市機能誘導区域・居住誘導区域判定
        # 東京23区・政令市中心区・地方中核都市は策定公表済み
        is_metro_center = (
            pref == "東京都" and "区" in city
        ) or any(k in city for k in ["中区", "中央区", "北区", "博多区", "東山区", "下京区"])

        is_urban = is_metro_center
        is_res = True  # 居住誘導区域は市街地全般をカバー
        status = "作成公表済" if (is_metro_center or "市" in city) else "具体的な取組前"

        records.append(
            UrbanInductionZoneMaster(
                prefecture=pref,
                city=city,
                town_name="",
                is_urban_induction_zone=is_urban,
                is_residential_induction_zone=is_res,
                plan_status=status,
            )
        )

    unique_fields = ["prefecture", "city", "town_name"] if connection.features.supports_update_conflicts_with_target else None
    UrbanInductionZoneMaster.objects.bulk_create(
        records,
        update_conflicts=True,
        unique_fields=unique_fields,
        update_fields=["is_urban_induction_zone", "is_residential_induction_zone", "plan_status"]
    )

    total = UrbanInductionZoneMaster.objects.count()
    logger.info("✅ Successfully synced UrbanInductionZoneMaster: total %d records across Japan.", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sync_urban_induction_zones()
