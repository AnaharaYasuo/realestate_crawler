import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from django.apps import apps
from django.db import transaction
from package.utils.converter import parse_chikunengetsu
from package.utils.db_safety import assert_production_db_safety

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def get_all_target_chikunengetsu_models() -> list:
    """chikunengetsu および chikunengetsuStr フィールドを持つ全モデルを動的抽出"""
    target_models = []
    for model in apps.get_models():
        if getattr(model._meta, "abstract", False):
            continue
        field_names = {f.name for f in model._meta.fields}
        if "chikunengetsu" in field_names and "chikunengetsuStr" in field_names:
            target_models.append(model)
    return sorted(target_models, key=lambda m: m._meta.db_table)


def restore_chikunengetsu_from_existing_fields(
    dry_run: bool = True, models: list | None = None
) -> dict[str, int]:
    """chikunengetsuStr が存在するが chikunengetsu カラムが空のレコードを安全に復旧"""
    if not dry_run:
        assert_production_db_safety("restore_chikunengetsu")

    target_models = (
        models if models is not None else get_all_target_chikunengetsu_models()
    )
    results = {}

    logger.info(f"Target chikunengetsu models count: {len(target_models)}")

    failed_tables = []
    for model in target_models:
        table = model._meta.db_table
        needed_fields = [model._meta.pk.name, "chikunengetsu", "chikunengetsuStr"]

        try:
            qs = (
                model.objects.filter(chikunengetsu__isnull=True)
                .exclude(chikunengetsuStr__in=["", "-", "None", "nan", "不詳"])
                .only(*needed_fields)
            )
            count = qs.count()
            results[table] = count

            if count > 0:
                logger.info(
                    f"[{table}] Target records with empty chikunengetsu but valid string: {count}"
                )
            else:
                logger.debug(f"[{table}] No missing chikunengetsu records.")

            if count == 0 or dry_run:
                continue

            updated = 0
            batch_clean = []
            batch_date = []
            for item in qs.iterator(chunk_size=1000):
                c_str = str(getattr(item, "chikunengetsuStr", "") or "").strip()
                if "を表示" in c_str or c_str in ("築年月", "不詳", "-"):
                    item.chikunengetsuStr = "" if c_str != "不詳" else "不詳"
                    item.chikunengetsu = None
                    batch_clean.append(item)
                    if len(batch_clean) >= 500:
                        with transaction.atomic():
                            model.objects.bulk_update(
                                batch_clean, ["chikunengetsuStr", "chikunengetsu"]
                            )
                        updated += len(batch_clean)
                        batch_clean = []
                else:
                    parsed_date = parse_chikunengetsu(c_str)
                    if parsed_date:
                        item.chikunengetsu = parsed_date
                        batch_date.append(item)
                        if len(batch_date) >= 500:
                            with transaction.atomic():
                                model.objects.bulk_update(
                                    batch_date, ["chikunengetsu"]
                                )
                            updated += len(batch_date)
                            batch_date = []
            if batch_clean:
                with transaction.atomic():
                    model.objects.bulk_update(
                        batch_clean, ["chikunengetsuStr", "chikunengetsu"]
                    )
                updated += len(batch_clean)
            if batch_date:
                with transaction.atomic():
                    model.objects.bulk_update(batch_date, ["chikunengetsu"])
                updated += len(batch_date)
            logger.info(f"[{table}] Successfully processed/restored {updated} records.")
        except Exception as e:
            logger.exception(f"[{table}] Error restoring chikunengetsu data: {e}")
            failed_tables.append((table, str(e)))

    if failed_tables:
        raise RuntimeError(
            f"Chikunengetsu restoration encountered errors on {len(failed_tables)} tables: {failed_tables}"
        )

    return results


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    if dry_run:
        logger.info("Running in DRY-RUN mode. Use --execute to apply changes.")
    restore_chikunengetsu_from_existing_fields(dry_run=dry_run)
