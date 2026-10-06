"""
学習成果物 (モデル・メタデータ) 保存およびアップロードモジュール (Issue #715)
"""

import logging
import os
from typing import Any

import joblib
from package.utils.storage import get_storage_manager

logger = logging.getLogger(__name__)


def save_stage_models(models_dict: dict[str, Any], model_dir: str, ptype: str, stage_key: str) -> None:
    """特定ステージの学習済みモデルファイルを保存"""
    for algo, model in models_dict.items():
        fname = f"{ptype}_{stage_key}_stage_{algo}.joblib"
        joblib.dump(model, os.path.join(model_dir, fname))


def save_metadata(
    model_dir: str,
    all_ensemble_weights: dict[str, Any],
    all_smearing_factors: dict[str, Any],
    mkt_master: dict[str, Any] | None = None,
) -> None:
    """アンサンブル重み、スミアリング補正係数、取引事例比較マスタを保存"""
    if mkt_master is not None:
        joblib.dump(mkt_master, os.path.join(model_dir, "mkt_comparison_master.joblib"))
    joblib.dump(all_ensemble_weights, os.path.join(model_dir, "ensemble_weights.joblib"))
    joblib.dump(all_smearing_factors, os.path.join(model_dir, "smearing_factors.joblib"))


def upload_models_to_storage(model_dir: str) -> int:
    """ローカルモデルディレクトリ内の joblib 群をリモートストレージへアップロード"""
    uploaded_count = 0
    try:
        storage = get_storage_manager()
        for f in os.listdir(model_dir):
            if f.endswith(".joblib"):
                local_fpath = os.path.join(model_dir, f)
                gcs_key = f"ml_models/{f}"
                storage.upload_file(local_fpath, gcs_key)
                uploaded_count += 1
    except (OSError, RuntimeError) as e:
        logger.warning("ML: Failed to upload models to storage: %s", e)
    except Exception as e:  # noqa: BLE001
        logger.warning("ML: Unexpected failure uploading models to storage: %s", e)
    return uploaded_count
