"""
学習成果物 (モデル・メタデータ) 保存およびアップロードモジュール (Issue #715)
"""

import logging
import os
from typing import Any

import joblib
from package.utils.storage import get_storage_manager

logger = logging.getLogger(__name__)

SHARED_METADATA_FILES: tuple[str, ...] = (
    "ensemble_weights.joblib",
    "smearing_factors.joblib",
    "location_encoders.joblib",
    "p10_conformal.joblib",
)


def sync_existing_metadata_from_storage(
    model_dir: str,
    storage_manager_getter: Any = None,
    overwrite_existing: bool = False,
) -> int:
    """エフェメラルコンテナ等での単一種別ローテーション学習時に他種別メタデータを消失させないため、
    保存前にリモートストレージ (ml_models/) から既存の共有メタデータ4点を事前ダウンロードする (Issue #1841)。
    """
    os.makedirs(model_dir, exist_ok=True)
    synced = 0
    try:
        getter = storage_manager_getter or get_storage_manager
        storage = getter()
        remote_keys = set(storage.list_files("ml_models/"))
    except Exception as e:  # noqa: BLE001
        logger.warning("ML: Could not list remote metadata from storage: %s", e)
        return 0

    for fname in SHARED_METADATA_FILES:
        local_path = os.path.join(model_dir, fname)
        if os.path.exists(local_path) and not overwrite_existing:
            continue
        remote_key = f"ml_models/{fname}"
        if remote_key not in remote_keys:
            continue
        try:
            storage.download_file(remote_key, local_path)
            synced += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("ML: Could not download existing metadata %s: %s", remote_key, e)

    if synced > 0:
        logger.info("ML: Pre-synced %d existing shared metadata files from storage to %s", synced, model_dir)
    return synced


def save_stage_models(
    models_dict: dict[str, Any], model_dir: str, ptype: str, stage_key: str
) -> None:
    """特定ステージの学習済みモデルファイルおよび P10 分位点モデルを保存"""
    import gc

    for algo, model in models_dict.items():
        fname = f"{ptype}_{stage_key}_stage_{algo}.joblib"
        joblib.dump(model, os.path.join(model_dir, fname))
        gc.collect()
    p10_model = getattr(models_dict, "p10_model", None)
    if p10_model is not None:
        p10_fname = f"{ptype}_{stage_key}_stage_p10.joblib"
        joblib.dump(p10_model, os.path.join(model_dir, p10_fname))
        gc.collect()


def _load_existing_dict(filepath: str) -> dict[str, Any]:
    if os.path.exists(filepath):
        try:
            val = joblib.load(filepath)
            if isinstance(val, dict):
                return dict(val)
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not load existing metadata %s: %s", filepath, e)
    return {}


def save_metadata(
    model_dir: str,
    all_ensemble_weights: dict[str, Any],
    all_smearing_factors: dict[str, Any],
    mkt_master: dict[Any, Any] | None = None,
    location_encoders: dict[str, Any] | None = None,
    p10_conformal: dict[str, Any] | None = None,
) -> None:
    """アンサンブル重み、スミアリング補正係数、取引事例比較マスタ、空間ターゲットエンコーダ、P10較正オフセットを保存 (既存マージ保護)"""
    if mkt_master is not None:
        joblib.dump(mkt_master, os.path.join(model_dir, "mkt_comparison_master.joblib"))

    weights_path = os.path.join(model_dir, "ensemble_weights.joblib")
    merged_weights = _load_existing_dict(weights_path)
    merged_weights.update(all_ensemble_weights)
    joblib.dump(merged_weights, weights_path)

    smearing_path = os.path.join(model_dir, "smearing_factors.joblib")
    merged_smearing = _load_existing_dict(smearing_path)
    merged_smearing.update(all_smearing_factors)
    joblib.dump(merged_smearing, smearing_path)

    if location_encoders is not None:
        loc_path = os.path.join(model_dir, "location_encoders.joblib")
        merged_loc = _load_existing_dict(loc_path)
        merged_loc.update(location_encoders)
        joblib.dump(merged_loc, loc_path)

    if p10_conformal is not None:
        p10_path = os.path.join(model_dir, "p10_conformal.joblib")
        merged_p10 = _load_existing_dict(p10_path)
        merged_p10.update(p10_conformal)
        joblib.dump(merged_p10, p10_path)


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
