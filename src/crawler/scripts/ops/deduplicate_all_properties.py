"""
全物件テーブルの重複pageUrlクレンジングスクリプト
同一pageUrlのレコードが存在する場合、最新のidを1件残して古いレコードを削除する。
"""
import os
import sys
import logging
from django.db import connection, transaction

# Django初期化
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import setup_env  # noqa: F401
from scripts.ops.run_bulk_ml_evaluation import get_all_property_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def deduplicate_property_table(model_class) -> int:
    """単一モデルテーブルの重複pageUrlレコードを削除する（最新のidのみ保持）"""
    table_name = model_class._meta.db_table
    logger.info("Cleaning duplicates for table: %s (%s)...", table_name, model_class.__name__)
    
    # pageUrl ごとに最大の id 以外の id を抽出して一括削除
    sql_find_dups = f"""
        SELECT id FROM {table_name}
        WHERE id NOT IN (
            SELECT max_id FROM (
                SELECT MAX(id) AS max_id
                FROM {table_name}
                GROUP BY pageUrl
            ) AS latest_ids
        )
    """
    with connection.cursor() as cursor:
        cursor.execute(sql_find_dups)
        dup_ids = [row[0] for row in cursor.fetchall()]
        
        if not dup_ids:
            logger.info("  No duplicates found for %s.", table_name)
            return 0
        
        logger.info("  Found %d duplicate rows to remove in %s.", len(dup_ids), table_name)
        
        # チャンクごとに安全に削除
        chunk_size = 1000
        total_deleted = 0
        for i in range(0, len(dup_ids), chunk_size):
            chunk = dup_ids[i:i + chunk_size]
            format_strings = ','.join(['%s'] * len(chunk))
            cursor.execute(f"DELETE FROM {table_name} WHERE id IN ({format_strings})", chunk)
            total_deleted += len(chunk)
            
        logger.info("  Successfully deleted %d duplicate rows from %s.", total_deleted, table_name)
        return total_deleted


def run_all_deduplications() -> int:
    """全モデルテーブルの重複を削除する"""
    models = get_all_property_models(skip_portals=False)
    logger.info("Starting deduplication for %d models...", len(models))
    total_removed = 0
    with transaction.atomic():
        for m in models:
            total_removed += deduplicate_property_table(m)
    logger.info("Deduplication completed. Total duplicate rows removed: %d", total_removed)
    return total_removed


if __name__ == "__main__":
    run_all_deduplications()
