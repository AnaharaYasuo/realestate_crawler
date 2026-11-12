"""
Issue #1379: 全サイト（全物件種別・全テーブル）の未パース・過去バス利用物件データクレンジングバッチ
traffic に「バス」が含まれるが busUse1 が未設定または駅徒歩分数と混同されているレコードに対し、
最新パーサーの _populateTraffic を適用して安全に再パース・更新する。
"""
import argparse
import importlib
import logging
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT_DIR)
import realestateSettings

realestateSettings.configure()
import django

django.setup()

from django.apps import apps
from django.db import transaction
from package.site_registry import SiteRegistry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INVESTMENT_TABLE_MAP = {
    "athome_investment_apartment": ("athome", "AthomeInvestmentApartmentParser"),
    "homes_investment_apartment": ("homes", "HomesInvestmentApartmentParser"),
    "kenbiya_investment_apartment": ("kenbiya", "KenbiyaInvestmentApartmentParser"),
    "kenbiya_investment_building": ("kenbiya", "KenbiyaInvestmentBuildingParser"),
    "misawa_investment_apartment": ("misawa", "MisawaInvestmentApartmentParser"),
    "misawa_investment_kodate": ("misawa", "MisawaInvestmentKodateParser"),
    "mitsui_investment_apartment": ("mitsui", "MitsuiInvestmentApartmentParser"),
    "mitsui_investment_kodate": ("mitsui", "MitsuiInvestmentKodateParser"),
    "nomura_investment_apartment": ("nomura", "NomuraInvestmentApartmentParser"),
    "nomura_investment_kodate": ("nomura", "NomuraInvestmentKodateParser"),
    "sumifu_investment_apartment": ("sumifu", "SumifuInvestmentApartmentParser"),
    "sumifu_investment_kodate": ("sumifu", "SumifuInvestmentKodateParser"),
    "tokyu_investment_apartment": ("tokyu", "TokyuInvestmentApartmentParser"),
    "tokyu_investment_kodate": ("tokyu", "TokyuInvestmentKodateParser"),
}


def build_table_to_parser_map() -> dict[str, type]:
    """SiteRegistry から全物件テーブルに対応するパーサークラスを完全自動構築する"""
    configs = SiteRegistry.get_all_sites()
    table_to_parser: dict[str, type] = {}

    for comp, sdef in configs.items():
        try:
            mod = importlib.import_module(sdef.parser_module)
            for ptype in sdef.property_types:
                ptype_cap = ptype.capitalize()
                candidates = [
                    f"{comp.capitalize()}{ptype_cap}Parser",
                    f"{comp.upper()}{ptype_cap}Parser",
                    f"{comp.capitalize()}{ptype}Parser",
                ]
                matched_cls = None
                for cand in candidates:
                    if hasattr(mod, cand):
                        matched_cls = getattr(mod, cand)
                        break
                if not matched_cls:
                    for attr in dir(mod):
                        if ptype.lower() in attr.lower() and "parser" in attr.lower():
                            cls = getattr(mod, attr)
                            if isinstance(cls, type):
                                matched_cls = cls
                                break
                if matched_cls:
                    table_name = f"{comp}_{ptype}"
                    if comp in ("ietan", "haseko", "adcast", "toho"):
                        table_name = f"crawled_{comp}_{ptype}"
                    table_to_parser[table_name] = matched_cls
        except Exception as e:
            logger.warning(f"Error building parser for company {comp}: {e}")

    for tbl, (comp, pcls_name) in INVESTMENT_TABLE_MAP.items():
        sdef = configs.get(comp)
        if sdef:
            try:
                mod = importlib.import_module(sdef.parser_module)
                if hasattr(mod, pcls_name):
                    table_to_parser[tbl] = getattr(mod, pcls_name)
            except Exception as e:
                logger.warning(f"Error loading investment parser {pcls_name}: {e}")

    return table_to_parser


def cleanse_kenbiya_boilerplate(dry_run: bool = True):
    """健美家モデルのシステム定型文（注記ノイズ）を空文字にクレンジングする"""
    logger.info("Cleaning Kenbiya boilerplate text...")
    models = apps.get_models()
    cleansed = 0
    boilerplate_marker = "最寄の沿線駅名及び駅までの徒歩分数または距離を表示"
    for m in models:
        tbl = m._meta.db_table
        if "kenbiya" not in tbl or not hasattr(m, "traffic"):
            continue
        qs = m.objects.filter(traffic__icontains=boilerplate_marker)
        cnt = qs.count()
        if cnt > 0:
            logger.info(f"Kenbiya table [{tbl}]: {cnt} boilerplate records found.")
            if not dry_run:
                # Update in chunks
                qs.update(traffic="")
            cleansed += cnt
    logger.info(f"Kenbiya boilerplate cleansing done: {cleansed} records updated (dry_run={dry_run}).")
    return cleansed


