"""
政令指定都市の address2 行政区復旧スクリプト (Issue #1277)
DB に保存された address2 が「名古屋市」等の政令市単体になっているレコードを、
原本 address から「市＋区」を再抽出して安全にバックフィルします。
"""

import logging
import re
import sys
import setup_env
from django.db import transaction
from package.ml.features.parsers import _clean_addr2
from package.ml.training.data_loader import collect_model_classes_by_type

logger = logging.getLogger(__name__)

DESIGNATED_PATTERN = r'^(名古屋|大阪|横浜|京都|神戸|福岡|札幌|さいたま|千葉|仙台|広島|静岡|浜松|新潟|相模原|堺|川崎|熊本|北九州|岡山)市$'


def restore_designated_city_address2(dry_run: bool = True) -> int:
    mbt = collect_model_classes_by_type()
    total_restored = 0
    updates_by_model = []

    print(f"\n{'='*50}")
    print(f"政令指定都市 address2 復旧バッチ (dry_run={dry_run})")
    print(f"{'='*50}")

    for ptype, model_list in mbt.items():
        for company, model in model_list:
            field_names = {f.name for f in model._meta.fields}
            if "address2" not in field_names or "address" not in field_names:
                continue

            qs = model.objects.filter(address2__regex=DESIGNATED_PATTERN)
            records = list(qs.only("pk", "address", "address2"))
            if not records:
                continue

            to_update = []
            for obj in records:
                raw_addr = getattr(obj, "address", "") or ""
                # 原本住所から市区町村（政令市＋区）を再抽出
                restored = _clean_addr2(raw_addr)
                # 都道府県名が混ざっている場合（例: 愛知県名古屋市中村区）のクレンジング
                m = re.search(r'((?:名古屋|大阪|横浜|京都|神戸|福岡|札幌|さいたま|千葉|仙台|広島|静岡|浜松|新潟|相模原|堺|川崎|熊本|北九州|岡山)市[^区]+区)', raw_addr)
                if m:
                    restored = m.group(1)

                # 元の address2 に含まれる市名と一致し、区名が取得できている場合のみ更新
                curr_city = obj.address2.strip()
                if restored and curr_city in restored and "区" in restored and restored != obj.address2:
                    old_addr2 = obj.address2
                    obj.address2 = restored
                    to_update.append((obj, old_addr2, restored, raw_addr))

            if to_update:
                total_restored += len(to_update)
                print(f"[{company} {ptype}] {model.__name__}: {len(to_update)} 件の復旧候補")
                for _, old_a2, new_a2, raw in to_update[:2]:
                    print(f"   pk={_ .pk}: {old_a2!r} -> {new_a2!r} (raw: {raw!r})")

                if not dry_run:
                    with transaction.atomic():
                        objs_to_save = [item[0] for item in to_update]
                        model.objects.bulk_update(objs_to_save, ["address2"], batch_size=500)
                    print(f"   -> DB更新完了 ({len(objs_to_save)} 件)")

    print(f"\n合計復旧件数: {total_restored} 件")
    return total_restored


if __name__ == "__main__":
    is_dry = "--commit" not in sys.argv
    restore_designated_city_address2(dry_run=is_dry)
