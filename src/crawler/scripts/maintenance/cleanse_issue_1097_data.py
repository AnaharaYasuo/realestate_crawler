"""
東急リバブル パーサー不整合データ インプレース直接修復スクリプト (Issue #1106 / #1097)

東急リバブル（tokyu）の物件において、間取りや構造等のフィールドに辞書の文字列表現
（例: "{'value': '3LDK', ...}"）が誤って格納されてしまったレコードを検出し、
再クローリングを行うことなく既存レコードから本来の値を直接抽出してインプレース修復する。

修復完了後、PropertyEvaluation 上の `needs_recrawl=False` および `data_quality_issue=""`
を設定し、MLモデルの学習・推論対象に即時安全に復帰させる。
"""
from __future__ import annotations

import argparse
import ast
import logging
import os
import re
import sys
from typing import Any

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401
        break
    _cur = _parent

from django.db import transaction
from django.db.models import Q
from package.models.evaluation import PropertyEvaluation
from package.models.tokyu import (
    TokyuInvestmentApartment,
    TokyuInvestmentKodate,
    TokyuKodate,
    TokyuMansion,
    TokyuTochi,
)

logger = logging.getLogger(__name__)

VALUE_REGEX = re.compile(r"['\"]value['\"]\s*:\s*(?:'([^']*)'|\"([^\"]*)\")")


def extract_value_from_dict_repr(val: Any) -> Any:
    """辞書文字列表現（"{'value': '3LDK', ...}" 等）から値文字列を取り出す。
    辞書文字列表現でない場合はそのままの値を返す。
    """
    if not isinstance(val, str):
        return val

    s = val.strip()
    if not (s.startswith("{") and ("'value'" in s or '"value"' in s)):
        return val

    m = VALUE_REGEX.search(s)
    if m:
        extracted = m.group(1) if m.group(1) is not None else m.group(2)
        return extracted.strip()

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, dict) and "value" in parsed:
            extracted_val = parsed["value"]
            return str(extracted_val).strip() if extracted_val is not None else ""
    except Exception:
        pass

    return val


def repair_model_records(model_cls, fields: list[str], dry_run: bool = False) -> tuple[int, set[str]]:
    """指定モデルの対象フィールドに存在する辞書文字列表現をインプレース修復する。"""
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__startswith": "{'value'"})
        query |= Q(**{f"{field}__startswith": '{"value"'})

    affected_urls: set[str] = set()
    total_repaired = 0

    qs = model_cls.objects.filter(query)
    for obj in qs:
        changed = False
        for field in fields:
            current_val = getattr(obj, field, None)
            if current_val and isinstance(current_val, str) and (current_val.startswith("{'value'") or current_val.startswith('{"value"')):
                new_val = extract_value_from_dict_repr(current_val)
                if new_val != current_val:
                    setattr(obj, field, new_val)
                    changed = True

        if changed:
            affected_urls.add(obj.pageUrl)
            total_repaired += 1
            if not dry_run:
                obj.save(update_fields=fields)

    logger.info(
        "[%s] Repaired %d records (%d unique URLs) in %s",
        "DRY RUN" if dry_run else "APPLIED",
        total_repaired,
        len(affected_urls),
        model_cls.__name__,
    )
    return total_repaired, affected_urls


def cleanse_tokyu_in_place(dry_run: bool = False) -> dict[str, int]:
    """東急リバブルの全モデルの辞書文字列表現を修復し、PropertyEvaluation を正常化する。"""
    model_targets = [
        (TokyuKodate, ["madori", "kouzou", "youtoChiiki", "tochikenri"]),
        (TokyuMansion, ["madori", "kouzou", "kaisuStr", "tochikenri"]),
        (TokyuTochi, ["chimoku", "youtoChiiki", "tochikenri"]),
        (TokyuInvestmentKodate, ["kouzou", "youtoChiiki", "tochikenri"]),
        (TokyuInvestmentApartment, ["kouzou", "youtoChiiki", "tochikenri", "chimoku"]),
    ]

    all_affected_urls: set[str] = set()
    stats: dict[str, int] = {}

    for model_cls, fields in model_targets:
        count, urls = repair_model_records(model_cls, fields, dry_run=dry_run)
        stats[model_cls.__name__] = count
        all_affected_urls.update(urls)

    # PropertyEvaluation のフラグ正常化 (不整合URLまたは既存のtokyu_madori_dict_bug対象)
    eval_qs = PropertyEvaluation.objects.filter(
        company="tokyu",
    ).filter(
        Q(data_quality_issue="tokyu_madori_dict_bug") | Q(property_url__in=all_affected_urls)
    )
    eval_count = eval_qs.count()
    stats["PropertyEvaluation_reset"] = eval_count

    if dry_run:
        logger.info("[DRY RUN] Would reset needs_recrawl and data_quality_issue for %d PropertyEvaluation records", eval_count)
    else:
        with transaction.atomic():
            eval_qs.update(
                needs_recrawl=False,
                data_quality_issue="",
            )
            logger.info("Reset %d PropertyEvaluation records to needs_recrawl=False", eval_count)

    return stats


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Cleanse tokyu anomaly data in-place without recrawling")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without modifying database")
    args = parser.parse_args()

    stats = cleanse_tokyu_in_place(dry_run=args.dry_run)
    print("Summary:", stats)


if __name__ == "__main__":
    main()
