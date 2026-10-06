"""
バルク ML 評価パッケージ (Issue #716)

未評価物件のストリーミング処理、プロ目線リスク抽出、
評価レコード永続化、並列実行ランナー、Slack通知を提供します。
"""

from package.ml.evaluation.notifications import notify_slack
from package.ml.evaluation.persistence import bulk_update_evaluation_records, save_chunk
from package.ml.evaluation.record_builder import (
    build_or_update_eval_record,
    extract_land_rent_and_liability,
    populate_text_risks,
)
from package.ml.evaluation.runner import evaluate_single_model, run_bulk_evaluation
from package.ml.evaluation.targets import (
    get_all_property_models,
    iter_unprocessed_chunks,
)

__all__ = [
    "build_or_update_eval_record",
    "bulk_update_evaluation_records",
    "evaluate_single_model",
    "extract_land_rent_and_liability",
    "get_all_property_models",
    "iter_unprocessed_chunks",
    "notify_slack",
    "populate_text_risks",
    "run_bulk_evaluation",
    "save_chunk",
]
