"""
Safety-net script to ensure cloud resources (ProxySQL MIG, NAT, etc.) are stopped.
Designed to run at 05:00 JST daily (or on demand) to eliminate zombie resource costs.
"""

import argparse
import asyncio
import inspect
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

from datetime import datetime, timezone

import requests

try:
    from asgiref.sync import async_to_sync
except ImportError:
    async_to_sync = None

try:
    from google.cloud import compute_v1
except ImportError:
    compute_v1 = None

try:
    from google.cloud import run_v2
except ImportError:
    run_v2 = None

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

ERR_NO_COMPUTE_CLIENT: str = (
    "Neither google-cloud-compute nor valid GCP credentials available"
)


@dataclass
class ResourceInspectionResult:
    was_leaked: bool
    forced_stop: bool
    leaked_size: int
    details: str = ""
    skipped_reason: str = ""
    canceled_jobs: list[str] | None = None


@dataclass
class CloudRunExecutionInfo:
    name: str
    job_name: str
    elapsed_sec: float | None = None


def send_slack_alert(message: str, channel: str | None = None) -> None:
    target_channel = channel or os.environ.get(
        "SLACK_ALERT_PROPERTY_ALERT", "property_alert"
    )
    if send_slack_message is not None:
        try:
            if inspect.iscoroutinefunction(send_slack_message):
                if async_to_sync is not None:
                    async_to_sync(send_slack_message)(
                        channel=target_channel, message=message
                    )
                else:
                    asyncio.run(
                        send_slack_message(channel=target_channel, message=message)
                    )
            else:
                res = send_slack_message(channel=target_channel, message=message)
                if inspect.isawaitable(res):
                    asyncio.run(res)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to send Slack alert: {e}")
    else:
        logger.info(f"[Slack Alert Placeholder ({target_channel})]: {message}")


