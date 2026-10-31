"""GCS real-time failure telemetry and auto-heal integration module."""
import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from package.utils.storage import get_storage_manager

logger = logging.getLogger(__name__)

_LOG_LINE_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")
_LOG_NAME_DATE_PATTERN = re.compile(r"(?<!\d)(\d{4})-?(\d{2})-?(\d{2})(?!\d)")
_ROTATED_LOG_NAME_PATTERN = re.compile(r"\.log\.(?:\d+|\d{4}-\d{2}-\d{2}(?:_[\d-]+)?)$")
MAX_FAILURES_PER_JOB = 50
MAX_LOCAL_ERROR_HTML_PATHS = 10


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


def html_meta_key(html_key: str) -> str:
    """エラー HTML キーに対応するサイドカーメタ JSON キー"""
    return html_key.removesuffix(".html") + "_meta.json"


def _html_meta_bytes(record: dict[str, Any]) -> bytes:
    meta = {k: record.get(k) for k in ("target_url", "error_type", "error_message", "timestamp")}
    if record.get("parent_list_url"):
        meta["parent_list_url"] = record["parent_list_url"]
    if record.get("http_status") is not None:
        meta["http_status"] = record["http_status"]
    return json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")


class FailureReporter:
    """クローリング障害テレメトリの即時GCS永続化および一括回収マネージャー"""

    @classmethod
    def _upload_failure_telemetry(
        cls,
        record: dict[str, Any],
        raw_html: bytes | None,
        html_key: str | None,
        metadata_key: str
    ) -> bool:
        try:
            sm = get_storage_manager()
            if raw_html and html_key:
                uploaded_path = sm.upload_bytes(raw_html, html_key, content_type="text/html")
                record["gcs_html_path"] = str(uploaded_path) if uploaded_path is not None else None
                try:
                    sm.upload_bytes(_html_meta_bytes(record), html_meta_key(html_key), content_type="application/json")
                except Exception as me:  # noqa: BLE001
                    logger.warning("Failed to upload error page sidecar meta %s: %s", html_key, me)

            meta_bytes = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
            sm.upload_bytes(meta_bytes, metadata_key, content_type="application/json")
            logger.info("Successfully recorded failure telemetry to storage: %s", metadata_key)
            return True
        except Exception as se:  # noqa: BLE001
            logger.warning("ObjectStorageManager upload failed, falling back to local: %s", se)
            return False

    @classmethod
    def _load_existing_failures(cls, job_key: str, date_str: str) -> list[dict[str, Any]]:
        fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        meta_path = fallback_base / "runs" / date_str / "failures" / f"{job_key}.json"
        if not meta_path.exists():
            return []
        try:
            prev_data = json.loads(meta_path.read_text(encoding="utf-8"))
            prev_failures = prev_data.get("failures")
            if isinstance(prev_failures, list) and prev_failures:
                return list(prev_failures)
            if isinstance(prev_data, dict) and prev_data.get("error_type"):
                return [{
                    "error_type": prev_data.get("error_type"),
                    "error_message": prev_data.get("error_message", ""),
                    "target_url": prev_data.get("target_url", ""),
                    "parent_list_url": prev_data.get("parent_list_url", ""),
                    "http_status": prev_data.get("http_status"),
                    "exit_code": prev_data.get("exit_code", 1),
                    "traceback": prev_data.get("traceback", ""),
                    "timestamp": prev_data.get("timestamp", ""),
                }]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not load existing failure telemetry from %s: %s", meta_path, exc)
        return []

    @classmethod
    def _save_local_fallback_telemetry(
        cls,
        record: dict[str, Any],
        raw_html: bytes | None,
        html_key: str | None,
        job_key: str,
        date_str: str
    ) -> None:
        fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        meta_path = fallback_base / "runs" / date_str / "failures" / f"{job_key}.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        if raw_html and html_key:
            html_path = fallback_base / html_key
            html_path.parent.mkdir(parents=True, exist_ok=True)
            with open(html_path, "wb") as f:
                f.write(raw_html)
            html_path_str = str(html_path)
            paths = record.setdefault("local_error_html_paths", [])
            if html_path_str not in paths:
                paths.append(html_path_str)
                record["local_error_html_paths"] = paths[:MAX_LOCAL_ERROR_HTML_PATHS]
            try:
                (fallback_base / html_meta_key(html_key)).write_bytes(_html_meta_bytes(record))
            except Exception as le:  # noqa: BLE001
                logger.warning("Failed to save local error page sidecar meta %s: %s", html_key, le)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        logger.info("Saved failure telemetry to local fallback: %s", meta_path)

    @classmethod
    def _auto_enrich_hang_diagnostics(
        cls,
        comp_clean: str,
        type_clean: str,
        error_type: str,
        target_url: str,
        parent_list_url: str,
        traceback_str: str,
        diagnostics: Any,
    ) -> tuple[str, str, str, Any]:
        if (target_url and traceback_str and diagnostics is not None) or error_type not in (
            "HangSilentFailure",
            "TimeoutError",
            "ProcessCrashFailure",
        ):
            return target_url, parent_list_url, traceback_str, diagnostics
        try:
            from package.utils.crawler_diagnostics import (
                build_hang_diagnostic_snapshot,
                format_snapshot_summary_text,
            )

            snap = build_hang_diagnostic_snapshot(
                comp_clean, type_clean, in_process=False, reason=error_type
            )
            target_url = target_url or str(snap.get("primary_target_url") or "")
            parent_list_url = parent_list_url or str(snap.get("primary_parent_list_url") or "")
            traceback_str = traceback_str or format_snapshot_summary_text(snap)
            if diagnostics is None:
                diagnostics = {
                    "active_urls": snap.get("active_urls", []),
                    "active_phases": snap.get("active_phases", []),
                    "hardware_and_network": snap.get("hardware_and_network", {}),
                    "database": snap.get("database", {}),
                    "persisted_thread_states": snap.get("persisted_thread_states", []),
                }
        except Exception as diag_err:  # noqa: BLE001
            logger.debug("Diagnostic enrichment skipped: %s", diag_err)
        return target_url, parent_list_url, traceback_str, diagnostics

    @classmethod
    def _resolve_local_error_html(
        cls, date_str: str, job_key: str, raw_html: bytes | None
    ) -> tuple[bytes | None, list[str]]:
        local_error_html_paths: list[str] = []
        fallback_base = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        existing_err_dir = fallback_base / "runs" / date_str / "error_pages" / job_key
        if not existing_err_dir.exists():
            return raw_html, local_error_html_paths
        existing_htmls = sorted(existing_err_dir.glob("*.html"))
        local_error_html_paths = [str(p) for p in existing_htmls[:MAX_LOCAL_ERROR_HTML_PATHS]]
        if not raw_html and existing_htmls:
            try:
                raw_html = existing_htmls[0].read_bytes()
            except OSError as exc:
                logger.debug("Could not read fallback error HTML %s: %s", existing_htmls[0], exc)
        return raw_html, local_error_html_paths

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
        date_str: str | None = None,
        **extra_context: Any,
    ) -> dict[str, Any]:
        """障害メタデータおよび失敗生HTMLを即座にGCS（またはフォールバック）へ保存（複数エラー履歴も追記保持）"""
        parent_list_url = str(extra_context.get("parent_list_url", ""))
        http_status_raw = extra_context.get("http_status")
        http_status = int(http_status_raw) if http_status_raw is not None else None
        diagnostics = extra_context.get("diagnostics")
        if not date_str:
            date_str = datetime.datetime.now(datetime.UTC).date().strftime("%Y%m%d")

        comp_clean = str(company).lower()
        type_clean = str(property_type).lower()
        job_key = f"{comp_clean}_{type_clean}"

        target_url, parent_list_url, traceback_str, diagnostics = cls._auto_enrich_hang_diagnostics(
            comp_clean, type_clean, error_type, target_url, parent_list_url, traceback_str, diagnostics
        )
        raw_html, local_error_html_paths = cls._resolve_local_error_html(date_str, job_key, raw_html)
        html_key = None

        if raw_html:
            url_hash = hashlib.sha256((target_url or job_key).encode("utf-8")).hexdigest()[:16]
            html_key = f"runs/{date_str}/error_pages/{job_key}/{url_hash}.html"

        metadata_key = f"runs/{date_str}/failures/{job_key}.json"
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()

        prev_failures = cls._load_existing_failures(job_key, date_str)
        current_entry: dict[str, Any] = {
            "error_type": error_type,
            "error_message": error_message,
            "target_url": target_url,
            "parent_list_url": parent_list_url,
            "http_status": http_status,
            "exit_code": exit_code,
            "traceback": traceback_str,
            "timestamp": now_iso,
        }
        if diagnostics:
            current_entry["diagnostics"] = diagnostics
        failures_history = (prev_failures + [current_entry])[-MAX_FAILURES_PER_JOB:]

        record: dict[str, Any] = {
            "date": date_str,
            "company": comp_clean,
            "property_type": type_clean,
            "status": "failed",
            "exit_code": exit_code,
            "error_type": error_type,
            "error_message": error_message,
            "target_url": target_url,
            "parent_list_url": parent_list_url,
            "http_status": http_status,
            "gcs_html_path": None,
            "local_error_html_paths": local_error_html_paths,
            "metadata_key": metadata_key,
            "parser_file": f"src/crawler/package/parser/{comp_clean}Parser.py",
            "traceback": traceback_str,
            "duration_seconds": duration_seconds,
            "task_index": task_index,
            "task_count": task_count,
            "timestamp": now_iso,
            "failure_count": len(failures_history),
            "failures": failures_history,
        }
        if diagnostics:
            record["diagnostics"] = diagnostics

        storage_uploaded = cls._upload_failure_telemetry(record, raw_html, html_key, metadata_key)

        if not storage_uploaded or os.getenv("STORAGE_LOCAL_FALLBACK_DIR"):
            cls._save_local_fallback_telemetry(record, raw_html, html_key, job_key, date_str)

        return record

    @classmethod
    def _parse_log_lines(
        cls,
        lines: Any,
        source: str,
        file_path: str,
        target_date: str | None = None,
        require_date: bool = False,
    ) -> list[dict[str, Any]]:
        extracted: list[dict[str, Any]] = []
        for line_num, line in enumerate(lines, 1):
            if target_date is not None and not cls._matches_log_date(line, target_date, require_date):
                continue
            if "ERROR" in line or "CRITICAL" in line:
                extracted.append({
                    "source": source,
                    "file_path": file_path,
                    "line_number": line_num,
                    "log_entry": line.strip(),
                    "level": "CRITICAL" if "CRITICAL" in line else "ERROR"
                })
        return extracted

    @staticmethod
    def _matches_log_date(line: str, target_date: str, require_date: bool) -> bool:
        match = _LOG_LINE_DATE_PATTERN.match(line)
        if match is None:
            return not require_date
        return match.group(1) == target_date

    @staticmethod
    def _modified_on_or_after(lpath: Path, iso_date: str) -> bool:
        try:
            mtime = lpath.stat().st_mtime
        except OSError:
            return False
        modified = datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC).date()
        return modified >= datetime.date.fromisoformat(iso_date) - datetime.timedelta(days=1)

    @classmethod
    def _scan_local_logs(cls, date_str: str) -> list[dict[str, Any]]:
        error_logs: list[dict[str, Any]] = []
        fallback_base = Path(os.getenv("CRAWLER_LOG_DIR", "").strip() or os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        if not fallback_base.exists():
            return error_logs

        iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        log_files = set(fallback_base.glob("*.log")) | {
            p for p in fallback_base.glob("*.log.*") if _ROTATED_LOG_NAME_PATTERN.search(p.name)
        }
        job_logs_dir = fallback_base / "runs" / date_str / "jobs"
        if job_logs_dir.exists():
            log_files |= set(job_logs_dir.glob("*.log"))
        for lpath in sorted(log_files):
            name_dates = {"".join(parts) for parts in _LOG_NAME_DATE_PATTERN.findall(str(lpath))}
            if name_dates and date_str not in name_dates:
                continue
            if not name_dates and not cls._modified_on_or_after(lpath, iso_date):
                continue
            require_date = not name_dates
            try:
                with open(lpath, encoding="utf-8", errors="ignore") as f:
                    error_logs.extend(
                        cls._parse_log_lines(f, "log_file", str(lpath), iso_date, require_date)
                    )
            except Exception as le:  # noqa: BLE001
                logger.warning("Failed to read log file %s: %s", lpath, le)
        return error_logs

    @classmethod
    def _scan_gcs_logs(cls, date_str: str) -> list[dict[str, Any]]:
        error_logs: list[dict[str, Any]] = []
        try:
            sm = get_storage_manager()
            gcs_log_prefix = f"runs/{date_str}/logs/"
            for k in sm.list_files(prefix=gcs_log_prefix):
                if not k.endswith(".log"):
                    continue
                try:
                    content = sm.read_text(k)
                    error_logs.extend(cls._parse_log_lines(content.splitlines(), "gcs_log_file", k))
                except Exception as gcle:  # noqa: BLE001
                    logger.warning("Failed to read GCS log file %s: %s", k, gcle)
        except Exception as se:  # noqa: BLE001
            logger.debug("Storage manager log scan skipped or failed: %s", se)
        return error_logs

    @classmethod
    def _scan_log_files(cls, date_str: str) -> list[dict[str, Any]]:
        """ローカルおよびGCS上のログファイルから ERROR / CRITICAL レベルのログエントリを抽出"""
        return cls._scan_local_logs(date_str) + cls._scan_gcs_logs(date_str)

    @classmethod
    def _fetch_from_storage(cls, date_str: str) -> tuple[list[dict[str, Any]], set[str], str | None]:
        failures: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        storage_error: str | None = None
        try:
            sm = get_storage_manager()
            gcs_prefix = f"runs/{date_str}/failures/"
            for k in sm.list_files(prefix=gcs_prefix):
                if not k.endswith(".json"):
                    continue
                try:
                    content = sm.read_text(k)
                    data = json.loads(content)
                    failures.append(data)
                    job_key = Path(k).stem
                    seen_keys.add(job_key)
                except Exception as fe:  # noqa: BLE001
                    logger.warning("Failed to parse telemetry file %s: %s", k, fe)
        except Exception as se:  # noqa: BLE001
            storage_error = str(se)
            logger.warning("ObjectStorageManager list/read failed, relying on local fallback: %s", se)

        return failures, seen_keys, storage_error

    @classmethod
    def _fetch_from_local_fallback(cls, date_str: str, seen_keys: set[str]) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []
        fallback_dir = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs")) / "runs" / date_str / "failures"
        if not fallback_dir.exists():
            return failures

        for local_file in fallback_dir.glob("*.json"):
            job_key = local_file.stem
            if job_key in seen_keys:
                continue
            try:
                with open(local_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if not data.get("gcs_html_path"):
                        error_pages_dir = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs")) / "runs" / date_str / "error_pages" / job_key
                        if error_pages_dir.exists():
                            html_files = sorted(error_pages_dir.glob("*.html"))
                            if html_files:
                                data["local_html_path"] = str(html_files[0])
                                data["local_error_html_paths"] = [str(p) for p in html_files[:MAX_LOCAL_ERROR_HTML_PATHS]]
                    failures.append(data)
            except Exception as fe:  # noqa: BLE001
                logger.warning("Failed to parse local telemetry file %s: %s", local_file, fe)

        return failures

    @classmethod
    def fetch_daily_failures(cls, date_str: str | None = None) -> dict[str, Any]:
        """GCS（およびローカルフォールバック）から指定日付の全障害情報とログエラーを集約ロード"""
        if not date_str:
            date_str = datetime.datetime.now(datetime.UTC).date().strftime("%Y%m%d")

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
