"""
Issue #1372: DB内の未パース・過去バス利用物件データクレンジングバッチ
traffic に「バス」が含まれるが busUse1 が未設定または駅徒歩分数と混同されているレコードに対し、
最新パーサーの _populateTraffic を適用して安全に再パース・更新する。
"""
import argparse
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
from package.parser.athomeParser import (
    AthomeKodateParser,
    AthomeMansionParser,
    AthomeTochiParser,
)
from package.parser.mitsuiParser import (
    MitsuiKodateParser,
    MitsuiMansionParser,
    MitsuiTochiParser,
)
from package.parser.sumifuParser import (
    SumifuKodateParser,
    SumifuMansionParser,
    SumifuTochiParser,
)
from package.parser.tokyuParser import (
    TokyuKodateParser,
    TokyuMansionParser,
    TokyuTochiParser,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PARSER_MAP = {
    "sumifu_tochi": SumifuTochiParser,
    "sumifu_kodate": SumifuKodateParser,
    "sumifu_mansion": SumifuMansionParser,
    "athome_tochi": AthomeTochiParser,
    "athome_kodate": AthomeKodateParser,
    "athome_mansion": AthomeMansionParser,
    "tokyu_tochi": TokyuTochiParser,
    "tokyu_kodate": TokyuKodateParser,
    "tokyu_mansion": TokyuMansionParser,
    "mitsui_tochi": MitsuiTochiParser,
    "mitsui_kodate": MitsuiKodateParser,
    "mitsui_mansion": MitsuiMansionParser,
}


def cleanse_bus_records(target_table: str | None = None, dry_run: bool = True, limit: int = 1000):
    models = apps.get_models()
    total_checked = 0
    total_updated = 0

    for model in models:
        tbl_name = model._meta.db_table
        if target_table and tbl_name != target_table:
            continue
        if tbl_name not in PARSER_MAP:
            continue

        parser_cls = PARSER_MAP[tbl_name]
        parser = parser_cls()

        # traffic に「バス」を含むが、busUse1 が設定されていない、または空のレコードを抽出
        qs = model.objects.filter(traffic__icontains="バス").filter(
            django.db.models.Q(busUse1__isnull=True) | django.db.models.Q(busUse1=0)
        )
        count = qs.count()
        if count == 0:
            continue

        logger.info(f"Target table [{tbl_name}]: {count} records need check.")
        for item in qs[:limit]:
            total_checked += 1
            getattr(item, "busUse1", None)
            getattr(item, "railwayWalkMinute1", None)
            getattr(item, "busWalkMinute1", None)

            # 最新パーサーでパース
            parser._populateTraffic(item, item.traffic)

            # 変化があった場合のみ保存対象
            if getattr(item, "busUse1", None) == 1:
                total_updated += 1
                if not dry_run:
                    item.save(update_fields=[
                        "railway1", "station1", "railwayWalkMinute1", "railwayWalkMinute1Str",
                        "busUse1", "busWalkMinute1", "busWalkMinute1Str", "busStation1"
                    ])
                if total_updated <= 5 or total_updated % 100 == 0:
                    logger.info(
                        f"[{tbl_name}] ID={item.id} -> R1={item.railway1}, S1={item.station1}, "
                        f"BusUse={item.busUse1}, BusMin={item.busWalkMinute1}, BusStop={item.busStation1}, Walk={item.railwayWalkMinute1}"
                    )

        logger.info(f"[{tbl_name}] Checked: {min(count, limit)}, Updated: {total_updated} (dry_run={dry_run})")

    logger.info(f"Summary: total_checked={total_checked}, total_updated={total_updated}, dry_run={dry_run}")
    return total_updated


if __name__ == "__main__":
    parser_arg = argparse.ArgumentParser()
    parser_arg.add_argument("--table", type=str, default=None, help="Specific table name")
    parser_arg.add_argument("--execute", action="store_true", help="Execute DB save (default is dry-run)")
    parser_arg.add_argument("--limit", type=int, default=1000, help="Limit records per table")
    args = parser_arg.parse_args()

    cleanse_bus_records(target_table=args.table, dry_run=not args.execute, limit=args.limit)
