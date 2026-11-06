"""
Issue #1291: price カラムの「万円」表記混在データの priceStr 再パースによる修復メンテナンススクリプト
"""
import argparse
import logging
import os
import sys
from typing import Any

# Ensure crawler directory is on sys.path
_crawler_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

# Ensure Django environment is configured
try:
    import setup_env  # noqa: F401
except ImportError:
    pass

from django.db import transaction
from django.db.models import Q

from package.ml.training.data_loader import collect_model_classes_by_type
from package.utils.converter import parse_price, parse_yen

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def restore_price_units(
    dry_run: bool = True,
    target_ptype: str | None = None,
    target_company: str | None = None,
    batch_size: int = 500,
) -> dict[str, int]:
    """
    全物件モデル（または指定種別/会社）の price カラムを走査し、
    priceStr から parse_price を用いて正確な『円単位』へ修復・一括更新する。
    """
    models_by_type = collect_model_classes_by_type()
    summary = {"total_scanned": 0, "total_repaired": 0, "total_skipped_already_correct": 0, "total_skipped_unparseable": 0}

    for ptype, model_list in models_by_type.items():
        if target_ptype and ptype != target_ptype:
            continue

        for company, model in model_list:
            if target_company and company != target_company:
                continue

            field_names = {f.name for f in model._meta.fields}
            if "price" not in field_names or "priceStr" not in field_names:
                continue

            # 50万円未満または priceStr に「億」が含まれる高額帯レコードを走査
            qs = model.objects.filter(
                Q(price__lt=500000) | Q(priceStr__contains="億")
            ).filter(price__isnull=False).exclude(price=0)
            records = list(qs.only("pk", "price", "priceStr"))
            if not records:
                continue

            summary["total_scanned"] += len(records)
            to_update = []

            for obj in records:
                p_str = getattr(obj, "priceStr", "") or ""
                reparsed = None
                # 「円」で終わる（または明示的に円単位表記）の場合は parse_yen を優先
                if "円" in p_str and "万円" not in p_str and "億" not in p_str:
                    reparsed = parse_yen(p_str)
                if reparsed is None:
                    reparsed = parse_price(p_str)

                if reparsed is None or reparsed <= 0:
                    summary["total_skipped_unparseable"] += 1
                    continue

                if reparsed == obj.price:
                    summary["total_skipped_already_correct"] += 1
                    continue

                old_price = obj.price
                to_update.append((obj, old_price, reparsed, p_str))

            if to_update:
                summary["total_repaired"] += len(to_update)
                logger.info(
                    "[%s %s] %s: %d 件の修復候補 (例: pk=%s, old=%s, new=%s, str=%r)",
                    company,
                    ptype,
                    model.__name__,
                    len(to_update),
                    to_update[0][0].pk,
                    to_update[0][1],
                    to_update[0][2],
                    to_update[0][3],
                )

                if not dry_run:
                    with transaction.atomic():
                        # 書き込み時に読み込み時と価格・文字列が変化していないレコードのみ更新
                        for target_obj, orig_price, new_val, orig_str in to_update:
                            updated_rows = model.objects.filter(
                                pk=target_obj.pk,
                                price=orig_price,
                                priceStr=orig_str,
                            ).update(price=new_val)
                            if updated_rows == 0:
                                logger.warning(
                                    "競合検出: pk=%s の値が実行中に更新されたためスキップしました",
                                    target_obj.pk,
                                )
                    logger.info("   -> DB更新完了 (%d 件)", len(to_update))

    logger.info("=== 処理結果サマリー ===")
    logger.info("走査件数: %d 件", summary["total_scanned"])
    logger.info("修復件数: %d 件 (dry_run=%s)", summary["total_repaired"], dry_run)
    logger.info("変更不要 (既に円単位): %d 件", summary["total_skipped_already_correct"])
    logger.info("再パース不能 (priceStr空等): %d 件", summary["total_skipped_unparseable"])
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore price units from priceStr")
    parser.add_argument("--commit", action="store_true", help="Actually commit updates to the database")
    parser.add_argument("--ptype", type=str, default=None, help="Filter by property type (mansion/kodate/tochi/apartment)")
    parser.add_argument("--company", type=str, default=None, help="Filter by company")
    args = parser.parse_args()

    restore_price_units(
        dry_run=not args.commit,
        target_ptype=args.ptype,
        target_company=args.company,
    )
