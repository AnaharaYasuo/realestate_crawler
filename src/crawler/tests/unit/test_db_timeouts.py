# -*- coding: utf-8 -*-
"""Issue #518: MySQL 接続に有限の接続・読み書きタイムアウトを設定する共通ヘルパーの単体テスト"""
import pytest

from package.utils import db_timeouts
from package.utils.db_timeouts import bound_mysql_timeouts


def test_default_timeouts():
    assert db_timeouts.DB_CONNECT_TIMEOUT_SEC == 10
    assert db_timeouts.DB_QUERY_TIMEOUT_SEC == 120


def test_sets_finite_timeouts_for_mysql():
    settings_dict = {"ENGINE": "django.db.backends.mysql", "OPTIONS": {"charset": "utf8mb4"}}
    bound_mysql_timeouts(settings_dict)
    assert settings_dict["OPTIONS"] == {
        "charset": "utf8mb4",
        "connect_timeout": 10,
        "read_timeout": 120,
        "write_timeout": 120,
    }


def test_keeps_explicit_values():
    options = {"connect_timeout": 3, "read_timeout": 30, "write_timeout": 40}
    settings_dict = {"ENGINE": "django.db.backends.mysql", "OPTIONS": dict(options)}
    bound_mysql_timeouts(settings_dict)
    assert settings_dict["OPTIONS"] == options


@pytest.mark.parametrize("settings_dict", [
    {"ENGINE": "django.db.backends.mysql"},
    {"ENGINE": "django.db.backends.mysql", "OPTIONS": None},
])
def test_creates_options_when_missing(settings_dict):
    bound_mysql_timeouts(settings_dict)
    assert settings_dict["OPTIONS"] == {"connect_timeout": 10, "read_timeout": 120, "write_timeout": 120}


@pytest.mark.parametrize("settings_dict", [
    {"ENGINE": "django.db.backends.sqlite3", "OPTIONS": {}},
    {"OPTIONS": {}},
])
def test_ignores_non_mysql_backends(settings_dict):
    bound_mysql_timeouts(settings_dict)
    assert settings_dict["OPTIONS"] == {}


@pytest.mark.parametrize("settings_dict", [None, {}])
def test_ignores_missing_settings(settings_dict):
    bound_mysql_timeouts(settings_dict)
    assert settings_dict in (None, {})
