import datetime
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from package.utils.converter import parse_chikunengetsu
from package.utils.db_safety import ProductionDatabaseModificationBlocked
from scripts.maintenance.restore_missing_chikunengetsu_data import (
    get_all_target_chikunengetsu_models,
    restore_chikunengetsu_from_existing_fields,
)


def test_parse_chikunengetsu_formats():
    """各種日付フォーマットが正しく parse されること"""
    assert parse_chikunengetsu("1995年3月") == datetime.date(1995, 3, 1)
    assert parse_chikunengetsu("昭和60年5月") == datetime.date(1985, 5, 1)
    assert parse_chikunengetsu("平成12年8月") == datetime.date(2000, 8, 1)
    assert parse_chikunengetsu("令和2年10月") == datetime.date(2020, 10, 1)
    assert parse_chikunengetsu("2010/04") == datetime.date(2010, 4, 1)
    assert parse_chikunengetsu("不詳") is None
    assert parse_chikunengetsu("-") is None


def test_get_all_target_chikunengetsu_models():
    """chikunengetsu フィールドを持つモデルが動的抽出されること"""
    models = get_all_target_chikunengetsu_models()
    assert len(models) >= 20
    model_names = {m.__name__ for m in models}
    assert "MitsuiMansion" in model_names
    assert "MitsuiInvestmentApartment" in model_names


def test_restore_chikunengetsu_blocks_when_local_executing_on_production(monkeypatch):
    """ローカル環境で本番DBに対して --execute を実行するとブロックされること"""
    from django.conf import settings

    monkeypatch.setitem(
        settings.DATABASES,
        "default",
        {
            "ENGINE": "django.db.backends.mysql",
            "HOST": "host.docker.internal",
            "PORT": "3307",
            "NAME": "real_estate",
        },
    )
    monkeypatch.setenv("DB_HOST", "host.docker.internal")
    monkeypatch.delenv("IS_PRODUCTION_DEPLOYMENT", raising=False)

    with pytest.raises(ProductionDatabaseModificationBlocked):
        restore_chikunengetsu_from_existing_fields(dry_run=False)


def test_restore_chikunengetsu_dry_run_does_not_modify_db():
    """ドライラン時はDB更新を行わず、走査結果辞書を返すこと"""
    with patch(
        "scripts.maintenance.restore_missing_chikunengetsu_data.assert_production_db_safety"
    ) as mock_safety:
        res = restore_chikunengetsu_from_existing_fields(dry_run=True)
        assert isinstance(res, dict)
        mock_safety.assert_not_called()
