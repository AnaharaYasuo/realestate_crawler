# ruff: noqa: E402
"""バルクML評価バッチ CLI スクリプト (Option B / Issue #716)"""
import argparse
import os
import sys

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
sys.path.insert(0, _crawler_dir)
import realestateSettings
realestateSettings.configure()

from package.ml.evaluation.notifications import notify_slack
from package.ml.evaluation.persistence import bulk_update_evaluation_records, save_chunk
from package.ml.evaluation.record_builder import (
    build_or_update_eval_record, extract_land_rent_and_liability, populate_text_risks,
)
from package.ml.evaluation.runner import evaluate_single_model, run_bulk_evaluation as _orig_run_bulk_evaluation
from package.ml.evaluation.targets import get_all_property_models
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_dev_report

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

def run_bulk_evaluation(force: bool = False, limit_per_model: int | None = None, skip_portals: bool = False) -> None:
    """CLI および外部呼び出し用のバルク評価実行（後方互換 monkeypatch 対応）"""
    import package.ml.evaluation.notifications as notif_mod
    import package.ml.evaluation.runner as runner_mod
    import package.ml.evaluation.targets as tgts_mod
    this_mod = sys.modules[__name__]
    runner_mod.evaluate_single_model = getattr(this_mod, "_evaluate_single_model", _evaluate_single_model)
    runner_mod.get_all_property_models = tgts_mod.get_all_property_models = getattr(this_mod, "get_all_property_models", get_all_property_models)
    notif_mod.send_dev_report = getattr(this_mod, "send_dev_report", send_dev_report)
    _orig_run_bulk_evaluation(force=force, limit_per_model=limit_per_model, skip_portals=skip_portals)

def main() -> None:
    """CLI エントリポイント"""
    parser = argparse.ArgumentParser(description="Bulk ML Evaluation Batch")
    parser.add_argument("--force", action="store_true", help="Force re-evaluation of already evaluated properties")
    parser.add_argument("--limit", type=int, default=None, help="Limit properties per model for testing")
    parser.add_argument("--skip-portals", action="store_true", help="Skip large portal sites (athome, homes)")
    args = parser.parse_args()
    run_bulk_evaluation(force=args.force, limit_per_model=args.limit, skip_portals=args.skip_portals)


if __name__ == "__main__":
    main()
