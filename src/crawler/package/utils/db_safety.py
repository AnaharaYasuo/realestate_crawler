import logging
import os

logger = logging.getLogger(__name__)

class ProductionDatabaseModificationBlocked(RuntimeError):
    """ローカル環境から本番データベースへの直接変更がブロックされた場合の例外"""

# 禁止する管理コマンド
BLOCKED_COMMANDS = {
    "migrate",
    "makemigrations",
    "sqlmigrate",
    "squashmigrations",
    "flush",
    "dbshell",
}

def is_production_db_target() -> bool:
    """現在設定されているDB接続先が本番DBかどうかを判定"""
    try:
        from django.conf import settings
        if settings.configured:
            default_db = settings.DATABASES.get("default", {})
            engine = default_db.get("ENGINE", "")
            # SQLite (テスト用一時DB等) は除外
            if "sqlite" in engine:
                return False
            db_host = default_db.get("HOST") or os.getenv("DB_HOST", "")
            db_port = str(default_db.get("PORT") or os.getenv("DB_PORT", ""))
            db_name = default_db.get("NAME") or os.getenv("DB_NAME", "")
        else:
            db_host = os.getenv("DB_HOST", "")
            db_port = str(os.getenv("DB_PORT", ""))
            db_name = os.getenv("DB_NAME", "")
    except (ImportError, AttributeError):
        db_host = os.getenv("DB_HOST", "")
        db_port = str(os.getenv("DB_PORT", ""))
        db_name = os.getenv("DB_NAME", "")

    is_prod_host = (
        "host.docker.internal" in (db_host or "").lower()
        or "34." in (db_host or "")
        or "35." in (db_host or "")
        or "cloudsql" in (db_host or "").lower()
    )
    is_prod_port = str(db_port).strip() in ("3306", "3307")
    is_prod_db = (db_name or "").strip() == "real_estate"

    return is_prod_host and is_prod_port and is_prod_db

def assert_production_db_safety(command_name: str | None = None) -> None:
    """
    本番DBに対する直接操作を原理的に遮断するハードガード。
    IS_PRODUCTION_DEPLOYMENT=true (CI/CD本番デプロイ時のみ付与) でない限り、
    本番DBに対する migrate 等の変更コマンドは例外を送出して即時中断する。
    """
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
