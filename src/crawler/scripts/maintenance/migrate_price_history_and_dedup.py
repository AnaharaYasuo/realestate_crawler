# ruff: noqa: E402
# -*- coding: utf-8 -*-
"""
migrate_price_history_and_dedup.py

既存データベース内の同一URL重複レコードを整理し、過去の価格改定推移を
PropertyPriceHistory テーブルへ移行して重複を解消するメンテナンススクリプト。

【安全設計】
1. クローラー稼働中の実行を防止（事前チェック）。
2. デフォルトは --dry-run（DB変更なし、集計レポートのみ出力）。
3. 実際の変更には --execute フラグの明示が必要。
4. 1物件1レコード（最新マスタ）へ正規化し、初回登録日（inputDateTime）を維持。
5. PropertyEvaluation の参照ID（property_id）を最新IDに自動再リンク。
"""

import os
import sys
import argparse
import logging
from typing import List, Tuple, Dict, Any

# パス設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.dirname(_current_dir)
_crawler_dir = os.path.dirname(_scripts_dir)
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from django.apps import apps
from django.db import transaction
from django.db.models import Count
from package.models.base import PropertyBaseModel
from package.models.evaluation import PropertyEvaluation, PropertyPriceHistory


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("migration")


def check_active_crawlers() -> bool:
    """現在アクティブなクローラー実行プロセスまたはジョブが存在するか確認する"""
    from package.models.crawler_task_execution import CrawlerTaskExecution
    try:
        if CrawlerTaskExecution.objects.filter(status="RUNNING").exists():
            logger.warning("DB上でステータスが RUNNING のクローラータスクを検出しました。")
            return True
    except Exception:
        pass

    myself = os.getpid()
    if not os.path.exists('/proc'):
        return False

    for pid_str in os.listdir('/proc'):
        if not pid_str.isdigit():
            continue
        pid = int(pid_str)
        if pid == myself:
            continue
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as f:
                cmdline = f.read().decode('utf-8', errors='ignore').replace('\0', ' ')
            # クロール実行コマンド（run_all_crawlers または --company 指定のmain.py実行）を検知
            if 'python' in cmdline and ('run_all_crawlers.py' in cmdline or '--company' in cmdline):
                logger.warning(f"稼働中クローラープロセスを検出: PID {pid} ({cmdline[:80]})")
                return True
        except Exception:
            continue
    return False


def get_target_models(target_filter: str = "") -> List[Any]:
    """移行対象となる全物件モデルクラスを取得する"""
    all_models = apps.get_models()
    targets = []
    for m in all_models:
        if issubclass(m, PropertyBaseModel) and m is not PropertyBaseModel:
            if not target_filter or target_filter.lower() in m.__name__.lower():
                targets.append(m)
    return sorted(targets, key=lambda x: x.__name__)


