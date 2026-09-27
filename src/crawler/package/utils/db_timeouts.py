"""DB 不通時に OS 既定の TCP 待ちで長時間ブロックしないよう MySQL 接続へ有限タイムアウトを設ける共通ヘルパー"""

DB_CONNECT_TIMEOUT_SEC = 10
DB_QUERY_TIMEOUT_SEC = 120


def bound_mysql_timeouts(settings_dict) -> None:
    """MySQL の接続設定 OPTIONS に接続・読み書きタイムアウトを設定する (明示設定がある場合はそれを優先)"""
    if not settings_dict or not str(settings_dict.get("ENGINE", "")).endswith("mysql"):
        return
    options = settings_dict.get("OPTIONS")
    if options is None:
        options = settings_dict["OPTIONS"] = {}
    options.setdefault("connect_timeout", DB_CONNECT_TIMEOUT_SEC)
    options.setdefault("read_timeout", DB_QUERY_TIMEOUT_SEC)
    options.setdefault("write_timeout", DB_QUERY_TIMEOUT_SEC)
