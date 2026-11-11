"""オープンデータJSONキャッシュのGCS双方向同期およびオンデマンド解決ポリシー (Issue #1366)"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from package.utils.storage import get_storage_manager

logger = logging.getLogger(__name__)

REMOTE_OPEN_DATA_PREFIX = "ml_reference_data"


def should_sync_storage_cache() -> bool:
    """実行環境がオブジェクトストレージ（GCS/MinIO）とのキャッシュ同期を行うべきか判定する。"""
    if os.getenv("OPEN_DATA_STORAGE_SYNC_FORCE", "").strip() in ("1", "true", "yes"):
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    if os.getenv("OPEN_DATA_STORAGE_SYNC_DISABLE", "").strip() in ("1", "true", "yes"):
        return False
    is_cloud = os.getenv("IS_CLOUD", "").strip().lower() in ("1", "true")
    is_gcs = os.getenv("STORAGE_BACKEND", "").strip().lower() == "gcs"
    return is_cloud or is_gcs


def allow_ondemand_open_geo() -> bool:
    """未キャッシュの新規町丁目・座標に対して単発オンデマンドGSI解決を許可するか判定する。"""
    explicit = os.getenv("ALLOW_ONDEMAND_OPEN_GEO", "").strip().lower()
    if explicit in ("0", "false", "no"):
        return False
    if explicit in ("1", "true", "yes"):
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return os.getenv("BULK_ML_EVALUATION_RUNNING", "").strip() not in ("1", "true")


def ensure_local_cache_from_storage(
    local_path: Path,
    remote_filename: str,
    storage_getter: Callable[[], Any] | None = None,
) -> bool:
    """ローカルにキャッシュファイルが存在しない場合、GCS `ml_reference_data/` から自動取得する。"""
    if local_path.exists() or not should_sync_storage_cache():
        return False
    remote_key = f"{REMOTE_OPEN_DATA_PREFIX}/{remote_filename}"
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        getter = storage_getter or get_storage_manager
        getter().download_file(remote_key, str(local_path))
        if local_path.exists() and local_path.stat().st_size > 0:
            logger.info("Downloaded open-data cache from storage: %s -> %s", remote_key, local_path)
            return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("Open-data cache not available in storage (%s): %s", remote_key, exc)
    return False


def upload_cache_to_storage(
    local_path: Path,
    remote_filename: str,
    storage_getter: Callable[[], Any] | None = None,
) -> bool:
    """更新されたローカルJSONキャッシュを GCS `ml_reference_data/` へアップロードする。"""
    if not local_path.exists() or not should_sync_storage_cache():
        return False
    remote_key = f"{REMOTE_OPEN_DATA_PREFIX}/{remote_filename}"
    try:
        getter = storage_getter or get_storage_manager
        getter().upload_file(str(local_path), remote_key, content_type="application/json")
        logger.info("Uploaded open-data cache to storage: %s -> %s", local_path, remote_key)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to upload open-data cache %s: %s", remote_key, exc)
        return False
