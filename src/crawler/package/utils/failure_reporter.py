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
    def _fetch_from_storage(cls, date_str: str) -> tuple[list[dict[str, Any]], set[str], str | None]:
        failures: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        storage_error: str | None = None
        try:
            sm = get_storage_manager()
            prefix = f"runs/{date_str}/failures/"
            for k in sm.list_files(prefix=prefix):
                if not k.endswith(".json"):
                    continue
                try:
                    data = json.loads(sm.read_text(k))
                    failures.append(data)
                    seen_keys.add(f"{data.get('company')}_{data.get('property_type')}")
                except Exception as ke:  # noqa: BLE001
                    logger.warning("Failed to parse failure JSON %s: %s", k, ke)
        except Exception as e:  # noqa: BLE001
            storage_error = str(e)
            logger.warning("Failed to fetch daily failures from storage: %s", e)
        return failures, seen_keys, storage_error

    @classmethod
    def _fetch_from_local_fallback(cls, date_str: str, seen_keys: set[str]) -> list[dict[str, Any]]:
        fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        local_dir = fallback_base / "runs" / date_str / "failures"
        if not local_dir.exists():
            return []
        extra: list[dict[str, Any]] = []
        for fpath in local_dir.glob("*.json"):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                jk = f"{data.get('company')}_{data.get('property_type')}"
                if jk not in seen_keys:
                    extra.append(data)
                    seen_keys.add(jk)
            except Exception as fe:  # noqa: BLE001
                logger.warning("Failed to read local fallback %s: %s", fpath, fe)
        return extra

    @classmethod
    def _scan_log_files(cls, date_str: str) -> list[dict[str, Any]]:
        """ローカルおよびGCS上のログファイルから ERROR / CRITICAL レベルのログエントリを抽出"""
        error_logs: list[dict[str, Any]] = []
        fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        
        # 1. ローカルログファイルの検索
        log_files: list[Path] = []
        if fallback_base.exists():
            log_files.extend(fallback_base.glob(f"*{date_str}*.log"))
            log_files.extend(fallback_base.glob("*.log"))
            
        for lpath in set(log_files):
            try:
                with open(lpath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if "ERROR" in line or "CRITICAL" in line:
                            error_logs.append({
                                "source": "log_file",
                                "file_path": str(lpath),
                                "line_number": line_num,
                                "log_entry": line.strip(),
                                "level": "CRITICAL" if "CRITICAL" in line else "ERROR"
                            })
            except Exception as le:  # noqa: BLE001
                logger.warning("Failed to read log file %s: %s", lpath, le)

        # 2. GCS ログファイルの検索 (runs/{date_str}/logs/ または logs/)
        try:
            sm = get_storage_manager()
            gcs_log_prefix = f"runs/{date_str}/logs/"
            for k in sm.list_files(prefix=gcs_log_prefix):
                if not k.endswith(".log"):
                    continue
                try:
                    content = sm.read_text(k)
                    for line_num, line in enumerate(content.splitlines(), 1):
                        if "ERROR" in line or "CRITICAL" in line:
                            error_logs.append({
                                "source": "gcs_log_file",
                                "file_path": k,
                                "line_number": line_num,
                                "log_entry": line.strip(),
                                "level": "CRITICAL" if "CRITICAL" in line else "ERROR"
                            })
                except Exception as gcle:  # noqa: BLE001
                    logger.warning("Failed to read GCS log file %s: %s", k, gcle)
        except Exception as se:  # noqa: BLE001
            logger.debug("Storage manager log scan skipped or failed: %s", se)

        return error_logs

    @classmethod
    def fetch_daily_failures(cls, date_str: str | None = None) -> dict[str, Any]:
        """GCS（およびローカルフォールバック）から指定日付の全障害情報とログエラーを集約ロード"""
        if not date_str:
            date_str = datetime.datetime.now(datetime.timezone.utc).date().strftime("%Y%m%d")

        failures, seen_keys, storage_error = cls._fetch_from_storage(date_str)
        fallback_failures = cls._fetch_from_local_fallback(date_str, seen_keys)
        failures.extend(fallback_failures)
        log_errors = cls._scan_log_files(date_str)

        return {
            "date": date_str,
            "total_failures": len(failures),
            "total_log_errors": len(log_errors),
            "storage_error": storage_error,
            "failures": failures,
            "log_errors": log_errors
        }
