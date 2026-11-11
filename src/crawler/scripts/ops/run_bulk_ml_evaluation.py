# ruff: noqa: E402
"""バルクML評価バッチ CLI スクリプト (Option B / Issue #716)"""
import argparse
import datetime
import os
import sys
from typing import Any

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)
import realestateSettings
realestateSettings.configure()
from django.utils import timezone

from package.ml.evaluation.notifications import notify_slack
from package.ml.evaluation.persistence import bulk_update_evaluation_records, save_chunk
from package.ml.evaluation.record_builder import (
    build_or_update_eval_record, extract_land_rent_and_liability, populate_text_risks,
)
from package.ml.evaluation.runner import evaluate_single_model, run_bulk_evaluation as _orig_run_bulk_evaluation
from package.ml.evaluation.targets import get_all_property_models
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_dev_report
from package.utils.crawl_jobs import is_cloud_environment

_populate_text_risks = populate_text_risks
_extract_land_rent_and_liability = extract_land_rent_and_liability
_build_or_update_eval_record = build_or_update_eval_record
_bulk_update_evaluation_records = bulk_update_evaluation_records
_process_eval_chunk = save_chunk
_evaluate_single_model = evaluate_single_model
_notify_slack = notify_slack
__all__ = [
    "PropertyEvaluation", "_build_or_update_eval_record", "_bulk_update_evaluation_records",
    "_evaluate_single_model", "_extract_land_rent_and_liability", "_notify_slack",
    "_populate_text_risks", "_process_eval_chunk", "get_all_property_models",
    "run_bulk_evaluation", "send_dev_report",
]

def run_bulk_evaluation(
    force: bool = False,
    limit_per_model: int | None = None,
    skip_portals: bool = False,
    skip_uncrawled: bool = False,
    reevaluate_before: datetime.date | datetime.datetime | None = None,
    skip_duplicate_check: bool = False,
    concurrency: int | None = None,
    batch_size: int | None = None,
) -> None:
    """CLI および外部呼び出し用のバルク評価実行（後方互換 monkeypatch 対応）"""
    import package.ml.evaluation.notifications as notif_mod
    import package.ml.evaluation.runner as runner_mod
    import package.ml.evaluation.targets as tgts_mod
    this_mod = sys.modules[__name__]
    runner_mod.evaluate_single_model = getattr(this_mod, "_evaluate_single_model", _evaluate_single_model)
    runner_mod.get_all_property_models = tgts_mod.get_all_property_models = getattr(this_mod, "get_all_property_models", get_all_property_models)
    notif_mod.send_dev_report = getattr(this_mod, "send_dev_report", send_dev_report)
    kwargs: dict[str, Any] = {
        "force": force,
        "limit_per_model": limit_per_model,
        "skip_portals": skip_portals,
        "skip_uncrawled": skip_uncrawled,
        "reevaluate_before": reevaluate_before,
        "skip_duplicate_check": skip_duplicate_check,
    }
    if concurrency is not None:
        kwargs["concurrency"] = concurrency
    if batch_size is not None:
        kwargs["batch_size"] = batch_size
    prev_bulk_flag = os.environ.get("BULK_ML_EVALUATION_RUNNING")
    os.environ["BULK_ML_EVALUATION_RUNNING"] = "1"
    try:
        _orig_run_bulk_evaluation(**kwargs)
    finally:
        if prev_bulk_flag is None:
            os.environ.pop("BULK_ML_EVALUATION_RUNNING", None)
        else:
            os.environ["BULK_ML_EVALUATION_RUNNING"] = prev_bulk_flag

def main() -> None:
    """CLI エントリポイント"""
    parser = argparse.ArgumentParser(description="Bulk ML Evaluation Batch")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already evaluated properties")
    parser.add_argument("--limit", type=int, default=None, help="Limit properties per model for testing")
    parser.add_argument(
        "--workers", "--concurrency",
        dest="concurrency",
        type=int,
        default=None,
        help="Number of parallel evaluation worker threads (e.g. 16)",
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=None,
        help="Database bulk_create / bulk_update write batch size (e.g. 100)",
    )
    parser.add_argument(
        "--before-date",
        type=str,
        default=None,
        help="Re-evaluate properties with analyzed_at before this date (YYYY-MM-DD)",
    )
    is_cloud = is_cloud_environment()
    parser.add_argument(
        "--skip-portals",
        dest="skip_portals",
        action="store_true",
        default=is_cloud,
        help="Skip large portal sites (athome, homes)",
    )
    parser.add_argument(
        "--no-skip-portals",
        dest="skip_portals",
        action="store_false",
        help="Do not skip portal sites even on Cloud environment",
    )
    parser.add_argument("--skip-uncrawled", action="store_true", help="Skip un-crawled/mid-tier broker sites (kenbiya, ietan, haseko, adcast, toho)")
    parser.add_argument("--skip-duplicate-check", action="store_true", help="Skip candidate pool duplicate check for ultra-fast full re-evaluation")
    args = parser.parse_args()

    reevaluate_before = None
    if args.before_date:
        parsed_d = datetime.date.fromisoformat(args.before_date)
        # 指定日の 00:00:00 (aware datetime) を閾値とし、それより前に分析されたものを再処理
        reevaluate_before = timezone.make_aware(
            datetime.datetime.combine(parsed_d, datetime.time.min)
        )

    run_bulk_evaluation(
        force=args.force,
        limit_per_model=args.limit,
        skip_portals=args.skip_portals,
        skip_uncrawled=args.skip_uncrawled,
        reevaluate_before=reevaluate_before,
        skip_duplicate_check=args.skip_duplicate_check,
        concurrency=args.concurrency,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()
