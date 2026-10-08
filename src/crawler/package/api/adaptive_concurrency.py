"""
コンテナ内動的詳細並行度制御およびDB過負荷自己適応サーキットブレーカー (Issue #795)
"""
import json
import logging
import os
import tempfile
import time
from typing import Any

logger = logging.getLogger(__name__)

# DB過負荷を示すMySQLエラーコード一覧
DB_OVERLOAD_ERROR_CODES = {
    1040,  # ER_CON_COUNT_ERROR (Too many connections)
    2006,  # CR_SERVER_GONE_ERROR (MySQL server has gone away)
    2013,  # CR_SERVER_LOST (Lost connection to MySQL server during query)
    1205,  # ER_LOCK_WAIT_TIMEOUT (Lock wait timeout exceeded)
    1213,  # ER_LOCK_DEADLOCK (Deadlock found when trying to get lock)
}

DB_OVERLOAD_KEYWORDS = (
    "too many connections",
    "server has gone away",
    "lost connection",
    "lock wait timeout",
    "deadlock",
)


class AdaptiveConcurrencyController:
    """
    コンテナ内のリソース余力（アクティブジョブ数）とDBの負荷状態に基づき、
    安全かつ最大限の処理速度を発揮するようにクローラーの詳細並行度を制御する。
    """
    STATE_FILE = os.path.join(tempfile.gettempdir(), "crawler_concurrency_state.json")
    DEFAULT_THROTTLE_SECONDS = 60
    THROTTLED_CONCURRENCY = 2

    @classmethod
    def _get_current_time(cls) -> float:
        return time.time()

    @classmethod
    def calculate_detail_concurrency(cls, active_jobs: int | None = None) -> int:
        """
        アクティブジョブ数に基づいて1ジョブあたりの詳細並行度を計算。
        環境変数 CLOUD_DETAIL_CONCURRENCY が設定されている場合は最優先。
        """
        env_limit = os.getenv("CLOUD_DETAIL_CONCURRENCY")
        if env_limit and env_limit.isdigit() and int(env_limit) > 0:
            return int(env_limit)

        if active_jobs is None:
            active_jobs = cls.get_active_jobs_count()

        if active_jobs <= 1:
            return 15
        elif active_jobs == 2:
            return 12
        elif active_jobs <= 4:
            return 8
        elif active_jobs <= 6:
            return 5
        else:
            return 4

    @classmethod
    def is_db_overload_error(cls, error: Exception) -> bool:
        """発生した例外がDB過負荷に起因するかを判定"""
        args = getattr(error, "args", ())
        if args and isinstance(args[0], int) and args[0] in DB_OVERLOAD_ERROR_CODES:
            return True

        err_str = str(error).lower()
        return any(keyword in err_str for keyword in DB_OVERLOAD_KEYWORDS)

    @classmethod
    def record_db_overload(cls, reason: str = "") -> None:
        """DB過負荷を検知した際に状態ファイルへ記録してスロットリングを発動"""
        now = cls._get_current_time()
        logger.warning(
            f"⚠️ [DB Throttling] DB過負荷を検知 ({reason})。詳細並行度を {cls.THROTTLED_CONCURRENCY} に絞り込み、{cls.DEFAULT_THROTTLE_SECONDS}秒間冷却します。"
        )
        data = {
            "last_overload_time": now,
            "reason": reason,
        }
        cls._write_state(data)

    @classmethod
    def is_throttled(cls) -> bool:
        """現在DB過負荷によるスロットリング中（冷却期間中）かどうかを判定"""
        state = cls._read_state()
        last_time = state.get("last_overload_time", 0)
        return (cls._get_current_time() - last_time) < cls.DEFAULT_THROTTLE_SECONDS

    @classmethod
    def get_effective_concurrency(cls, active_jobs: int | None = None) -> int:
        """スロットリング状態を考慮した実効並行度を返す"""
        if cls.is_throttled():
            return cls.THROTTLED_CONCURRENCY
        return cls.calculate_detail_concurrency(active_jobs)

    @classmethod
    def set_active_jobs_count(cls, count: int) -> None:
        """親プロセス（run_all_crawlers.py）から現在のアクティブジョブ数を更新"""
        state = cls._read_state()
        state["active_jobs_count"] = max(1, count)
        state["updated_at"] = cls._get_current_time()
        cls._write_state(state)

    @classmethod
    def get_active_jobs_count(cls) -> int:
        """状態ファイルまたは環境変数から現在のアクティブジョブ数を取得"""
        env_val = os.getenv("CONTAINER_ACTIVE_JOBS")
        if env_val and env_val.isdigit() and int(env_val) > 0:
            return int(env_val)

        state = cls._read_state()
        return state.get("active_jobs_count", 1)

    @classmethod
    def _read_state(cls) -> dict[str, Any]:
        if not os.path.exists(cls.STATE_FILE):
            return {}
        try:
            with open(cls.STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    @classmethod
    def _write_state(cls, data: dict[str, Any]) -> None:
        try:
            current = cls._read_state()
            current.update(data)
            with open(cls.STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f)
        except OSError as e:
            logger.debug(f"Failed to write concurrency state file: {e}")
