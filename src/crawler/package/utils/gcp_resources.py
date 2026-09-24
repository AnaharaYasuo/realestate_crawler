"""GCP リソース管理共通ユーティリティ (ProxySQL MIG, GCE, Auth)."""

import logging
import os
import socket
import time
from collections.abc import Callable
from typing import Any

import requests

try:
    from google.cloud import compute_v1
except ImportError:
    compute_v1 = None

try:
    import google.auth
    import google.auth.transport.requests
except ImportError:
    google = None

logger = logging.getLogger(__name__)


def get_gcp_access_token() -> str | None:
    """GCP 認証トークンを取得 (google.auth または メタデータサーバー経由)"""
    if google is not None:
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/compute"]
            )
            req = google.auth.transport.requests.Request()
            credentials.refresh(req)
            if credentials.token:
                return str(credentials.token)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"google.auth default credentials not available: {e}")

    try:
        resp = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
            timeout=5,
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                return str(token)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Metadata server token not available: {e}")
    return None


def _resize_mig_via_rest(
    project: str,
    region: str,
    mig: str,
    target_size: int,
    token: str | None,
) -> bool:
    """REST API を直接呼び出して ProxySQL MIG をリサイズ。"""
    if not token:
        return False
    url = f"https://compute.googleapis.com/compute/v1/projects/{project}/regions/{region}/instanceGroupManagers/{mig}/resize?size={target_size}"
    try:
        resp = requests.post(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code in (200, 204):
            logger.info(
                f"Resize operation submitted via REST API: HTTP {resp.status_code}"
            )
            return True
        logger.error(f"REST API resize failed: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"REST API resize request error: {e}")
    return False


def scale_proxysql_mig(
    target_size: int = 1,
    project_id: str | None = None,
    region: str | None = None,
    mig_name: str | None = None,
    dry_run: bool = False,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> bool:
    """ProxySQL MIG のサイズを変更 (0 -> 1 または 1 -> 0)。

    compute_v1 -> REST API -> gcloud CLI の順でフォールバック。
    """
    project = (
        project_id
        or os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    )
    reg = region or os.getenv("GCP_REGION", "asia-northeast1")
    mig = mig_name or os.getenv(
        "PROXYSQL_MIG_NAME", f"proxysql-mig-{os.getenv('ENVIRONMENT', 'prod')}"
    )

    logger.info(
        f"Scaling ProxySQL MIG '{mig}' to size {target_size} (project: {project}, region: {reg}, dry_run: {dry_run})"
    )
    if dry_run or not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        logger.info(f"[Dry-run/Local] ProxySQL MIG scaled to {target_size} (mocked).")
        return True

    # 1. compute_v1 クライアントライブラリ
    if compute_module is not None:
        try:
            client = compute_module.RegionInstanceGroupManagersClient()
            op = client.resize(
                project=project,
                region=reg,
                instance_group_manager=mig,
                size=target_size,
            )
            logger.info(
                f"Resize operation submitted via compute_v1: {getattr(op, 'name', op)}"
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to resize ProxySQL MIG via compute_v1: {e}")

    # 2. REST API フォールバック
    token_fn = get_token_callback or get_gcp_access_token
    if _resize_mig_via_rest(project, reg, mig, target_size, token_fn()):
        return True

    logger.error(
        f"Failed to resize ProxySQL MIG '{mig}' to size {target_size} (all methods failed)."
    )
    return False


def wait_for_proxysql_health(
    host: str | None = None,
    port: int | None = None,
    timeout_sec: int = 120,
) -> bool:
    """ProxySQL のポート (6033) 疎通を確認 (起動チェック)."""
    target_host = host or os.getenv("DB_HOST", "127.0.0.1")
    target_port = int(port or os.getenv("DB_PORT", "6033"))

    if not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        logger.info(
            f"[Local/Test] Skipping remote ProxySQL wait, checking {target_host}:{target_port}..."
        )
        return True

    logger.info(
        f"Waiting for ProxySQL health at {target_host}:{target_port} (timeout: {timeout_sec}s)..."
    )
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with socket.create_connection((target_host, target_port), timeout=2.0):
                logger.info(
                    f"ProxySQL is healthy and reachable at {target_host}:{target_port}!"
                )
                return True
        except OSError:
            time.sleep(2)

    logger.warning(
        f"ProxySQL connection wait timed out ({timeout_sec}s). Proceeding with caution."
    )
    return False