def _get_gcp_access_token() -> str | None:
    if google is not None:
        try:
            credentials, _ = google.auth.default(
                scopes=[
                    "https://www.googleapis.com/auth/compute",
                    "https://www.googleapis.com/auth/cloud-platform",
                ]
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


def _extract_autoscaler_name(autoscaler_url_or_name: str | None) -> str | None:
    if not autoscaler_url_or_name:
        return None
    return autoscaler_url_or_name.rstrip("/").split("/")[-1]


def _get_mig_info(
    project_id: str, region: str, mig_name: str
) -> tuple[int, str, str | None]:
    last_err = ""
    if compute_v1 is not None:
        try:
            client = compute_v1.RegionInstanceGroupManagersClient()
            igm = client.get(
                project=project_id,
                region=region,
                instance_group_manager=mig_name,
                timeout=10.0,
            )
            target_size = int(igm.target_size or 0)
            autoscaler = getattr(getattr(igm, "status", None), "autoscaler", None)
            return target_size, "", autoscaler
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            logger.warning(f"Failed to get MIG info via compute_v1: {e}")

    token = _get_gcp_access_token()
    if not token:
        return -1, last_err or ERR_NO_COMPUTE_CLIENT, None

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/instanceGroupManagers/{mig_name}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code != 200:
            return -1, f"HTTP {resp.status_code}: {resp.text}", None
        data = resp.json()
        target_size = data.get("targetSize")
        if not isinstance(target_size, int) or isinstance(target_size, bool):
            return -1, "REST response has missing or invalid targetSize", None
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
            request_cls = getattr(compute_v1, "PatchRegionAutoscalerRequest", None)
            policy = (
                policy_cls(min_num_replicas=0, max_num_replicas=0)
                if policy_cls
                else None
            )
            resource = auto_cls(autoscaling_policy=policy) if auto_cls else None
            if request_cls is not None:
                req = request_cls(
                    project=project_id,
                    region=region,
                    autoscaler=autoscaler_name,
                    autoscaler_resource=resource,
                )
                auto_client.patch(request=req, timeout=10.0)
            else:
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

    patch_url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/autoscalers"
    params = {"autoscaler": autoscaler_name}
    body = {"autoscalingPolicy": {"minNumReplicas": 0, "maxNumReplicas": 0}}
    try:
        resp = requests.patch(
            patch_url,
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code in (200, 204):
            return ""
        return f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:  # noqa: BLE001
        return str(e)


def _parse_timestamp_to_seconds_ago(timestamp_str: str | None) -> float | None:
    if not timestamp_str:
        return None
    try:
        ts = str(timestamp_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0.0, (now - dt).total_seconds())
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return None



def _get_mig_uptime_seconds(
    project_id: str, region: str, mig_name: str
) -> float | None:
    """Returns minimum uptime in seconds of instances in the MIG, or None if unknown/empty."""
    if compute_v1 is not None and hasattr(
        compute_v1, "RegionInstanceGroupManagersClient"
    ):
        try:
            client = compute_v1.RegionInstanceGroupManagersClient()
            req_cls = getattr(
                compute_v1,
                "ListManagedInstancesRegionInstanceGroupManagersRequest",
                None,
            )
            if req_cls is not None:
                req = req_cls(
                    project=project_id,
                    region=region,
                    instance_group_manager=mig_name,
                )
                resp = client.list_managed_instances(request=req, timeout=10.0)
            else:
                resp = client.list_managed_instances(
                    project=project_id,
                    region=region,
                    instance_group_manager=mig_name,
                    timeout=10.0,
                )
            uptimes = []
            for item in getattr(resp, "managed_instances", resp):
                ts = getattr(item, "creation_timestamp", None) or getattr(
                    getattr(item, "instance_status", None), "creation_timestamp", None
                )
                sec = _parse_timestamp_to_seconds_ago(ts)
                if sec is not None:
                    uptimes.append(sec)
            if uptimes:
                return min(uptimes)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Failed to list managed instances via compute_v1: {e}")

    token = _get_gcp_access_token()
    if not token:
        return None

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/instanceGroupManagers/{mig_name}/listManagedInstances"
    try:
        resp = requests.post(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            uptimes = []
            for item in data.get("managedInstances", []):
                ts = item.get("creationTimestamp") or item.get(
                    "instanceStatus", {}
                ).get("creationTimestamp")
                sec = _parse_timestamp_to_seconds_ago(ts)
                if sec is not None:
                    uptimes.append(sec)
            if uptimes:
                return min(uptimes)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to list managed instances via REST API: {e}")
    return None


def _get_active_cloud_run_executions(
    project_id: str,
    region: str,
    job_prefixes: tuple[str, ...],
) -> tuple[list[CloudRunExecutionInfo], str]:
    """Returns (active_executions, error_message). On failure, error_message is non-empty."""
    active_jobs: list[CloudRunExecutionInfo] = []
    last_err: str = ""

    # 1. Try run_v2 ExecutionsClient
    if run_v2 is not None and hasattr(run_v2, "ExecutionsClient"):
        try:
            client = run_v2.ExecutionsClient()
            jobs_client = getattr(run_v2, "JobsClient", None)
            matched_job_names = []
            run_v2_has_error = False
            if jobs_client is not None:
                try:
                    jc = jobs_client()
                    for job_obj in jc.list_jobs(
                        parent=f"projects/{project_id}/locations/{region}",
                        timeout=10.0,
                    ):
                        j_short = getattr(job_obj, "name", "").split("/")[-1]
                        if any(j_short.startswith(p) for p in job_prefixes):
                            matched_job_names.append(job_obj.name)
                except Exception as je:  # noqa: BLE001
                    logger.debug(f"Failed to list jobs via run_v2 JobsClient: {je}")
                    run_v2_has_error = True
                    last_err = str(je)

            req_cls = getattr(run_v2, "ListExecutionsRequest", None)
            parents = matched_job_names or [
                f"projects/{project_id}/locations/{region}/jobs/{prefix}"
                for prefix in job_prefixes
            ]
            run_v2_active: list[CloudRunExecutionInfo] = []
            for parent in parents:
                try:
                    if req_cls is not None:
                        resp = client.list_executions(
                            request=req_cls(parent=parent), timeout=10.0
                        )
                    else:
                        resp = client.list_executions(parent=parent, timeout=10.0)
                    for ex in resp:
                        completion_time = getattr(ex, "completion_time", None)
                        cancelled = getattr(ex, "cancelled", False)
                        if not completion_time and not cancelled:
                            create_time = getattr(ex, "create_time", None)
                            elapsed = (
                                _parse_timestamp_to_seconds_ago(str(create_time))
                                if create_time
                                else None
                            )
                            name = getattr(ex, "name", "")
                            job_name = (
                                name.split("/jobs/")[1].split("/")[0]
                                if "/jobs/" in name
                                else parent.split("/")[-1]
                            )
                            run_v2_active.append(
                                CloudRunExecutionInfo(
                                    name=name,
                                    job_name=job_name,
                                    elapsed_sec=elapsed,
                                )
                            )
                except Exception as inner_e:  # noqa: BLE001
                    logger.debug(
                        f"Could not list executions for job parent {parent}: {inner_e}"
                    )
                    run_v2_has_error = True
                    last_err = str(inner_e)
            if not run_v2_has_error:
                return run_v2_active, ""
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            logger.debug(f"Failed to list executions via run_v2: {e}")

    # 2. REST API fallback
    token = _get_gcp_access_token()
    if not token:
        return active_jobs, last_err or ERR_NO_COMPUTE_CLIENT

    headers = {"Authorization": f"Bearer {token}"}
    try:
        jobs_url = f"https://run.googleapis.com/v2/projects/{project_id}/locations/{region}/jobs"
        j_resp = requests.get(jobs_url, headers=headers, timeout=10)
        if j_resp.status_code != 200:
            return active_jobs, f"HTTP {j_resp.status_code} listing jobs: {j_resp.text}"

        jobs_data = j_resp.json().get("jobs", [])
        for j in jobs_data:
            j_full_name = j.get("name", "")
            j_short_name = j_full_name.rstrip("/").split("/")[-1]
            if any(j_short_name.startswith(p) for p in job_prefixes):
                exec_url = f"https://run.googleapis.com/v2/{j_full_name}/executions"
                e_resp = requests.get(exec_url, headers=headers, timeout=10)
                if e_resp.status_code != 200:
                    return (
                        active_jobs,
                        f"HTTP {e_resp.status_code} listing executions for {j_short_name}: {e_resp.text}",
                    )
                for ex in e_resp.json().get("executions", []):
                    is_completed = bool(ex.get("completionTime"))
                    is_cancelled = bool(ex.get("cancelled"))
                    if not is_completed and not is_cancelled:
                        create_ts = ex.get("createTime") or ex.get("startTime")
                        elapsed = _parse_timestamp_to_seconds_ago(create_ts)
                        active_jobs.append(
                            CloudRunExecutionInfo(
                                name=ex.get("name", ""),
                                job_name=j_short_name,
                                elapsed_sec=elapsed,
                            )
                        )
        return active_jobs, ""
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to query Cloud Run Executions via REST: {e}")
        return active_jobs, str(e)


def _cancel_cloud_run_execution(execution_name: str) -> str:
    """Cancels a Cloud Run Job Execution."""
    if run_v2 is not None and hasattr(run_v2, "ExecutionsClient"):
        try:
            client = run_v2.ExecutionsClient()
            req_cls = getattr(run_v2, "CancelExecutionRequest", None)
            if req_cls is not None:
                client.cancel_execution(
                    request=req_cls(name=execution_name), timeout=10.0
                )
            else:
                client.cancel_execution(name=execution_name, timeout=10.0)
            return ""
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Failed to cancel execution via run_v2: {e}")

    token = _get_gcp_access_token()
    if not token:
        return ERR_NO_COMPUTE_CLIENT

    url = f"https://run.googleapis.com/v2/{execution_name}:cancel"
    try:
        resp = requests.post(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code in (200, 204):
            return ""
        return f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:  # noqa: BLE001
        return str(e)


def _resize_mig_to_zero(project_id: str, region: str, mig_name: str) -> str:
    last_err = ""
    if compute_v1 is not None:
        try:
            client = compute_v1.RegionInstanceGroupManagersClient()
            client.resize(
                project=project_id,
                region=region,
                instance_group_manager=mig_name,
                size=0,
                timeout=10.0,
            )
            return ""
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            logger.warning(f"Failed to resize MIG via compute_v1: {e}")

    token = _get_gcp_access_token()
    if not token:
        return last_err or ERR_NO_COMPUTE_CLIENT

    resize_url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/instanceGroupManagers/{mig_name}/resize?size=0"
    try:
        resp = requests.post(
            resize_url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code not in (200, 204):
            return f"HTTP {resp.status_code}: {resp.text}"
        return ""
    except Exception as e:  # noqa: BLE001
        return str(e)


def _get_instance_info(
    project_id: str, zone: str, instance_name: str
) -> tuple[str, str, float | None]:
    """Retrieve instance status ('RUNNING', 'TERMINATED', etc.), error message, and uptime in seconds."""
    last_err = ""
    if compute_v1 is not None and hasattr(compute_v1, "InstancesClient"):
        try:
            client = compute_v1.InstancesClient()
            inst = client.get(
                project=project_id,
                zone=zone,
                instance=instance_name,
                timeout=10.0,
            )
            status = str(getattr(inst, "status", ""))
            ts = getattr(inst, "last_start_timestamp", None) or getattr(
                inst, "creation_timestamp", None
            )
            uptime = _parse_timestamp_to_seconds_ago(ts)
            return status, "", uptime
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            logger.debug(f"Failed to get instance info via compute_v1: {e}")

    token = _get_gcp_access_token()
    if not token:
        return "UNKNOWN", last_err or ERR_NO_COMPUTE_CLIENT, None

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/instances/{instance_name}"
    try:
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            status = str(data.get("status", "UNKNOWN"))
            ts = data.get("lastStartTimestamp") or data.get("creationTimestamp")
            uptime = _parse_timestamp_to_seconds_ago(ts)
            return status, "", uptime
        return "UNKNOWN", f"HTTP {resp.status_code}: {resp.text}", None
    except Exception as e:  # noqa: BLE001
        return "UNKNOWN", str(e), None


def _stop_instance(project_id: str, zone: str, instance_name: str) -> str:
    """Stop Compute Engine instance via compute_v1 or REST API fallback."""
    last_err = ""
    if compute_v1 is not None and hasattr(compute_v1, "InstancesClient"):
        try:
            client = compute_v1.InstancesClient()
            client.stop(
                project=project_id,
                zone=zone,
                instance=instance_name,
                timeout=15.0,
            )
            return ""
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            logger.warning(f"Failed to stop instance via compute_v1: {e}")

    token = _get_gcp_access_token()
    if not token:
        return last_err or ERR_NO_COMPUTE_CLIENT

    url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/instances/{instance_name}/stop"
    try:
        resp = requests.post(
            url, headers={"Authorization": f"Bearer {token}"}, timeout=10
        )
        if resp.status_code in (200, 204):
            return ""
        return f"HTTP {resp.status_code}: {resp.text}"
    except Exception as e:  # noqa: BLE001
        return str(e)


def check_and_stop_proxysql_instance(
    project_id: str,
    zone: str,
    instance_name: str,
    job_prefixes: tuple[str, ...] = (
        "realestate-crawler-pipeline",
        "realestate-ml-pipeline",
        "realestate-migrate",
    ),
    grace_period_sec: float = 600.0,
    timeout_threshold_sec: float = 4200.0,
    dry_run: bool = False,
) -> ResourceInspectionResult:
    """
    Checks if single ProxySQL instance is RUNNING.
    - If status in ('TERMINATED', 'STOPPED', 'STOPPING'): returns safely stopped.
    - If launched within grace_period_sec: skips stop (startup grace).
    - If Cloud Run Jobs (crawler, ML, migrate) are actively RUNNING within timeout_threshold_sec: skips stop.
    - If Cloud Run Jobs exceeded timeout_threshold_sec (hung): cancels executions and stops instance (Dual Kill).
    - If no active Cloud Run Jobs (orphaned): stops instance immediately.
    """
    status, err, uptime = _get_instance_info(project_id, zone, instance_name)
    if err:
        err_msg = f":rotating_light: *【緊急】ProxySQL インスタンス状態取得失敗*: {err}"
        logger.error(err_msg)
        send_slack_alert(err_msg)
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=False, leaked_size=-1, details=err
        )

    logger.info(f"ProxySQL instance '{instance_name}' current status: {status}")

    if status in ("TERMINATED", "STOPPED", "STOPPING"):
        logger.info(f"ProxySQL instance is safely stopped (status: {status}).")
        return ResourceInspectionResult(
            was_leaked=False,
            forced_stop=False,
            leaked_size=0,
            skipped_reason="stopped",
        )

    # 1. Grace Period check
    if uptime is None:
        logger.info(
            f"ProxySQL instance '{instance_name}' uptime could not be determined. "
            f"Skipping stop to prevent terminating newly launched instance."
        )
        return ResourceInspectionResult(
            was_leaked=False,
            forced_stop=False,
            leaked_size=1,
            skipped_reason="uptime_unknown",
        )
    if uptime <= grace_period_sec:
        logger.info(
            f"ProxySQL instance '{instance_name}' was launched {uptime:.1f}s ago "
            f"(<= grace_period {grace_period_sec}s). Skipping stop."
        )
        return ResourceInspectionResult(
            was_leaked=False,
            forced_stop=False,
            leaked_size=1,
            skipped_reason="grace_period",
        )

    # 2. Check active Cloud Run Jobs
    region = "-".join(zone.split("-")[:2]) if zone else "asia-northeast1"
    active_jobs, exec_err = _get_active_cloud_run_executions(
        project_id=project_id, region=region, job_prefixes=job_prefixes
    )
    if exec_err:
        err_msg = (
            f":rotating_light: *【緊急】Cloud Run Executions取得失敗*: {exec_err}。"
            f"安全のためProxySQL停止をスキップしました。"
        )
        logger.error(err_msg)
        send_slack_alert(err_msg)
        return ResourceInspectionResult(
            was_leaked=True,
            forced_stop=False,
            leaked_size=1,
            details=exec_err,
            skipped_reason="api_error",
        )

    if active_jobs:
        hung_jobs = [
            j
            for j in active_jobs
            if j.elapsed_sec is None or j.elapsed_sec > timeout_threshold_sec
        ]
        if not hung_jobs:
            job_desc = ", ".join(
                f"`{j.job_name}` ({int(j.elapsed_sec) if j.elapsed_sec is not None else 'unknown'}s)"
                for j in active_jobs
            )
            info_msg = (
                f":information_source: *【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQL停止をスキップしました*\n"
                f"・プロジェクト: `{project_id}`\n"
                f"・稼働ジョブ: {job_desc}\n"
                f"・ProxySQL: `{instance_name}` (RUNNING)"
            )
            logger.info(info_msg)
            send_slack_alert(info_msg)
            return ResourceInspectionResult(
                was_leaked=False,
                forced_stop=False,
                leaked_size=1,
                skipped_reason="job_running",
            )

        # Hung jobs detected! Trigger Dual Hard-Kill
        hung_desc = ", ".join(
            f"`{j.job_name}` ({int(j.elapsed_sec) if j.elapsed_sec is not None else 'unknown'}s)"
            for j in hung_jobs
        )
        warning_msg = (
            f":warning: *【ゾンビ課金アラート】ジョブ異常超過検知*\n"
            f"・プロジェクト: `{project_id}`\n"
            f"・ゾーン: `{zone}`\n"
            f"・超過ジョブ: {hung_desc}\n"
            f"・処置: {'[DRY-RUN] 停止スキップ' if dry_run else 'Cloud Run Job キャンセル および ProxySQL インスタンス強制停止を実行しました。'}"
        )
        logger.warning(warning_msg)
        send_slack_alert(warning_msg)

        if dry_run:
            return ResourceInspectionResult(
                was_leaked=True,
                forced_stop=False,
                leaked_size=1,
                canceled_jobs=[j.name for j in hung_jobs],
            )

        canceled_names = []
        cancel_errors = []
        for j in hung_jobs:
            c_err = _cancel_cloud_run_execution(j.name)
            if c_err:
                logger.warning(f"Failed to cancel {j.name}: {c_err}")
                cancel_errors.append(f"{j.job_name}: {c_err}")
            else:
                canceled_names.append(j.name)

        healthy_jobs = [j for j in active_jobs if j not in hung_jobs]
        if healthy_jobs:
            healthy_desc = ", ".join(
                f"`{j.job_name}` ({int(j.elapsed_sec) if j.elapsed_sec is not None else 'unknown'}s)"
                for j in healthy_jobs
            )
            logger.info(
                f"Hung jobs {[j.name for j in hung_jobs]} were cancelled, but healthy jobs "
                f"({healthy_desc}) are still legitimately running. Skipping ProxySQL stop."
            )
            return ResourceInspectionResult(
                was_leaked=False,
                forced_stop=False,
                leaked_size=1,
                canceled_jobs=canceled_names,
                skipped_reason="healthy_jobs_still_running",
            )

        stop_err = _stop_instance(project_id, zone, instance_name)
        if cancel_errors or stop_err:
            fail_items = []
            if cancel_errors:
                fail_items.append(f"Job cancel failures: {', '.join(cancel_errors)}")
            if stop_err:
                fail_items.append(f"ProxySQL stop failure: {stop_err}")
            send_slack_alert(
                f":rotating_light: *【緊急】強制停止処理で一部失敗が発生しました*: {'; '.join(fail_items)}"
            )

        return ResourceInspectionResult(
            was_leaked=True,
            forced_stop=not stop_err and len(canceled_names) == len(hung_jobs),
            leaked_size=1,
            canceled_jobs=canceled_names,
            details=stop_err or ("; ".join(cancel_errors)),
        )

    # 3. No active jobs (orphaned ProxySQL instance)
    warning_msg = (
        f":warning: *【ゾンビ課金アラート】ProxySQL停止漏れ検知*\n"
        f"・プロジェクト: `{project_id}`\n"
        f"・ゾーン: `{zone}`\n"
        f"・インスタンス名: `{instance_name}`\n"
        f"・検知時状態: `{status}`\n"
        f"・処置: {'[DRY-RUN] 停止スキップ' if dry_run else '自動強制停止を実行しました。'}"
    )
    logger.warning(warning_msg)
    send_slack_alert(warning_msg)

    if dry_run:
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=False, leaked_size=1
        )

    stop_err = _stop_instance(project_id, zone, instance_name)
    if not stop_err:
        logger.info(f"Successfully stopped ProxySQL instance '{instance_name}'.")
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=True, leaked_size=1
        )

    err_msg = f"Failed to stop ProxySQL instance '{instance_name}': {stop_err}"
    logger.error(err_msg)
    send_slack_alert(
        f":rotating_light: *【緊急】ProxySQL インスタンスの強制停止に失敗しました*: {err_msg}"
    )
    return ResourceInspectionResult(
        was_leaked=True,
        forced_stop=False,
        leaked_size=1,
        details=stop_err,
    )


def check_and_stop_proxysql_mig(
    project_id: str,
    region: str,
    mig_name: str,
    job_prefixes: tuple[str, ...] = (
        "realestate-crawler-pipeline",
        "realestate-ml-pipeline",
        "realestate-migrate",
    ),
    grace_period_sec: float = 600.0,
    timeout_threshold_sec: float = 4200.0,
    dry_run: bool = False,
) -> ResourceInspectionResult:
    """
    Checks if ProxySQL MIG target_size > 0.
    - If target_size == 0: returns safely stopped.
    - If launched within grace_period_sec: skips stop (startup grace).
    - If Cloud Run Jobs (crawler, ML, migrate) are actively RUNNING within timeout_threshold_sec: skips stop.
    - If Cloud Run Jobs exceeded timeout_threshold_sec (hung): cancels executions and stops MIG (Dual Kill).
    - If no active Cloud Run Jobs (orphaned): stops MIG immediately.
    """
    current_target_size, err, autoscaler = _get_mig_info(project_id, region, mig_name)
    if err:
        err_msg = f":rotating_light: *【緊急】ProxySQL MIG状態取得失敗*: {err}"
        logger.error(err_msg)
        send_slack_alert(err_msg)
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=False, leaked_size=-1, details=err
        )

    logger.info(f"ProxySQL MIG '{mig_name}' current target_size: {current_target_size}")

    if current_target_size == 0:
        logger.info("ProxySQL MIG is safely stopped (target_size = 0).")
        return ResourceInspectionResult(
            was_leaked=False,
            forced_stop=False,
            leaked_size=0,
            skipped_reason="stopped",
        )

    # 1. Grace Period check (avoid startup race conditions)
    mig_uptime = _get_mig_uptime_seconds(project_id, region, mig_name)
    if mig_uptime is None:
        logger.info(
            f"ProxySQL MIG '{mig_name}' uptime could not be determined. "
            f"Skipping stop to prevent terminating newly launched instances."
        )
        return ResourceInspectionResult(
            was_leaked=False,
            forced_stop=False,
            leaked_size=current_target_size,
            skipped_reason="uptime_unknown",
        )
    if mig_uptime <= grace_period_sec:
        logger.info(
            f"ProxySQL MIG '{mig_name}' was launched {mig_uptime:.1f}s ago "
            f"(<= grace_period {grace_period_sec}s). Skipping stop."
        )
        return ResourceInspectionResult(
            was_leaked=False,
            forced_stop=False,
            leaked_size=current_target_size,
            skipped_reason="grace_period",
        )

    # 2. Check active Cloud Run Jobs (including crawler, ML pricing pipeline, migration)
    active_jobs, exec_err = _get_active_cloud_run_executions(
        project_id=project_id, region=region, job_prefixes=job_prefixes
    )
    if exec_err:
        err_msg = (
            f":rotating_light: *【緊急】Cloud Run Executions取得失敗*: {exec_err}。"
            f"安全のためProxySQL停止をスキップしました。"
        )
        logger.error(err_msg)
        send_slack_alert(err_msg)
        return ResourceInspectionResult(
            was_leaked=True,
            forced_stop=False,
            leaked_size=current_target_size,
            details=exec_err,
            skipped_reason="api_error",
        )

    if active_jobs:
        # Unknown/missing elapsed_sec is treated as timed out (failsafe)
        hung_jobs = [
            j
            for j in active_jobs
            if j.elapsed_sec is None or j.elapsed_sec > timeout_threshold_sec
        ]
        if not hung_jobs:
            # All active jobs are legitimately running within timeout
            job_desc = ", ".join(
                f"`{j.job_name}` ({int(j.elapsed_sec) if j.elapsed_sec is not None else 'unknown'}s)"
                for j in active_jobs
            )
            info_msg = (
                f":information_source: *【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQL停止をスキップしました*\n"
                f"・プロジェクト: `{project_id}`\n"
                f"・稼働ジョブ: {job_desc}\n"
                f"・MIGサイズ: `{current_target_size}` 台"
            )
            logger.info(info_msg)
            send_slack_alert(info_msg)
            return ResourceInspectionResult(
                was_leaked=False,
                forced_stop=False,
                leaked_size=current_target_size,
                skipped_reason="job_running",
            )

        # Hung jobs detected! Trigger Dual Hard-Kill
        hung_desc = ", ".join(
            f"`{j.job_name}` ({int(j.elapsed_sec) if j.elapsed_sec is not None else 'unknown'}s)"
            for j in hung_jobs
        )
        warning_msg = (
            f":warning: *【ゾンビ課金アラート】ジョブ異常超過検知*\n"
            f"・プロジェクト: `{project_id}`\n"
            f"・リージョン: `{region}`\n"
            f"・超過ジョブ: {hung_desc}\n"
            f"・処置: {'[DRY-RUN] 停止スキップ' if dry_run else 'Cloud Run Job キャンセル および ProxySQL MIG 自動強制停止 (size -> 0) を実行しました。'}"
        )
        logger.warning(warning_msg)
        send_slack_alert(warning_msg)

        if dry_run:
            return ResourceInspectionResult(
                was_leaked=True,
                forced_stop=False,
                leaked_size=current_target_size,
                canceled_jobs=[j.name for j in hung_jobs],
            )

        canceled_names = []
        cancel_errors = []
        for j in hung_jobs:
            c_err = _cancel_cloud_run_execution(j.name)
            if c_err:
                logger.warning(f"Failed to cancel {j.name}: {c_err}")
                cancel_errors.append(f"{j.job_name}: {c_err}")
            else:
                canceled_names.append(j.name)

        # Check if there are other jobs legitimately running within timeout
        healthy_jobs = [j for j in active_jobs if j not in hung_jobs]
        if healthy_jobs:
            healthy_desc = ", ".join(
                f"`{j.job_name}` ({int(j.elapsed_sec) if j.elapsed_sec is not None else 'unknown'}s)"
                for j in healthy_jobs
            )
            logger.info(
                f"Hung jobs {[j.name for j in hung_jobs]} were cancelled, but healthy jobs "
                f"({healthy_desc}) are still legitimately running. Skipping ProxySQL MIG stop."
            )
            return ResourceInspectionResult(
                was_leaked=False,
                forced_stop=False,
                leaked_size=current_target_size,
                canceled_jobs=canceled_names,
                skipped_reason="healthy_jobs_still_running",
            )

        auto_name = _extract_autoscaler_name(autoscaler)
        if auto_name:
            stop_err = _stop_autoscaler(project_id, region, auto_name)
        else:
            stop_err = _resize_mig_to_zero(project_id, region, mig_name)

        if cancel_errors or stop_err:
            fail_items = []
            if cancel_errors:
                fail_items.append(
                    f"Job cancel failures: {', '.join(cancel_errors)}"
                )
            if stop_err:
                fail_items.append(f"ProxySQL stop failure: {stop_err}")
            send_slack_alert(
                f":rotating_light: *【緊急】強制停止処理で一部失敗が発生しました*: {'; '.join(fail_items)}"
            )

        return ResourceInspectionResult(
            was_leaked=True,
            forced_stop=not stop_err and len(canceled_names) == len(hung_jobs),
            leaked_size=current_target_size,
            canceled_jobs=canceled_names,
            details=stop_err or ("; ".join(cancel_errors)),
        )

    # 3. No active jobs (orphaned ProxySQL MIG)
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
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=False, leaked_size=current_target_size
        )

    auto_name = _extract_autoscaler_name(autoscaler)
    if auto_name:
        logger.info(
            f"MIG is managed by autoscaler '{auto_name}'. Scaling autoscaler to 0."
        )
        stop_err = _stop_autoscaler(project_id, region, auto_name)
    else:
        stop_err = _resize_mig_to_zero(project_id, region, mig_name)

    if not stop_err:
        logger.info(f"Successfully stopped ProxySQL MIG '{mig_name}'.")
        return ResourceInspectionResult(
            was_leaked=True, forced_stop=True, leaked_size=current_target_size
        )

    err_msg = f"Failed to stop ProxySQL MIG '{mig_name}': {stop_err}"
    logger.error(err_msg)
    send_slack_alert(
        f":rotating_light: *【緊急】ProxySQL MIGの強制停止に失敗しました*: {err_msg}"
    )
    return ResourceInspectionResult(
        was_leaked=True,
        forced_stop=False,
        leaked_size=current_target_size,
        details=stop_err,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ensure GCP on-demand resources are safely stopped."
    )
    parser.add_argument(
        "--project-id",
        default=os.environ.get(
            "GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "sumifu")
        ),
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
        "--job-prefixes",
        default="realestate-crawler-pipeline,realestate-ml-pipeline,realestate-migrate",
        help="Comma-separated prefixes of monitored Cloud Run Jobs",
    )
    parser.add_argument(
        "--grace-period-sec",
        type=float,
        default=600.0,
        help="Grace period in seconds for newly launched instances (default: 600s / 10m)",
    )
    parser.add_argument(
        "--timeout-threshold-sec",
        type=float,
        default=4200.0,
        help="Timeout threshold in seconds for active jobs before forced cancel (default: 4200s / 70m)",
    )
    parser.add_argument(
        "--instance-name",
        default=os.environ.get("PROXYSQL_INSTANCE_NAME", ""),
        help="ProxySQL Compute Engine Instance Name (Direct VPC single instance mode)",
    )
    parser.add_argument(
        "--zone",
        default=os.environ.get("PROXYSQL_ZONE", ""),
        help="ProxySQL Compute Engine Instance Zone",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check only without resizing",
    )

    args = parser.parse_args()
    prefixes = tuple(p.strip() for p in args.job_prefixes.split(",") if p.strip())

    logger.info("=== [START] Checking for leaked GCP resources ===")
    if args.instance_name:
        inst_zone = args.zone or os.environ.get("PROXYSQL_ZONE") or f"{args.region}-a"
        result = check_and_stop_proxysql_instance(
            project_id=args.project_id,
            zone=inst_zone,
            instance_name=args.instance_name,
            job_prefixes=prefixes,
            grace_period_sec=args.grace_period_sec,
            timeout_threshold_sec=args.timeout_threshold_sec,
            dry_run=args.dry_run,
        )
    else:
        result = check_and_stop_proxysql_mig(
            project_id=args.project_id,
            region=args.region,
            mig_name=args.mig_name,
            job_prefixes=prefixes,
            grace_period_sec=args.grace_period_sec,
            timeout_threshold_sec=args.timeout_threshold_sec,
            dry_run=args.dry_run,
        )

    if result.was_leaked:
        if result.forced_stop:
            logger.warning(
                f"Leaked resource detected and forcibly stopped: {result.leaked_size} instances."
            )
            return 0
        logger.error(f"Leaked resource detected but failed to stop: {result.details}")
        return 1

    logger.info("=== [FINISH] All checked resources are safely stopped or legitimately active. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

