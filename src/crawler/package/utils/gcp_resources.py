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


def get_gcp_access_token(scopes: list[str] | None = None) -> str | None:
    """GCP 認証トークンを取得 (google.auth または メタデータサーバー経由)"""
    target_scopes = scopes or ["https://www.googleapis.com/auth/cloud-platform"]
    if google is not None:
        try:
            credentials, _ = google.auth.default(scopes=target_scopes)
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


def _resize_via_compute_client(
    compute_module: Any, project: str, reg: str, mig: str, target_size: int
) -> bool:
    if compute_module is None:
        return False
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
        return False


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


def _patch_autoscaler_via_compute_v1(
    compute_module: Any,
    project: str,
    region: str,
    auto_name: str,
    min_replicas: int,
    max_replicas: int,
) -> bool:
    if compute_module is None or not hasattr(compute_module, "RegionAutoscalersClient"):
        return False
    try:
        auto_client = compute_module.RegionAutoscalersClient()
        policy_cls = getattr(compute_module, "AutoscalingPolicy", None)
        auto_cls = getattr(compute_module, "Autoscaler", None)
        request_cls = getattr(compute_module, "PatchRegionAutoscalerRequest", None)
        policy = (
            policy_cls(min_num_replicas=min_replicas, max_num_replicas=max_replicas)
            if policy_cls
            else None
        )
        resource = auto_cls(autoscaling_policy=policy) if auto_cls else None
        if request_cls is not None:
            req = request_cls(
                project=project,
                region=region,
                autoscaler=auto_name,
                autoscaler_resource=resource,
            )
            op = auto_client.patch(request=req, timeout=10.0)
        else:
            op = auto_client.patch(
                project=project,
                region=region,
                autoscaler=auto_name,
                autoscaler_resource=resource,
                timeout=10.0,
            )
        if hasattr(op, "result") and callable(op.result):
            op.result(timeout=15.0)
        logger.info(
            f"Patched ProxySQL Autoscaler '{auto_name}' to min={min_replicas}, max={max_replicas} via compute_v1."
        )
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to patch autoscaler via compute_v1: {e}")
        return False


