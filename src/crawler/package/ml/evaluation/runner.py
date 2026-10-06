"""
バルク ML 評価の並列実行オーケストレーター (Issue #716)
"""

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from django.db import close_old_connections
from package.ml.evaluation.notifications import notify_slack
from package.ml.evaluation.persistence import EVAL_MAP_FIELDS, save_chunk
from package.ml.evaluation.record_builder import resolve_company_and_type
from package.ml.evaluation.targets import (
    get_all_property_models,
    iter_unprocessed_chunks,
)
from package.ml.predict import bulk_predict_first_stage
from package.models.evaluation import PropertyEvaluation
from package.utils.batch_metrics import BatchMetrics
from package.utils.deduplication import clear_real_property_cache

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 8
DEFAULT_BATCH_SIZE = 1000


def evaluate_single_model(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool,
    limit_per_model: int | None,
    batch_size: int = 1000,
) -> tuple[int, int, int, int]:
    """単一モデルの物件群をストリーミング評価（スレッドセーフ）"""
    close_old_connections()
    model_name = model.__name__
    company, property_type = resolve_company_and_type(model_name)
    evaluated_count = 0
    passed_count = 0
    duplicate_count = 0
    total_skipped = 0

    try:
        chunk_iter = iter_unprocessed_chunks(
            model=model,
            existing_eval_map=existing_eval_map,
            force=force,
            limit=limit_per_model,
            chunk_size=batch_size,
        )
        for chunk, skipped_in_chunk in chunk_iter:
            total_skipped += skipped_in_chunk
            if not chunk:
                continue

            predicted_prices = bulk_predict_first_stage(chunk)
            p_cnt, d_cnt = save_chunk(
                chunk=chunk,
                predicted_prices=predicted_prices,
                existing_eval_map=existing_eval_map,
                company=company,
                property_type=property_type,
                batch_size=batch_size,
            )
            evaluated_count += len(chunk)
            passed_count += p_cnt
            duplicate_count += d_cnt
            logger.info("Evaluated %d properties for %s...", evaluated_count, model_name)
            sys.stdout.flush()
    finally:
        close_old_connections()

    return evaluated_count, total_skipped, passed_count, duplicate_count


def _build_slack_and_banner_messages(
    metrics: BatchMetrics,
    passed_total: int,
    duplicate_total: int,
    model_count: int,
    concurrency: int,
    failed_models: list[str],
) -> tuple[str, str]:
    """完了通知用 Slack メッセージおよびバナー文字列の構築"""
    custom_lines = [
        f"• *スクリーニング*: 1次通過(割安候補) {passed_total:,} 件 | 重複除外 {duplicate_total:,} 件",
        f"• *実行環境*: {model_count} モデル | 並行スレッド {concurrency}",
    ]
    if failed_models:
        custom_lines.append(f"⚠️ *評価失敗モデル*: {', '.join(failed_models)}")

    finish_msg = metrics.build_slack_summary(
        title="バルク価格推定完了",
        custom_lines=custom_lines,
        emoji="✅" if not failed_models else "⚠️",
    )
    banner = metrics.build_log_banner(
        title="Bulk ML Evaluation Batch",
        custom_sections=[
            f"• スクリーニング: 1次通過(割安候補) {passed_total:,} 件 | 重複除外 {duplicate_total:,} 件",
            f"• 実行環境    : {model_count} モデル | 並行スレッド {concurrency}",
        ],
    )
    return finish_msg, banner


def run_bulk_evaluation(force: bool = False, limit_per_model: int | None = None, skip_portals: bool = False) -> None:
    """全モデルの未評価物件を一括価格推定・投資評価"""
    clear_real_property_cache()
    concurrency = int(os.getenv("BULK_EVAL_CONCURRENCY", str(DEFAULT_CONCURRENCY)))
    batch_size = int(os.getenv("BULK_EVAL_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    logger.info(
        "🚀 Starting Bulk ML Evaluation Batch (Parallel Threads=%d, Batch Size=%d, force=%s, limit=%s, skip_portals=%s)...",
        concurrency, batch_size, force, limit_per_model, skip_portals,
    )
    metrics = BatchMetrics(job_name="Bulk ML Evaluation")

    existing_eval_map = {
        e.property_url: e
        for e in PropertyEvaluation.objects.all().only(*EVAL_MAP_FIELDS)
    }

    model_getter = globals().get("get_all_property_models", get_all_property_models)
    models = model_getter(skip_portals=skip_portals)
    slack_notifier = globals().get("notify_slack", notify_slack)
    single_evaluator = globals().get("evaluate_single_model", evaluate_single_model)

    if not models:
        logger.error("❌ No property models found for evaluation.")
        slack_notifier("⚠️ 【バルク価格推定エラー】 評価対象の物件モデルが0件でした。処理を中断します。")
        sys.exit(1)

    slack_notifier(
        f"🚀 【バルク価格推定開始】 未評価物件の一括価格予測および投資シミュレーション評価を開始します "
        f"(並行スレッド: {concurrency}, 全 {len(models)} モデル{' [ポータル割愛]' if skip_portals else ''})..."
    )

    evaluated_count, skipped_count, passed_total, duplicate_total = 0, 0, 0, 0
    failed_models: list[str] = []
    slack_progress_active = True

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_model = {
            executor.submit(single_evaluator, m, existing_eval_map, force, limit_per_model, batch_size): m
            for m in models
        }
        for future in as_completed(future_to_model):
            m = future_to_model[future]
            try:
                cnt, skp, p_cnt, d_cnt = future.result()
                evaluated_count += cnt
                skipped_count += skp
                passed_total += p_cnt
                duplicate_total += d_cnt
                metrics.record_processed(cnt)
                metrics.record_skipped(skp)

                if cnt > 0 and slack_progress_active:
                    try:
                        notify_slack(
                            f"📊 【価格推定進捗】 {m.__name__}: 評価 {cnt} 件 (スキップ: {skp} 件) | 累計 {evaluated_count} 件完了"
                        )
                    except (RuntimeError, OSError) as se:
                        logger.warning("Per-model progress Slack notification failed: %s", se)
                        slack_progress_active = False
            except Exception:
                failed_models.append(m.__name__)
                metrics.record_failed(1)
                logger.exception("Failed evaluating %s", m.__name__)

    metrics.total_count = evaluated_count + skipped_count
    metrics.finish()

    finish_msg, banner = _build_slack_and_banner_messages(
        metrics, passed_total, duplicate_total, len(models), concurrency, failed_models
    )
    notify_slack(finish_msg)
    logger.info("\n%s", banner)

    if failed_models:
        logger.error("❌ Bulk ML Evaluation failed on models: %s", failed_models)
        sys.exit(1)

    clear_real_property_cache()
    logger.info("✅ Bulk ML Evaluation Finished! Evaluated: %d, Skipped (Already done): %d", evaluated_count, skipped_count)
    sys.stdout.flush()
