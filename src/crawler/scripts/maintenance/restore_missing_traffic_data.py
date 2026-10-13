import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings
realestateSettings.configure()

from django.db import connection, transaction
from package.models.mitsui import MitsuiKodate, MitsuiMansion, MitsuiTochi
from package.models.daikyo import DaikyoKodate, DaikyoMansion, DaikyoTochi
from package.models.sumirin import SumirinKodate, SumirinMansion, SumirinTochi
from package.models.tokyu import TokyuKodate, TokyuMansion, TokyuTochi

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TARGET_MODELS = [
    MitsuiKodate, MitsuiMansion, MitsuiTochi,
    DaikyoKodate, DaikyoMansion, DaikyoTochi,
    SumirinKodate, SumirinMansion, SumirinTochi,
    TokyuKodate, TokyuMansion, TokyuTochi,
]

def synthesize_traffic_str(item) -> str:
    """station1 / railway1 等の個別カラムから交通文字列を合成"""
    parts = []
    r1 = str(getattr(item, "railway1", "") or "").strip()
    s1 = str(getattr(item, "station1", "") or "").strip()
    m1 = getattr(item, "railwayWalkMinute1", None)
    m1_str = str(getattr(item, "railwayWalkMinute1Str", "") or "").strip()

    if r1 or s1:
        elem = f"{r1} {s1}".strip()
        if m1 is not None and m1 > 0:
            elem += f" 徒歩{m1}分"
        elif m1_str:
            elem += f" {m1_str}"
        parts.append(elem)

    b_station = str(getattr(item, "busStation1", "") or "").strip()
    b_min = getattr(item, "busWalkMinute1", None)
    if b_station:
        b_elem = f"バス停 {b_station}"
        if b_min is not None and b_min > 0:
            b_elem += f" 徒歩{b_min}分"
        parts.append(b_elem)

    return " / ".join(parts).strip()

def restore_traffic_from_existing_fields(dry_run: bool = True) -> dict[str, int]:
    """すでに駅情報が存在するが traffic カラムが空のレコードを安全に復旧"""
    results = {}
    for model in TARGET_MODELS:
        table = model._meta.db_table
        # traffic が空で、station1 または railway1 が存在するレコードを抽出
        qs = model.objects.filter(
            traffic__in=["", "-", "None", "nan"]
        ).exclude(station1__in=["", "-", "None", "nan"])

        count = qs.count()
        results[table] = count
        logger.info(f"[{table}] Target records with empty traffic but valid station: {count}")

        if count == 0 or dry_run:
            continue

        updated = 0
        batch = []
        for item in qs.iterator(chunk_size=1000):
            syn_traffic = synthesize_traffic_str(item)
            if syn_traffic:
                item.traffic = syn_traffic
                batch.append(item)
                if len(batch) >= 500:
                    with transaction.atomic():
                        model.objects.bulk_update(batch, ["traffic"])
                    updated += len(batch)
                    batch = []
        if batch:
            with transaction.atomic():
                model.objects.bulk_update(batch, ["traffic"])
            updated += len(batch)
        logger.info(f"[{table}] Successfully restored {updated} records.")

    return results

if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    if dry_run:
        logger.info("Running in DRY-RUN mode. Use --execute to apply changes.")
    restore_traffic_from_existing_fields(dry_run=dry_run)