def process_model(model: Any, is_execute: bool, batch_size: int = 500) -> Dict[str, Any]:
    """対象モデルの重複URLを走査し、価格履歴の抽出および重複解消を行う"""
    model_name = model.__name__
    stats = {
        "model_name": model_name,
        "total_records": 0,
        "unique_urls": 0,
        "duplicate_urls": 0,
        "records_to_delete": 0,
        "price_history_created": 0,
        "eval_relinked": 0,
    }

    stats["total_records"] = model.objects.count()
    if stats["total_records"] == 0:
        return stats

    # 重複URL（件数 > 1）の抽出
    dup_groups = list(
        model.objects.values("pageUrl")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
        .values_list("pageUrl", "cnt")
    )
    stats["duplicate_urls"] = len(dup_groups)
    stats["records_to_delete"] = sum(cnt - 1 for _, cnt in dup_groups)
    stats["unique_urls"] = stats["total_records"] - stats["records_to_delete"]

    if not dup_groups:
        return stats

    # 会社コード・種別の推定
    company = "unknown"
    for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio"]:
        if model_name.lower().startswith(c):
            company = c
            break
    property_type = model_name.lower().replace(company, "")

    # 重複URLをバッチ単位で処理
    total_dups = len(dup_groups)
    for i in range(0, total_dups, batch_size):
        chunk_urls = [u for u, _ in dup_groups[i : i + batch_size]]

        # chunk内の全レコードを一括取得してURLごとにグルーピング
        chunk_records = list(
            model.objects.filter(pageUrl__in=chunk_urls)
            .order_by("pageUrl", "inputDateTime", "id")
        )

        grouped: Dict[str, List[Any]] = {}
        for r in chunk_records:
            grouped.setdefault(r.pageUrl, []).append(r)

        history_to_create: List[PropertyPriceHistory] = []
        ids_to_delete: List[int] = []
        updates_to_perform: List[Tuple[Any, Any, Any]] = []  # (latest_row, oldest_row)
        eval_relink_ids: Dict[str, int] = {}  # url -> latest_id

        for url, records in grouped.items():
            if len(records) < 2:
                continue

            oldest = records[0]
            latest = records[-1]
            ids_to_delete.extend([r.id for r in records[:-1]])
            eval_relink_ids[url] = latest.id

            # 価格推移の時系列チェック
            prev_price = None
            for r in records:
                curr_price = r.price
                if curr_price is not None and curr_price > 0:
                    if prev_price is not None and curr_price != prev_price:
                        diff = curr_price - prev_price
                        history_to_create.append(
                            PropertyPriceHistory(
                                property_url=url,
                                company=company,
                                property_type=property_type,
                                old_price=prev_price,
                                new_price=curr_price,
                                price_diff=diff,
                                recorded_at=r.inputDateTime or r.updateDateTime or oldest.inputDateTime
                            )
                        )
                    prev_price = curr_price

            updates_to_perform.append((latest, oldest))

        stats["price_history_created"] += len(history_to_create)

        # 実行モード時の実データ反映
        if is_execute:
            with transaction.atomic():
                # 1. 価格履歴のバルク投入
                if history_to_create:
                    PropertyPriceHistory.objects.bulk_create(history_to_create, batch_size=500)

                # 2. 生存マスタ（最新レコード）の日時整合性更新
                for latest, oldest in updates_to_perform:
                    latest.inputDate = oldest.inputDate
                    latest.inputDateTime = oldest.inputDateTime
                    # updateDateTime が未設定なら最新レコードの inputDateTime を適用
                    latest.updateDateTime = latest.updateDateTime or latest.inputDateTime
                    latest.save(update_fields=["inputDate", "inputDateTime", "updateDateTime"])

                # 3. PropertyEvaluation の参照先を最新レコードIDに再リンク
                for url, new_id in eval_relink_ids.items():
                    updated = PropertyEvaluation.objects.filter(property_url=url).update(property_id=new_id)
                    stats["eval_relinked"] += updated

                # 4. 旧重複レコードの削除
                if ids_to_delete:
                    model.objects.filter(id__in=ids_to_delete).delete()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate property price history and clean up duplicates.")
    parser.add_argument("--execute", action="store_true", help="Perform actual database modifications (Default: dry-run).")
    parser.add_argument("--table", type=str, default="", help="Filter specific table/model name (e.g. mitsui, MitsuiMansion).")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for URL chunking (default: 500).")
    parser.add_argument("--skip-crawler-check", action="store_true", help="Skip checking for active crawler processes.")
    args = parser.parse_args()

    mode_str = "【本番実行モード (EXECUTE)】" if args.execute else "【事前検証モード (DRY-RUN - 変更なし)】"
    print("\n==================================================")
    print("  価格改定履歴移行 & 重複レコード解消スクリプト")
    print(f"  実行モード: {mode_str}")
    print("==================================================\n")

    # クローラー停止チェック
    if not args.skip_crawler_check:
        if check_active_crawlers():
            print("❌ 【安全停止エラー】クローラープロセスが現在稼働中です。")
            print("   データの不整合を防ぐため、事前にクローラーを停止してください：")
            print("   実行コマンド: python src/crawler/stop_crawler.py\n")
            print("   強制実行する場合は --skip-crawler-check を付与してください。")
            sys.exit(1)
        else:
            print("✅ クローラー停止確認: アクティブなクローラーは検知されませんでした。\n")

    targets = get_target_models(args.table)
    if not targets:
        print(f"対象モデルが見つかりませんでした (フィルター: '{args.table}')")
        return

    print(f"対象モデル数: {len(targets)} 件\n")

    total_records = 0
    total_dups = 0
    total_deletes = 0
    total_histories = 0
    total_relinks = 0

    results = []

    for idx, model in enumerate(targets, 1):
        print(f"[{idx}/{len(targets)}] 走査中: {model.__name__} ...", end="", flush=True)
        stats = process_model(model, is_execute=args.execute, batch_size=args.batch_size)
        results.append(stats)
        print(f" 完了 (重複: {stats['duplicate_urls']:,} URL, 削除対象: {stats['records_to_delete']:,} 行, 履歴: {stats['price_history_created']:,} 件)")

        total_records += stats["total_records"]
        total_dups += stats["duplicate_urls"]
        total_deletes += stats["records_to_delete"]
        total_histories += stats["price_history_created"]
        total_relinks += stats["eval_relinked"]

    # 総合サマリーレポート
    print("\n==================================================")
    print(f"  移行集計結果サマリー ({mode_str})")
    print("==================================================")
    print(f"・ 走査テーブル数:        {len(targets):,} テーブル")
    print(f"・ 総物件レコード数:      {total_records:,} 件")
    print(f"・ 重複URL数:             {total_dups:,} 件")
    print(f"・ 削除対象（重複行）:    {total_deletes:,} 件")
    print(f"・ 抽出される価格改定履歴: {total_histories:,} 件")
    if args.execute:
        print(f"・ PropertyEvaluation再リンク: {total_relinks:,} 件")
    print("==================================================\n")

    if not args.execute:
        print("💡 これは DRY-RUN（事前シミュレーション）です。データベースは一切変更されていません。")
        print("   実際に移行・重複解消を実行するには以下のコマンドを実行してください：")
        table_arg = f" --table {args.table}" if args.table else ""
        print(f"   python src/crawler/scripts/maintenance/migrate_price_history_and_dedup.py --execute{table_arg}\n")


if __name__ == "__main__":
    main()