def _patch_autoscaler_via_rest(
    project: str,
    region: str,
    auto_name: str,
    min_replicas: int,
    max_replicas: int,
    token: str | None,
) -> bool:
    if not token:
        return False
    patch_url = f"https://compute.googleapis.com/compute/v1/projects/{project}/regions/{region}/autoscalers"
    params = {"autoscaler": auto_name}
    body = {
        "autoscalingPolicy": {
            "minNumReplicas": min_replicas,
            "maxNumReplicas": max_replicas,
        }
    }
    try:
        resp = requests.patch(
            patch_url,
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code in (200, 204):
            logger.info(
                f"Patched ProxySQL Autoscaler '{auto_name}' to min={min_replicas}, max={max_replicas} via REST API."
            )
            return True
        logger.warning(
            f"REST API patch autoscaler failed: HTTP {resp.status_code} - {resp.text}"
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"REST API patch autoscaler request error: {e}")
    return False


def patch_proxysql_autoscaler(
    min_replicas: int = 1,
    max_replicas: int = 2,
    project_id: str | None = None,
    region: str | None = None,
    autoscaler_name: str | None = None,
    dry_run: bool = False,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> bool:
    """ProxySQL MIG の Autoscaler 設定 (min_replicas, max_replicas) を更新。"""
    if dry_run or not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        logger.info(
            f"[Dry-run/Local] ProxySQL Autoscaler min={min_replicas}, max={max_replicas} (mocked)."
        )
        return True

    if os.getenv("PROXYSQL_INSTANCE_NAME"):
        logger.info(
            "[Single Instance Mode] ProxySQL Autoscaler patch skipped (managed as single GCE instance)."
        )
        return True

    project = (
        project_id
        or os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    )
    reg = region or os.getenv("GCP_REGION", "asia-northeast1")
    auto_name = autoscaler_name or os.getenv(
        "PROXYSQL_AUTOSCALER_NAME",
        f"proxysql-autoscaler-{os.getenv('ENVIRONMENT', 'prod')}",
    )

    if _patch_autoscaler_via_compute_v1(
        compute_module, project, reg, auto_name, min_replicas, max_replicas
    ):
        return True

    token_fn = get_token_callback or get_gcp_access_token
    token = token_fn()
    return _patch_autoscaler_via_rest(
        project, reg, auto_name, min_replicas, max_replicas, token
    )


def _extract_autoscaler_name(autoscaler_url_or_name: Any) -> str | None:
    if not autoscaler_url_or_name or not isinstance(autoscaler_url_or_name, str):
        return None
    val = autoscaler_url_or_name.strip()
    if not val:
        return None
    return val.rstrip("/").split("/")[-1]


def _get_mig_via_compute_client(
    compute_module: Any, project_id: str, region: str, mig_name: str
) -> tuple[int, str, str | None]:
    if compute_module is None or not hasattr(
        compute_module, "RegionInstanceGroupManagersClient"
    ):
        return -1, "No compute client", None
    try:
        client = compute_module.RegionInstanceGroupManagersClient()
        igm = client.get(
            project=project_id,
            region=region,
            instance_group_manager=mig_name,
            timeout=10.0,
        )
        raw_size = getattr(igm, "target_size", 0)
        target_size = int(raw_size) if isinstance(raw_size, (int, float)) else 0
        status_obj = getattr(igm, "status", None)
        autoscaler_val = (
            getattr(status_obj, "autoscaler", None) if status_obj is not None else None
        )
        autoscaler = autoscaler_val if isinstance(autoscaler_val, str) else None
        return target_size, "", autoscaler
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to get MIG info via compute_v1: {e}")
        return -1, str(e), None


def _get_mig_via_rest(
    project_id: str, region: str, mig_name: str, token: str | None
) -> tuple[int, str, str | None]:
    if not token:
        return -1, "No GCP token", None
    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/instanceGroupManagers/{mig_name}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code != 200:
            return -1, f"HTTP {resp.status_code}: {resp.text}", None
        data = resp.json()
        target_size = int(data.get("targetSize", 0))
        autoscaler_val = data.get("status", {}).get("autoscaler") or data.get(
            "autoscaler"
        )
        autoscaler = autoscaler_val if isinstance(autoscaler_val, str) else None
        return target_size, "", autoscaler
    except Exception as e:  # noqa: BLE001
        return -1, str(e), None


def get_mig_info(
    project_id: str,
    region: str,
    mig_name: str,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> tuple[int, str, str | None]:
    """Retrieve MIG target_size, error message, and attached autoscaler."""
    target_size, err, autoscaler = _get_mig_via_compute_client(
        compute_module, project_id, region, mig_name
    )
    if not err:
        return target_size, "", autoscaler

    token_fn = get_token_callback or get_gcp_access_token
    token = token_fn()
    rest_size, rest_err, rest_auto = _get_mig_via_rest(
        project_id, region, mig_name, token
    )
    if not rest_err:
        return rest_size, "", rest_auto

    return -1, f"{err}; {rest_err}", None


def _is_prefix_matched(name: str, prefix: str) -> bool:
    """Check if instance name equals prefix or starts with prefix followed by hyphen."""
    return name == prefix or name.startswith(f"{prefix}-")


def _evaluate_sql_instances_matches(
    all_matches: list[dict], prefix: str
) -> tuple[bool, str]:
    """Evaluate matched Cloud SQL instances count and return status tuple."""
    if len(all_matches) == 1:
        inst = all_matches[0]
        state = inst.get("state", "UNKNOWN")
        act_policy = inst.get("settings", {}).get("activationPolicy", "UNKNOWN")
        logger.info(
            f"Cloud SQL '{inst.get('name')}' (prefix '{prefix}') state: {state}, activationPolicy: {act_policy}"
        )
        return state == "RUNNABLE", state
    if len(all_matches) > 1:
        logger.warning(
            f"Multiple Cloud SQL instances match prefix '{prefix}': {[m.get('name') for m in all_matches]}"
        )
        return False, "MULTIPLE_MATCHES"
    return False, "HTTP 404"


def _fetch_cloud_sql_instances_by_prefix(
    project: str, prefix: str, token: str
) -> tuple[list[dict] | None, str | None]:
    """Fetch and filter Cloud SQL instances matching prefix via REST API pagination."""
    page_token = None
    all_matches = []
    while True:
        list_url = f"https://sqladmin.googleapis.com/v1/projects/{project}/instances"
        params = {"pageToken": page_token} if page_token else None
        resp = requests.get(
            list_url,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=5,
        )
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"

        data = resp.json()
        for inst in data.get("items", []):
            if _is_prefix_matched(inst.get("name", ""), prefix):
                all_matches.append(inst)

        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return all_matches, None


def _find_cloud_sql_by_prefix(
    project: str, prefix: str, token: str
) -> tuple[bool, str]:
    """Find Cloud SQL instance whose name matches prefix (e.g. realestate-mysql-prod-*) on 404."""
    try:
        matches, err = _fetch_cloud_sql_instances_by_prefix(project, prefix, token)
        if err is not None:
            return False, err
        return _evaluate_sql_instances_matches(matches or [], prefix)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Failed to list Cloud SQL instances for prefix match '{prefix}': {e}"
        )
        return False, str(e)


def check_cloud_sql_status(
    project_id: str | None = None,
    instance_name: str | None = None,
    dry_run: bool = False,
    get_token_callback: Callable[[], str | None] | None = None,
) -> tuple[bool, str]:
    """Check Cloud SQL instance state (RUNNABLE)."""
    if dry_run or not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        return True, "RUNNABLE (mocked)"

    project = (
        project_id
        or os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    )
    instance = instance_name or os.getenv(
        "CLOUDSQL_INSTANCE_NAME", "realestate-mysql-prod"
    )
    token_fn = get_token_callback or (
        lambda: get_gcp_access_token(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    )
    token = token_fn()
    if not token:
        logger.error("No GCP token available for Cloud SQL status check.")
        return False, "UNKNOWN (no token)"

    url = f"https://sqladmin.googleapis.com/v1/projects/{project}/instances/{instance}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            state = data.get("state", "UNKNOWN")
            act_policy = data.get("settings", {}).get("activationPolicy", "UNKNOWN")
            logger.info(
                f"Cloud SQL '{instance}' state: {state}, activationPolicy: {act_policy}"
            )
            return state == "RUNNABLE", state
        if resp.status_code == 404:
            return _find_cloud_sql_by_prefix(project, instance, token)
        logger.error(f"Cloud SQL API returned HTTP {resp.status_code}: {resp.text}")
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        logger.exception("Cloud SQL status check failed")
        return False, str(e)


def _scale_direct_mig(
    compute_module: Any,
    project: str,
    reg: str,
    mig: str,
    target_size: int,
    get_token_callback: Callable[[], str | None] | None,
) -> bool:
    if _resize_via_compute_client(compute_module, project, reg, mig, target_size):
        return True
    token_fn = get_token_callback or get_gcp_access_token
    if _resize_mig_via_rest(project, reg, mig, target_size, token_fn()):
        return True
    logger.error(
        f"Failed to resize ProxySQL MIG '{mig}' to size {target_size} (all methods failed)."
    )
    return False


def get_instance_status(
    project_id: str,
    zone: str,
    instance_name: str,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> tuple[str, str]:
    """Retrieve Compute Engine instance status (e.g. 'RUNNING', 'TERMINATED') and error message."""
    last_err = ""
    if compute_module is not None and hasattr(compute_module, "InstancesClient"):
        try:
            client = compute_module.InstancesClient()
            inst = client.get(
                project=project_id,
                zone=zone,
                instance=instance_name,
                timeout=10.0,
            )
            raw_status = getattr(inst, "status", "")
            return str(raw_status), ""
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to get instance status via compute_v1: {e}")
            last_err = str(e)
    else:
        last_err = "compute_v1 not available"

    token_fn = get_token_callback or get_gcp_access_token
    token = token_fn()
    if not token:
        return "UNKNOWN", f"{last_err}; No GCP token"

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/instances/{instance_name}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return str(data.get("status", "UNKNOWN")), ""
        return "UNKNOWN", f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:  # noqa: BLE001
        return "UNKNOWN", str(e)


def _execute_instance_action(
    action: str,
    project: str,
    zone: str,
    instance_name: str,
    compute_module: Any,
    token_fn: Callable[[], str | None],
) -> bool:
    """Execute start/stop action via compute_v1 or fallback to REST API."""
    if compute_module is not None and hasattr(compute_module, "InstancesClient"):
        try:
            client = compute_module.InstancesClient()
            method = getattr(client, action)
            op = method(
                project=project,
                zone=zone,
                instance=instance_name,
            )
            logger.info(
                f"Instance {action} operation submitted via compute_v1: {getattr(op, 'name', op)}"
            )
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to {action} instance via compute_v1: {e}")

    token = token_fn()
    if not token:
        logger.error(
            f"No GCP access token available to {action} ProxySQL instance via REST."
        )
        return False

    url = f"https://compute.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances/{instance_name}/{action}"
    try:
        resp = requests.post(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code in (200, 204):
            logger.info(
                f"Instance {action} operation submitted via REST API: HTTP {resp.status_code}"
            )
            return True
        logger.error(f"REST API {action} failed: HTTP {resp.status_code} - {resp.text}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"REST API {action} request error: {e}")

    return False


def start_proxysql_instance(
    project_id: str | None = None,
    zone: str | None = None,
    instance_name: str | None = None,
    dry_run: bool = False,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> bool:
    """Start single ProxySQL Compute Engine instance."""
    project = (
        project_id
        or os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    )
    reg = os.getenv("GCP_REGION", "asia-northeast1")
    inst_zone = zone or os.getenv("PROXYSQL_ZONE", f"{reg}-b")
    inst_name = instance_name or os.getenv(
        "PROXYSQL_INSTANCE_NAME",
        f"proxysql-instance-{os.getenv('ENVIRONMENT', 'prod')}",
    )

    logger.info(
        f"Starting ProxySQL instance '{inst_name}' (project: {project}, zone: {inst_zone}, dry_run: {dry_run})"
    )
    if dry_run or not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        logger.info(
            f"[Dry-run/Local] ProxySQL instance '{inst_name}' started (mocked)."
        )
        return True

    status, _ = get_instance_status(
        project,
        inst_zone,
        inst_name,
        compute_module=compute_module,
        get_token_callback=get_token_callback,
    )
    if status == "RUNNING":
        logger.info(f"ProxySQL instance '{inst_name}' is already RUNNING.")
        return True

    return _execute_instance_action(
        "start",
        project,
        inst_zone,
        inst_name,
        compute_module,
        get_token_callback or get_gcp_access_token,
    )


def stop_proxysql_instance(
    project_id: str | None = None,
    zone: str | None = None,
    instance_name: str | None = None,
    dry_run: bool = False,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> bool:
    """Stop single ProxySQL Compute Engine instance."""
    project = (
        project_id
        or os.getenv("GCP_PROJECT")
        or os.getenv("GOOGLE_CLOUD_PROJECT", "sumifu")
    )
    reg = os.getenv("GCP_REGION", "asia-northeast1")
    inst_zone = zone or os.getenv("PROXYSQL_ZONE", f"{reg}-b")
    inst_name = instance_name or os.getenv(
        "PROXYSQL_INSTANCE_NAME",
        f"proxysql-instance-{os.getenv('ENVIRONMENT', 'prod')}",
    )

    logger.info(
        f"Stopping ProxySQL instance '{inst_name}' (project: {project}, zone: {inst_zone}, dry_run: {dry_run})"
    )
    if dry_run or not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        logger.info(
            f"[Dry-run/Local] ProxySQL instance '{inst_name}' stopped (mocked)."
        )
        return True

    status, _ = get_instance_status(
        project,
        inst_zone,
        inst_name,
        compute_module=compute_module,
        get_token_callback=get_token_callback,
    )
    if status in ("TERMINATED", "STOPPED", "STOPPING"):
        logger.info(f"ProxySQL instance '{inst_name}' is already {status}.")
        return True

    return _execute_instance_action(
        "stop",
        project,
        inst_zone,
        inst_name,
        compute_module,
        get_token_callback or get_gcp_access_token,
    )


def _delegate_to_single_instance(
    target_size: int,
    project: str,
    reg: str,
    instance_name: str,
    dry_run: bool,
    compute_module: Any,
    get_token_callback: Callable[[], str | None] | None,
) -> bool:
    """Delegate scale request to single ProxySQL instance."""
    zone = os.getenv("PROXYSQL_ZONE", f"{reg}-b")
    if target_size > 0:
        return start_proxysql_instance(
            project_id=project,
            zone=zone,
            instance_name=instance_name,
            dry_run=dry_run,
            compute_module=compute_module,
            get_token_callback=get_token_callback,
        )
    return stop_proxysql_instance(
        project_id=project,
        zone=zone,
        instance_name=instance_name,
        dry_run=dry_run,
        compute_module=compute_module,
        get_token_callback=get_token_callback,
    )


def scale_proxysql_mig(
    target_size: int = 1,
    project_id: str | None = None,
    region: str | None = None,
    mig_name: str | None = None,
    dry_run: bool = False,
    compute_module: Any = compute_v1,
    get_token_callback: Callable[[], str | None] | None = None,
) -> bool:
    """ProxySQL MIG または単一インスタンスのサイズを変更 (0 -> 1 または 1 -> 0)。

    PROXYSQL_INSTANCE_NAME 環境変数が設定されている場合は単一インスタンスの起動/停止を実行。
    Autoscaler 管理下の MIG の場合は patch_proxysql_autoscaler を呼出し、
    直接 resize API (GCPにより拒否される) の発行を回避する。
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

    # 単一インスタンス構成 (Direct VPC Egress 移行後) の自動委任
    instance_name = os.getenv("PROXYSQL_INSTANCE_NAME")
    if instance_name:
        return _delegate_to_single_instance(
            target_size,
            project,
            reg,
            instance_name,
            dry_run,
            compute_module,
            get_token_callback,
        )

    logger.info(
        f"Scaling ProxySQL MIG '{mig}' to size {target_size} (project: {project}, region: {reg}, dry_run: {dry_run})"
    )
    if dry_run or not bool(
        os.getenv("IS_CLOUD") or os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB")
    ):
        logger.info(f"[Dry-run/Local] ProxySQL MIG scaled to {target_size} (mocked).")
        return True

    # 1. Autoscaler 存在チェック (GCP は Autoscaler 管理下 MIG への直接 resize を禁止)
    _, err, autoscaler = get_mig_info(
        project,
        reg,
        mig,
        compute_module=compute_module,
        get_token_callback=get_token_callback,
    )
    auto_name = _extract_autoscaler_name(autoscaler)
    if not auto_name and err and os.getenv("PROXYSQL_AUTOSCALER_NAME"):
        auto_name = os.getenv("PROXYSQL_AUTOSCALER_NAME")

    if auto_name:
        min_rep = target_size
        max_rep = max(2, target_size) if target_size > 0 else 0
        logger.info(
            f"ProxySQL MIG is managed by Autoscaler '{auto_name}'. Adjusting min={min_rep}, max={max_rep}."
        )
        return patch_proxysql_autoscaler(
            min_replicas=min_rep,
            max_replicas=max_rep,
            project_id=project,
            region=reg,
            autoscaler_name=auto_name,
            dry_run=dry_run,
            compute_module=compute_module,
            get_token_callback=get_token_callback,
        )

    if err:
        logger.error(
            f"Failed to inspect ProxySQL MIG '{mig}' before scaling: {err}. Refusing to resize directly."
        )
        return False

    return _scale_direct_mig(
        compute_module, project, reg, mig, target_size, get_token_callback
    )


def wait_for_proxysql_health(
    host: str | None = None,
    port: int | None = None,
    timeout_sec: int = 240,
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
