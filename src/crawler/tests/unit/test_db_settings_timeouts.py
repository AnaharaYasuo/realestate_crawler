# -*- coding: utf-8 -*-
"""Issue #916: 全 Django DB 接続への有限タイムアウト (connect_timeout, read_timeout, write_timeout) 適用テスト"""
import os

from package.utils import db_timeouts


def test_get_database_config_applies_timeouts(monkeypatch):
    """get_database_config() が返却する設定辞書に有限タイムアウトが含まれていることを検証"""
    import realestateSettings

    config = realestateSettings.get_database_config()
    assert config["ENGINE"] == "django.db.backends.mysql"
    options = config.get("OPTIONS", {})
    assert options.get("charset") == "utf8mb4"
    assert options.get("connect_timeout") == db_timeouts.DB_CONNECT_TIMEOUT_SEC
    assert options.get("read_timeout") == db_timeouts.DB_QUERY_TIMEOUT_SEC
    assert options.get("write_timeout") == db_timeouts.DB_QUERY_TIMEOUT_SEC


def test_realestate_settings_source_code_enforces_bound_mysql_timeouts():
    """realestateSettings.py のソースコード上で bound_mysql_timeouts が組み込まれていることを静的検証"""
    import realestateSettings

    settings_file = os.path.abspath(realestateSettings.__file__)
    with open(settings_file, encoding="utf-8") as f:
        content = f.read()

    assert "bound_mysql_timeouts" in content, (
        "bound_mysql_timeouts must be imported and called in realestateSettings.py"
    )
