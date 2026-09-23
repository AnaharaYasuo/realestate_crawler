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

try:
    from google.cloud import compute_v1
except ImportError:
    compute_v1 = None

try:
    from package.utils.slack import send_slack_message
except ImportError:
    send_slack_message = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


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


def check_and_stop_proxysql_mig(
    project_id: str,
    region: str,
    mig_name: str,
    dry_run: bool = False,
) -> ResourceInspectionResult:
    """
    Checks if ProxySQL MIG target_size > 0. If leaked, forcibly resizes to 0 and notifies Slack.
    """
    if compute_v1 is None:
        logger.error("google-cloud-compute is not installed. Skipping GCP inspection.")
        return ResourceInspectionResult(was_leaked=False, forced_stop=False, leaked_size=0, details="SDK missing")

    client = compute_v1.RegionInstanceGroupManagersClient()

    try:
        igm = client.get(
            project=project_id,
            region=region,
            region_instance_group_manager=mig_name,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Failed to get IGM '{mig_name}' in region '{region}': {e}")
        return ResourceInspectionResult(was_leaked=False, forced_stop=False, leaked_size=0, details=str(e))

    current_target_size = igm.target_size or 0
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

    try:
        client.resize(
            project=project_id,
            region=region,
            region_instance_group_manager=mig_name,
            size=0,
        )
        logger.info(f"Successfully resized ProxySQL MIG '{mig_name}' to 0.")
        return ResourceInspectionResult(was_leaked=True, forced_stop=True, leaked_size=current_target_size)
    except Exception as e:  # noqa: BLE001
        err_msg = f"Failed to resize ProxySQL MIG '{mig_name}' to 0: {e}"
        logger.error(err_msg)
        send_slack_alert(f":rotating_light: *【緊急】ProxySQL MIGの強制停止に失敗しました*: {err_msg}")
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=False, leaked_size=current_target_size, details=str(e)
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
