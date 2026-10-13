import logging
import os

logger = logging.getLogger(__name__)

class ProductionDatabaseModificationBlocked(RuntimeError):
    """ローカル環境から本番データベースへの直接変更がブロックされた場合の例外"""


BLOCKED_COMMANDS = {
    "migrate",
    "makemigrations",
    "sqlmigrate",
    "squashmigrations",
    "flush",
    "dbshell",
    "restore_traffic",
    "restore_chikunengetsu",
    "bulk_update",
}

LOCAL_HOSTS = {"localhost", "127.0.0.1", "db", "mysql", "testserver"}


def _get_active_db_params() -> tuple[str, str, str]:
    """現在アクティブなDBホスト、ポート、DB名を取得"""
    try:
        from django.conf import settings
        if settings.configured:
            default_db = settings.DATABASES.get("default", {})
            if "sqlite" in default_db.get("ENGINE", ""):
                return "", "", ""
            host = default_db.get("HOST") or os.getenv("DB_HOST", "")
            port = str(default_db.get("PORT") or os.getenv("DB_PORT", ""))
            name = default_db.get("NAME") or os.getenv("DB_NAME", "")
            return host, port, name
    except (ImportError, AttributeError):
        pass

    return os.getenv("DB_HOST", ""), str(os.getenv("DB_PORT", "")), os.getenv("DB_NAME", "")


def is_production_db_target() -> bool:
    """現在設定されているDB接続先が本番DBかどうかを判定"""
    db_host, _, _ = _get_active_db_params()
    host_clean = db_host.strip().lower()
    if not host_clean or host_clean in LOCAL_HOSTS:
        return False

    prod_env_host = os.getenv("PROD_DB_HOST", "").strip().lower()
    if prod_env_host and host_clean == prod_env_host:
        return True

    return host_clean == "host.docker.internal" or "cloudsql" in host_clean


def assert_production_db_safety(command_name: str | None = None) -> None:
    """本番DBに対する直接操作を原理的に遮断するハードガード"""
    if os.getenv("IS_PRODUCTION_DEPLOYMENT") == "true":
        return

    cmd = (command_name or "").lower()
    is_blocked_cmd = (not cmd) or (cmd in BLOCKED_COMMANDS)
    if is_blocked_cmd and is_production_db_target():
        target_name = cmd or "direct data modification"
        msg = (
            f"CRITICAL BLOCK: Direct execution of '{target_name}' against the production database "
            "from a local/development environment is physically prohibited! "
            "All database schema changes and maintenance updates must be applied strictly via the CI/CD production deployment pipeline."
        )
        logger.critical(msg)
        raise ProductionDatabaseModificationBlocked(msg)