def cleanse_bus_records(target_table: str | None = None, dry_run: bool = True, limit: int = 0):
    table_to_parser = build_table_to_parser_map()
    models = apps.get_models()
    total_checked = 0
    total_updated = 0
    processed_tables = 0

    if not target_table or "kenbiya" in target_table:
        cleanse_kenbiya_boilerplate(dry_run=dry_run)

    for model in models:
        tbl_name = model._meta.db_table
        if target_table and tbl_name != target_table:
            continue
        if tbl_name not in table_to_parser:
            continue
        if not hasattr(model, "busUse1") or not hasattr(model, "traffic"):
            continue

        processed_tables += 1
        parser_cls = table_to_parser[tbl_name]
        parser = parser_cls()

        # traffic に「バス」を含むが、busUse1 が未設定または 0 のレコードを抽出
        qs = model.objects.filter(traffic__icontains="バス").filter(
            django.db.models.Q(busUse1__isnull=True) | django.db.models.Q(busUse1=0)
        )
        count = qs.count()
        if count == 0:
            continue

        logger.info(f"Target table [{tbl_name}]: {count} records need check.")
        table_updated = 0

        # チャンクごとに処理して安全にバッチ更新
        batch_size = 500
        records_to_process = qs[:limit] if limit > 0 else qs
        
        # IDリストを取得して個別更新
        ids = list(records_to_process.values_list("id", flat=True))
        logger.info(f"[{tbl_name}] Processing {len(ids)} items...")

        for i in range(0, len(ids), batch_size):
            chunk_ids = ids[i : i + batch_size]
            items = list(model.objects.filter(id__in=chunk_ids))
            items_to_save = []

            for item in items:
                total_checked += 1
                old_bus_use = getattr(item, "busUse1", None)
                old_bus_min = getattr(item, "busWalkMinute1", None)
                old_bus_stop = getattr(item, "busStation1", None)
                old_rail_min = getattr(item, "railwayWalkMinute1", None)

                parser._populateTraffic(item, item.traffic)
                if hasattr(parser, "clean_parsed_item"):
                    parser.clean_parsed_item(item)

                new_bus_use = getattr(item, "busUse1", None)
                new_bus_min = getattr(item, "busWalkMinute1", None)
                new_bus_stop = getattr(item, "busStation1", None)
                new_rail_min = getattr(item, "railwayWalkMinute1", None)

                if (
                    new_bus_use != old_bus_use
                    or new_bus_min != old_bus_min
                    or new_bus_stop != old_bus_stop
                    or new_rail_min != old_rail_min
                ):
                    table_updated += 1
                    total_updated += 1
                    items_to_save.append(item)
                    if table_updated <= 2 or table_updated % 500 == 0:
                        logger.info(
                            f"[{tbl_name}] ID={item.id} -> R1={item.railway1}, S1={item.station1}, "
                            f"BusUse={item.busUse1}, BusMin={item.busWalkMinute1}, BusStop={item.busStation1}, Walk={item.railwayWalkMinute1}"
                        )

            if items_to_save and not dry_run:
                with transaction.atomic():
                    for item in items_to_save:
                        item.save(update_fields=[
                            "railway1", "station1", "railwayWalkMinute1", "railwayWalkMinute1Str",
                            "busUse1", "busWalkMinute1", "busWalkMinute1Str", "busStation1"
                        ])

        logger.info(f"[{tbl_name}] Checked: {len(ids)}, Updated: {table_updated} (dry_run={dry_run})")

    logger.info(
        f"Summary: processed_tables={processed_tables}, total_checked={total_checked}, "
        f"total_updated={total_updated}, dry_run={dry_run}"
    )
    return total_updated


if __name__ == "__main__":
    parser_arg = argparse.ArgumentParser()
    parser_arg.add_argument("--table", type=str, default=None, help="Specific table name")
    parser_arg.add_argument("--execute", action="store_true", help="Execute DB save (default is dry-run)")
    parser_arg.add_argument("--limit", type=int, default=0, help="Limit records per table (default 0: unlimited)")
    args = parser_arg.parse_args()

    cleanse_bus_records(target_table=args.table, dry_run=not args.execute, limit=args.limit)
