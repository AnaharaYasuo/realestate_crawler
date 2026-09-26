"""GCS real-time failure telemetry and auto-heal integration module."""
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from package.utils.storage import get_storage_manager

logger = logging.getLogger(__name__)


def generate_auto_heal_trigger_message(
    date_str: str,
    failed_count: int,
    failed_jobs: list[Any]
) -> str:
    """Slack #dev-agent 宛の Antigravity 自動修復トリガーメッセージを生成"""
    jobs_summary = "\n".join([f"  • {c} - {p}" for c, p in failed_jobs])
    return (
        f"[AGY-REQ:AUTO-HEAL] @DevAgent 【クローリング障害自動検知】\n"
        f"本日 ({date_str}) のクローリングで {failed_count} 件の異常を検知しました。\n"
        f"対象ジョブ:\n{jobs_summary}\n\n"
        f"GCSより障害情報を一括取得し、パーサーの自動修復・テスト検証を実行してください。\n"
        f"取得コマンド: python src/crawler/scripts/debug_tools/fetch_run_failures.py --date {date_str}"
    )


class FailureReporter:
    """クローリング障害テレメトリの即時GCS永続化および一括回収マネージャー"""

    @classmethod
    def record_job_failure(
        cls,
        company: str,
        property_type: str,
        error_type: str,
        error_message: str,
        target_url: str = "",
        exit_code: int = 1,
        traceback_str: str = "",
        raw_html: bytes | None = None,
        duration_seconds: int = 0,
        task_index: int | None = None,
        task_count: int | None = None,
        date_str: str | None = None
    ) -> dict[str, Any]:
        """障害メタデータおよび失敗生HTMLを即座にGCS（またはフォールバック）へ保存"""
        if not date_str:
            date_str = datetime.datetime.now(datetime.timezone.utc).date().strftime("%Y%m%d")

        comp_clean = str(company).lower()
        type_clean = str(property_type).lower()
        job_key = f"{comp_clean}_{type_clean}"

        # HTML保存パス構築
        html_key = None
        if raw_html:
            url_hash = hashlib.sha256((target_url or job_key).encode("utf-8")).hexdigest()[:16]
            html_key = f"runs/{date_str}/error_pages/{job_key}/{url_hash}.html"

        metadata_key = f"runs/{date_str}/failures/{job_key}.json"

        record: dict[str, Any] = {
            "date": date_str,
            "company": comp_clean,
            "property_type": type_clean,
            "status": "failed",
            "exit_code": exit_code,
            "error_type": error_type,
            "error_message": error_message,
            "target_url": target_url,
            "gcs_html_path": None,
            "metadata_key": metadata_key,
            "parser_file": f"src/crawler/package/parser/{comp_clean}Parser.py",
            "traceback": traceback_str,
            "duration_seconds": duration_seconds,
            "task_index": task_index,
            "task_count": task_count,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        # 1. GCS / オブジェクトストレージへのアップロード試行
        storage_uploaded = False
        try:
            sm = get_storage_manager()
            if raw_html and html_key:
                uploaded_path = sm.upload_bytes(raw_html, html_key, content_type="text/html")
                record["gcs_html_path"] = str(uploaded_path) if uploaded_path is not None else None

            meta_bytes = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
            sm.upload_bytes(meta_bytes, metadata_key, content_type="application/json")
            storage_uploaded = True
            logger.info("Successfully recorded failure telemetry to storage: %s", metadata_key)
        except Exception as se:  # noqa: BLE001
            logger.warning("ObjectStorageManager upload failed, falling back to local: %s", se)

        # 2. ローカルフォールバック保存
        if not storage_uploaded or os.getenv("STORAGE_LOCAL_FALLBACK_DIR"):
            fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
            meta_path = fallback_base / "runs" / date_str / "failures" / f"{job_key}.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            if raw_html and html_key:
                html_path = fallback_base / html_key
                html_path.parent.mkdir(parents=True, exist_ok=True)
                with open(html_path, "wb") as f:
                    f.write(raw_html)
                record["gcs_html_path"] = str(html_path)

            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            logger.info("Saved failure telemetry to local fallback: %s", meta_path)

        return record

    @classmethod
    def fetch_daily_failures(cls, date_str: str | None = None) -> dict[str, Any]:
        """GCS（およびローカルフォールバック）から指定日付の全障害情報を集約ロード"""
        if not date_str:
            date_str = datetime.datetime.now(datetime.timezone.utc).date().strftime("%Y%m%d")

        failures: list[dict[str, Any]] = []
        seen_keys = set()
        storage_error: str | None = None

        # 1. オブジェクトストレージより取得
        try:
            sm = get_storage_manager()
            prefix = f"runs/{date_str}/failures/"
            keys = sm.list_files(prefix=prefix)
            for k in keys:
                if k.endswith(".json"):
                    content = sm.read_text(k)
                    data = json.loads(content)
                    failures.append(data)
                    seen_keys.add(f"{data.get('company')}_{data.get('property_type')}")
        except Exception as e:  # noqa: BLE001
            storage_error = str(e)
            logger.warning("Failed to fetch daily failures from storage: %s", e)

        # 2. ローカルフォールバックも走査して補完
        fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        local_dir = fallback_base / "runs" / date_str / "failures"
        if local_dir.exists():
            for fpath in local_dir.glob("*.json"):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    jk = f"{data.get('company')}_{data.get('property_type')}"
                    if jk not in seen_keys:
                        failures.append(data)
                        seen_keys.add(jk)
                except Exception as fe:  # noqa: BLE001
                    logger.warning("Failed to read local fallback %s: %fe", fpath, fe)

        return {
            "date": date_str,
            "total_failures": len(failures),
            "storage_error": storage_error,
            "failures": failures
        }
