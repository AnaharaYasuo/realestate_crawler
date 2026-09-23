"""
Safety-net script to ensure cloud resources (ProxySQL MIG, NAT, etc.) are stopped.
Designed to run at 05:00 JST daily (or on demand) to eliminate zombie resource costs.
"""
import argparse
import logging
import os
import sys
from dataclasses import dataclass

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401
        break
    _cur = _parent

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

try:
    from package.utils.slack import send_slack_message
except ImportError:
    send_slack_message = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ERR_NO_COMPUTE_CLIENT: str = "Neither google-cloud-compute nor valid GCP credentials available"


@dataclass
class ResourceInspectionResult:
    was_leaked: bool
    forced_stop: bool
    leaked_size: int
    details: str = ""


def send_slack_alert(message: str, channel: str | None = None) -> None:
    target_channel = channel or os.environ.get("SLACK_ALERT_PROPERTY_ALERT", "property_alert")
    if send_slack_message is not None:
        try:
            send_slack_message(channel=target_channel, message=message)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to send Slack alert: {e}")
    else:
        logger.info(f"[Slack Alert Placeholder ({target_channel})]: {message}")


def _get_gcp_access_token() -> str | None:
    if google is not None:
        try:
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/compute"])
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


def _extract_autoscaler_name(autoscaler_url_or_name: str | None) -> str | None:
    if not autoscaler_url_or_name:
        return None
    return autoscaler_url_or_name.rstrip("/").split("/")[-1]


def _get_mig_info(project_id: str, region: str, mig_name: str) -> tuple[int, str, str | None]:
    if compute_v1 is not None:
        try:
            client = compute_v1.RegionInstanceGroupManagersClient()
            igm = client.get(
                project=project_id,
                region=region,
                region_instance_group_manager=mig_name,
                timeout=10.0,
            )
            target_size = int(igm.target_size or 0)
            autoscaler = getattr(getattr(igm, "status", None), "autoscaler", None)
            return target_size, "", autoscaler
        except Exception as e:  # noqa: BLE001
            return -1, str(e), None

    token = _get_gcp_access_token()
    if not token:
        return -1, ERR_NO_COMPUTE_CLIENT, None

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/instanceGroupManagers/{mig_name}"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.status_code != 200:
            return -1, f"HTTP {resp.status_code}: {resp.text}", None
        data = resp.json()
        target_size = int(data.get("targetSize", 0))
        autoscaler = data.get("status", {}).get("autoscaler") or data.get("autoscaler")
        return target_size, "", autoscaler
    except Exception as e:  # noqa: BLE001
        return -1, str(e), None


