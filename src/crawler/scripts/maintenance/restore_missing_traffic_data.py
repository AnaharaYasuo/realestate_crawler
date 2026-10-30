import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from django.apps import apps
from django.db import transaction
from django.db.models import Q
from package.utils.db_safety import assert_production_db_safety

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def get_all_target_property_models() -> list:
    """全アプリケーションから traffic フィールドおよび交通系フィールドを持つ物件モデルを動的抽出"""
    target_models = []
    for model in apps.get_models():
        if getattr(model._meta, "abstract", False):
            continue
        field_names = {f.name for f in model._meta.fields}
        # traffic があり、かつ駅情報・沿線フィールドを持つ物件モデル
        has_traffic = "traffic" in field_names
        has_station = any(
            f"station{i}" in field_names or f"railway{i}" in field_names
            for i in range(1, 6)
        )
        if has_traffic and has_station:
            target_models.append(model)
    return sorted(target_models, key=lambda m: m._meta.db_table)


def synthesize_traffic_str(item) -> str:
    """station / railway / bus 等の個別カラムから交通文字列を合成 (Route 1〜5対応)"""
    parts = []

    # 鉄道ルート 1〜5
    for i in range(1, 6):
        r = str(getattr(item, f"railway{i}", "") or "").strip()
        s = str(getattr(item, f"station{i}", "") or "").strip()
        m = getattr(item, f"railwayWalkMinute{i}", None)
        m_str = str(getattr(item, f"railwayWalkMinute{i}Str", "") or "").strip()

        if r or s:
            elem = f"{r} {s}".strip()
            if m is not None and m > 0:
                elem += f" 徒歩{m}分"
            elif m_str:
                if not m_str.startswith("徒歩"):
                    elem += f" {m_str}"
                else:
                    elem += f" {m_str}"
            if elem and elem not in parts:
                parts.append(elem)

    # バス停ルート 1〜5
    for i in range(1, 6):
        b_station = str(getattr(item, f"busStation{i}", "") or "").strip()
        b_min = getattr(item, f"busWalkMinute{i}", None)
        b_min_str = str(getattr(item, f"busWalkMinute{i}Str", "") or "").strip()
        if b_station:
            b_elem = f"バス停 {b_station}"
            if b_min is not None and b_min > 0:
                b_elem += f" 徒歩{b_min}分"
            elif b_min_str:
                b_elem += f" {b_min_str}"
            if b_elem and b_elem not in parts:
                parts.append(b_elem)

    return " / ".join(parts).strip()


def restore_traffic_from_existing_fields(
    dry_run: bool = True, models: list | None = None
) -> dict[str, int]:
    """すでに駅情報が存在するが traffic カラムが空のレコードを安全に包括復旧"""
    if not dry_run:
        assert_production_db_safety("restore_traffic")

    target_models = models if models is not None else get_all_target_property_models()
    results = {}

    logger.info(f"Target property models count: {len(target_models)}")

    failed_tables = []
    for model in target_models:
        table = model._meta.db_table
        field_names = {f.name for f in model._meta.fields}

        # traffic が空文字 / None / - / nan
        q_empty_traffic = Q(traffic__in=["", "-", "None", "nan"]) | Q(
            traffic__isnull=True
        )

        # 交通系フィールド（station1〜5, railway1〜5, busStation1〜5）が存在するレコード
        q_has_station = Q()
        for i in range(1, 6):
            if f"station{i}" in field_names:
                q_has_station |= ~Q(
                    **{f"station{i}__in": ["", "-", "None", "nan"]}
                ) & Q(**{f"station{i}__isnull": False})
            if f"railway{i}" in field_names:
                q_has_station |= ~Q(
                    **{f"railway{i}__in": ["", "-", "None", "nan"]}
                ) & Q(**{f"railway{i}__isnull": False})
            if f"busStation{i}" in field_names:
                q_has_station |= ~Q(
                    **{f"busStation{i}__in": ["", "-", "None", "nan"]}
                ) & Q(**{f"busStation{i}__isnull": False})

        needed_fields = [model._meta.pk.name, "traffic"]
        for i in range(1, 6):
            for f_prefix in [
                "railway",
                "station",
                "railwayWalkMinute",
                "busStation",
                "busWalkMinute",
            ]:
                fname = f"{f_prefix}{i}"
                if fname in field_names:
                    needed_fields.append(fname)
                fname_str = f"{f_prefix}{i}Str"
                if fname_str in field_names:
                    needed_fields.append(fname_str)

        try:
            qs = model.objects.filter(q_empty_traffic & q_has_station).only(*needed_fields)
            count = qs.count()
            results[table] = count

            if count > 0:
                logger.info(
                    f"[{table}] Target records with empty traffic but valid station: {count}"
                )
            else:
                logger.debug(f"[{table}] No missing traffic records.")

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
        except Exception as e:
            logger.exception(f"[{table}] Error restoring traffic data: {e}")
            failed_tables.append((table, str(e)))

    if failed_tables:
        raise RuntimeError(
            f"Traffic restoration encountered errors on {len(failed_tables)} tables: {failed_tables}"
        )

    return results


if __name__ == "__main__":
    dry_run = "--execute" not in sys.argv
    if dry_run:
        logger.info("Running in DRY-RUN mode. Use --execute to apply changes.")
    restore_traffic_from_existing_fields(dry_run=dry_run)
