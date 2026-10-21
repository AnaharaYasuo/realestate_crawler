"""Crawler process watchdog module for detecting silent hanging jobs."""
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _parse_hang_threshold() -> float:
    raw = os.getenv("CRAWLER_HANG_THRESHOLD_SEC", "0.0").strip()
    try:
        val = float(raw)
        return max(0.0, val)
    except (ValueError, TypeError):
        return 0.0

HANG_THRESHOLD_SEC: float = _parse_hang_threshold()
INITIAL_DISCOVERY_GRACE_SEC: float = float(os.getenv("CRAWLER_INITIAL_GRACE_SEC", "1800.0").strip())


def get_progress_dir() -> Path:
    """進捗通知用ファイルの格納ディレクトリを取得・作成する"""
    custom_dir = os.getenv("CRAWLER_PROGRESS_DIR")
    if custom_dir:
        p = Path(custom_dir)
    else:
        # デフォルトは logs/progress
        p = Path(os.getenv("CRAWLER_LOG_DIR", "logs")) / "progress"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_progress_file_path(company: str, ptype: str) -> Path:
    """会社名と種別に応じた進捗通知ファイルパスを返す"""
    return get_progress_dir() / f"progress_{company}_{ptype}.touch"


def touch_crawler_progress(company: str, ptype: str) -> None:
    """子プロセスが物件詳細取得や保存時に呼び出し、進捗ファイルのmtimeを更新する"""
    try:
        path = get_progress_file_path(company, ptype)
        path.touch(exist_ok=True)
    except Exception as e:
        logger.debug(f"Failed to touch progress file for {company} {ptype}: {e}")


def cleanup_crawler_progress(company: str, ptype: str) -> None:
    """ジョブ終了時に進捗通知ファイルを削除する"""
    try:
        path = get_progress_file_path(company, ptype)
        if path.exists():
            path.unlink()
    except Exception:
        pass


def check_job_hung(
    last_activity_time: float,
    current_time: float | None = None,
    threshold_sec: float = HANG_THRESHOLD_SEC,
    prev_db_cnt: int = 0,
    start_time: float | None = None,
) -> bool:
    """Check if job has been silent (no heartbeat/progress) for longer than threshold."""
    if threshold_sec <= 0:
        return False
    now = current_time if current_time is not None else time.time()
    # 1. すでに一度でも活動（進捗ファイルのmtime更新等）が記録されている場合は、最後の活動からの経過時間を判定
    if last_activity_time > (start_time or 0.0):
        return (now - last_activity_time) > threshold_sec

    # 2. 起動直後の初回一覧取得フェーズ (DB件数がまだ0件かつ進捗未発生) では探索猶予を設ける
    if prev_db_cnt == 0 and start_time is not None:
        effective_threshold = max(threshold_sec, INITIAL_DISCOVERY_GRACE_SEC)
        return (now - start_time) > effective_threshold
    return (now - last_activity_time) > threshold_sec


def kill_hung_job_process(proc: Any) -> bool:
    """Terminate hung job process group via SIGKILL."""
    if proc is None or proc.poll() is not None:
        return False
    try:
        if hasattr(os, "getpgid") and hasattr(os, "killpg"):
            pgid = os.getpgid(proc.pid)
            logger.warning(
                f"⚠️ [Watchdog Hang Detected] Process group {pgid} (PID {proc.pid}) "
                f"silent > {HANG_THRESHOLD_SEC}s. Killing process group via SIGKILL..."
            )
            os.killpg(pgid, signal.SIGKILL)
            proc.communicate()
            return True
        else:
            logger.warning(
                f"⚠️ [Watchdog Hang Detected] Process PID {proc.pid} "
                f"silent > {HANG_THRESHOLD_SEC}s. Killing process via proc.kill()..."
            )
            proc.kill()
            proc.communicate()
            return True
    except Exception:
        logger.exception("Failed to kill hung process group")
        return False


def _update_single_job_progress(
    job_info: tuple,
    now: float,
    count_fn: Any,
    check_interval_sec: float,
) -> tuple:
    """単一ジョブのローカル進捗ファイルmtimeおよびDB進捗を確認し、更新後のタプルを返す"""
    proc, company, ptype, start_t, start_dt, *extra = job_info
    last_act = extra[0] if extra else start_t
    prev_db_cnt = extra[1] if len(extra) > 1 else 0
    last_check_t = extra[2] if len(extra) > 2 else 0.0

    if (now - last_check_t) < check_interval_sec:
        return job_info

    # 1. ローカル進捗ファイル（mtime）による進捗確認 (Issue #1059: DB負荷完全ゼロ)
    prog_path = get_progress_file_path(company, ptype)
    if prog_path.exists():
        try:
            mtime = prog_path.stat().st_mtime
            if mtime > last_act:
                last_act = mtime
                # 少なくとも1回以上活動があったので prev_db_cnt もインクリメント扱いにして探索猶予から実稼働へ遷移
                if prev_db_cnt == 0:
                    prev_db_cnt = 1
        except Exception:
            pass

    # 2. DB COUNT(*) による進捗確認（count_fn が提供されている場合のみ）
    if count_fn is not None:
        try:
            counts = count_fn(company, ptype, start_dt)
            current_db_cnt = counts[2] if counts[0] is not None else None
        except Exception:
            current_db_cnt = None
    else:
        current_db_cnt = None

    if current_db_cnt is not None:
        if current_db_cnt > prev_db_cnt:
            last_act = now
        return (proc, company, ptype, start_t, start_dt, last_act, max(current_db_cnt, prev_db_cnt), now)
    return (proc, company, ptype, start_t, start_dt, last_act, prev_db_cnt, now)


def update_watchdog_progress(
    active_processes: dict[int, tuple],
    now: float,
    count_fn: Any,
    check_interval_sec: float = 15.0,
) -> None:
    """進捗監視対象プロセスの進捗（ファイルmtimeおよびDB件数）を確認し、公平に last_act を更新する"""
    for idx in tuple(active_processes.keys()):
        if idx in active_processes:
            active_processes[idx] = _update_single_job_progress(
                active_processes[idx], now, count_fn, check_interval_sec
            )