def _stop_autoscaler(project_id: str, region: str, autoscaler_name: str) -> str:
    """Sets autoscaler min_num_replicas and max_num_replicas to 0."""
    if compute_v1 is not None and hasattr(compute_v1, "RegionAutoscalersClient"):
        try:
            auto_client = compute_v1.RegionAutoscalersClient()
            policy_cls = getattr(compute_v1, "AutoscalingPolicy", None)
            auto_cls = getattr(compute_v1, "Autoscaler", None)
            policy = policy_cls(min_num_replicas=0, max_num_replicas=0) if policy_cls else None
            resource = auto_cls(autoscaling_policy=policy) if auto_cls else None
            auto_client.patch(
                project=project_id,
                region=region,
                autoscaler=autoscaler_name,
                autoscaler_resource=resource,
                timeout=10.0,
            )
            return ""
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to patch autoscaler via compute_v1: {e}")

    token = _get_gcp_access_token()
    if not token:
        return ERR_NO_COMPUTE_CLIENT

    patch_url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/autoscalers/{autoscaler_name}"
    body = {"autoscalingPolicy": {"minNumReplicas": 0, "maxNumReplicas": 0}}
    try:
        resp = requests.patch(patch_url, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.status_code in (200, 204):
            return ""
        return f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:  # noqa: BLE001
        return str(e)


def _resize_mig_to_zero(project_id: str, region: str, mig_name: str) -> str:
    if compute_v1 is not None:
        try:
            client = compute_v1.RegionInstanceGroupManagersClient()
            client.resize(
                project=project_id,
                region=region,
                region_instance_group_manager=mig_name,
                size=0,
                timeout=10.0,
            )
            return ""
        except Exception as e:  # noqa: BLE001
            return str(e)

    token = _get_gcp_access_token()
    if not token:
        return ERR_NO_COMPUTE_CLIENT

    resize_url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/instanceGroupManagers/{mig_name}/resize?size=0"
    try:
        resp = requests.post(resize_url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.status_code not in (200, 204):
            return f"HTTP {resp.status_code}: {resp.text}"
        return ""
    except Exception as e:  # noqa: BLE001
        return str(e)


def check_and_stop_proxysql_mig(
    project_id: str,
    region: str,
    mig_name: str,
    dry_run: bool = False,
) -> ResourceInspectionResult:
    """
    Checks if ProxySQL MIG target_size > 0. If leaked, forcibly stops it and notifies Slack.
    Uses autoscaler scale-to-zero when autoscaler is attached, otherwise MIG resize.
    """
    current_target_size, err, autoscaler = _get_mig_info(project_id, region, mig_name)
    if err:
        err_msg = f":rotating_light: *【緊急】ProxySQL MIG状態取得失敗*: {err}"
        logger.error(err_msg)
        send_slack_alert(err_msg)
        return ResourceInspectionResult(was_leaked=True, forced_stop=False, leaked_size=-1, details=err)

    logger.info(f"ProxySQL MIG '{mig_name}' current target_size: {current_target_size}")

    if current_target_size == 0:
        logger.info("ProxySQL MIG is safely stopped (target_size = 0).")
        return ResourceInspectionResult(was_leaked=False, forced_stop=False, leaked_size=0)

    # Leak detected!
    warning_msg = (
        f":warning: *【ゾンビ課金アラート】ProxySQL MIG停止漏れ検知*\n"
        f"・プロジェクト: `{project_id}`\n"
        f"・リージョン: `{region}`\n"
        f"・MIG名: `{mig_name}`\n"
        f"・検知時サイズ: `{current_target_size}` 台\n"
        f"・処置: {'[DRY-RUN] 停止スキップ' if dry_run else '自動強制停止 (size -> 0) を実行しました。'}"
    )
    logger.warning(warning_msg)
    send_slack_alert(warning_msg)

    if dry_run:
        return ResourceInspectionResult(was_leaked=True, forced_stop=False, leaked_size=current_target_size)

    auto_name = _extract_autoscaler_name(autoscaler)
    if auto_name:
        logger.info(f"MIG is managed by autoscaler '{auto_name}'. Scaling autoscaler to 0.")
        stop_err = _stop_autoscaler(project_id, region, auto_name)
    else:
        stop_err = _resize_mig_to_zero(project_id, region, mig_name)

    if not stop_err:
        logger.info(f"Successfully stopped ProxySQL MIG '{mig_name}'.")
        return ResourceInspectionResult(was_leaked=True, forced_stop=True, leaked_size=current_target_size)

    err_msg = f"Failed to stop ProxySQL MIG '{mig_name}': {stop_err}"
    logger.error(err_msg)
    send_slack_alert(f":rotating_light: *【緊急】ProxySQL MIGの強制停止に失敗しました*: {err_msg}")
    return ResourceInspectionResult(
        was_leaked=True, forced_stop=False, leaked_size=current_target_size, details=stop_err
    )



def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure GCP on-demand resources are safely stopped.")
    parser.add_argument(
        "--project-id",
        default=os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "sumifu")),
        help="GCP Project ID",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("GCP_REGION", "asia-northeast1"),
        help="GCP Region",
    )
    parser.add_argument(
        "--mig-name",
        default=os.environ.get("PROXYSQL_MIG_NAME", "proxysql-mig-prod"),
        help="ProxySQL Region IGM Name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check only without resizing",
    )

    args = parser.parse_args()

    logger.info("=== [START] Checking for leaked GCP resources ===")
    result = check_and_stop_proxysql_mig(
        project_id=args.project_id,
        region=args.region,
        mig_name=args.mig_name,
        dry_run=args.dry_run,
    )

    if result.was_leaked:
        if result.forced_stop:
            logger.warning(f"Leaked resource detected and forcibly stopped: {result.leaked_size} instances.")
            return 0
        logger.error(f"Leaked resource detected but failed to stop: {result.details}")
        return 1

    logger.info("=== [FINISH] All checked resources are safely stopped. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
