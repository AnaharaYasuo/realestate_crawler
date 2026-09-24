"""GCP リソース管理共通ユーティリティ (ProxySQL MIG, GCE, Auth)."""

from collections.abc import Callable
import logging
import os
import shutil
import subprocess
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
            return str(resp.json().get("access_token"))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Metadata server token not available: {e}")
    return None


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
        os.getenv("IS_CLOUD")
        or os.getenv("K_SERVICE")
        or os.getenv("CLOUD_RUN_JOB")
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
                region_instance_group_manager=mig,
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
    token = token_fn()
    if token:
        url = f"https://compute.googleapis.com/compute/v1/projects/{project}/regions/{reg}/instanceGroupManagers/{mig}/resize?size={target_size}"
        try:
            resp = requests.post(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=10
            )
            if resp.status_code in (200, 204):
                logger.info(
                    f"Resize operation submitted via REST API: HTTP {resp.status_code}"
                )
                return True
            logger.error(
                f"REST API resize failed: HTTP {resp.status_code} - {resp.text}"
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"REST API resize request error: {e}")

    # 3. gcloud CLI フォールバック (CLIが存在する場合のみ)
    if shutil.which("gcloud"):
        cmd = [
            "gcloud",
            "compute",
            "instance-groups",
            "managed",
            "resize",
            mig,
            f"--size={target_size}",
            f"--region={reg}",
            f"--project={project}",
            "--quiet",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                logger.info("Resize operation succeeded via gcloud CLI.")
                return True
            logger.error(f"gcloud resize failed: {res.stderr}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"gcloud execution error: {e}")

    logger.error(
        f"Failed to resize ProxySQL MIG '{mig}' to size {target_size} (all methods failed)."
    )
    return False
