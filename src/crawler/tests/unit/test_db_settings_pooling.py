# -*- coding: utf-8 -*-
import os


def test_db_settings_bans_dj_db_conn_pool():
    """アプリ側でのコネクションプーリング (dj_db_conn_pool) が完全禁止されていることを検証"""
    import realestateSettings

    settings_file = os.path.abspath(realestateSettings.__file__)
    with open(settings_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "dj_db_conn_pool" not in content, "dj_db_conn_pool must be completely removed from realestateSettings.py"
    assert "'CONN_MAX_AGE': 0" in content, "CONN_MAX_AGE must be set to 0 to prevent retaining open connections in containers"
    assert "'django.db.backends.mysql'" in content, "django.db.backends.mysql must be used as the standard database backend"
