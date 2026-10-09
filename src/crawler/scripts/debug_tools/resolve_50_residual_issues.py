"""
Issue #794: 残留50課題（不整合物件）の一括解消・再評価スクリプト

1. URL生存確認を行い、404または掲載終了のものは is_published=False, delisted_at を設定。
2. 掲載中の物件は最新のパーサー・バリデータ（PropertyDataValidator）で再評価。
3. 所在階の欠損しているSMTRCや東急等の物件は実ページまたは既存属性（floorType_kai, kaisuStr）から再補正。
4. 検証がパスした物件の needs_parser_fix を解除し、data_quality_issue をクリア。
"""
import asyncio
import os
import sys

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
from datetime import datetime, timezone

# Django初期化
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import realestateSettings

realestateSettings.configure()

from package.models.evaluation import PropertyEvaluation
from package.utils.data_validator import PropertyDataValidator
from package.utils.slack import verify_url_active
from scripts.debug_tools.auto_heal_parsers import MODEL_MAP


async def resolve_all_residual_issues():
    print("Starting resolution of residual data quality issues...")

    # 全体の中で data_quality_issue が設定されている物件を対象とする
    target_evals = list(
        PropertyEvaluation.objects.exclude(data_quality_issue="")
        .exclude(data_quality_issue__isnull=True)
    )
    print(f"Total target evaluation records: {len(target_evals)}")

    resolved_count = 0
    delisted_count = 0
    repaired_count = 0
    remaining_count = 0

    for idx, ev in enumerate(target_evals):
        model = MODEL_MAP.get((ev.company, ev.property_type))
        if not model:
            continue

        try:
            prop = model.objects.get(id=ev.property_id)
        except model.DoesNotExist:
            # 物件自体が存在しない場合は評価レコードも整合化
            ev.needs_parser_fix = False
            ev.is_published = False
            ev.data_quality_issue = ""
            ev.save(update_fields=["needs_parser_fix", "is_published", "data_quality_issue"])
            resolved_count += 1
            continue

        url = getattr(prop, "pageUrl", "")

        # 1. 所在階補正（SMTRC等で floorType_kai があって kaisuStr が空の場合、または kaisuStr から所在階を復元）
        if hasattr(prop, "kaisuStr") and not prop.kaisuStr:
            kai = getattr(prop, "floorType_kai", None)
            if kai:
                prop.kaisuStr = f"{kai}階"
                prop.save(update_fields=["kaisuStr"])
                repaired_count += 1

        # 2. 公開状況（URL生存確認）の先行チェック
        if url:
            is_active = await verify_url_active(url)
            if not is_active:
                ev.is_published = False
                ev.delisted_at = datetime.now(timezone.utc)
                ev.needs_parser_fix = False
                ev.needs_recrawl = False
                ev.data_quality_issue = ""
                ev.save(update_fields=["is_published", "delisted_at", "needs_parser_fix", "needs_recrawl", "data_quality_issue"])
                delisted_count += 1
                resolved_count += 1
                continue

        # 3. 公開中物件に対する現行バリデータ検証
        valid, _reasons = PropertyDataValidator.validate_property(prop, ev.property_type)
        if valid:
            ev.needs_parser_fix = False
            ev.data_quality_issue = ""
            ev.save(update_fields=["needs_parser_fix", "data_quality_issue"])
            resolved_count += 1
            continue

        # 4. バリデーションNGだが価格0等の異常データは再クロール要フラグを設定
        price = getattr(prop, "price", 0) or 0
        if price == 0 and url:
            ev.needs_recrawl = True
            ev.save(update_fields=["needs_recrawl"])
        remaining_count += 1

        if (idx + 1) % 500 == 0:
            print(f"Processed {idx + 1}/{len(target_evals)}... (Resolved: {resolved_count}, Delisted: {delisted_count})")

    print("\n=== Resolution Summary ===")
    print(f"Total processed: {len(target_evals)}")
    print(f"Resolved/Cleaned: {resolved_count} (Delisted 404: {delisted_count}, Repaired: {repaired_count})")
    print(f"Remaining: {remaining_count}")


if __name__ == "__main__":
    asyncio.run(resolve_all_residual_issues())
