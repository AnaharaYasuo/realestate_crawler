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
}

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
    """現在設定されているDB接続先が本番DBかどうかを判定 (S3776 分散)"""
    db_host, db_port, db_name = _get_active_db_params()
    if not db_host:
        return False

    is_prod_host = any(h in db_host.lower() for h in ("host.docker.internal", "34.", "35.", "cloudsql"))
    is_prod_port = db_port.strip() in ("3306", "3307")
    is_prod_db = db_name.strip() == "real_estate"

    return is_prod_host and is_prod_port and is_prod_db

def assert_production_db_safety(command_name: str | None = None) -> None:
    """本番DBに対する直接操作を原理的に遮断するハードガード"""
    if os.getenv("IS_PRODUCTION_DEPLOYMENT") == "true":
        return

    cmd = (command_name or "").lower()
    if cmd in BLOCKED_COMMANDS and is_production_db_target():
        msg = (
            f"CRITICAL BLOCK: Direct execution of '{cmd}' against the production database "
            "from a local/development environment is physically prohibited! "
            "All database schema changes must be applied strictly via the CI/CD production deployment pipeline."
        )
        logger.critical(msg)
        raise ProductionDatabaseModificationBlocked(msg)
