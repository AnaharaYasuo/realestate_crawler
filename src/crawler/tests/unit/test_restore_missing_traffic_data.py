import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import realestateSettings

realestateSettings.configure()

from package.models.mitsui import MitsuiKodate
from package.models.nomura import NomuraMansion
from package.utils.db_safety import ProductionDatabaseModificationBlocked
from scripts.maintenance.restore_missing_traffic_data import (
    get_all_target_property_models,
    restore_traffic_from_existing_fields,
    synthesize_traffic_str,
)


def test_synthesize_traffic_str_basic():
    """Route 1 の駅・路線・徒歩分数から正しい交通文字列が合成されること"""
    item = MitsuiKodate()
    item.railway1 = "JR山手線"
    item.station1 = "渋谷駅"
    item.railwayWalkMinute1 = 8

    res = synthesize_traffic_str(item)
    assert res == "JR山手線 渋谷駅 徒歩8分"

    item.busStation1 = "渋谷西口"
    item.busWalkMinute1 = 3
    res2 = synthesize_traffic_str(item)
    assert "JR山手線 渋谷駅 徒歩8分" in res2
    assert "バス停 渋谷西口 徒歩3分" in res2


def test_synthesize_traffic_str_multi_routes():
    """Route 1〜5 およびバス停1〜5 の複数経路が網羅されて合成されること"""
    item = NomuraMansion()
    item.railway1 = "東京メトロ銀座線"
    item.station1 = "表参道駅"
    item.railwayWalkMinute1 = 5

    item.railway2 = "東京メトロ千代田線"
    item.station2 = "明治神宮前駅"
    item.railwayWalkMinute2Str = "徒歩7分"

    item.railway3 = "JR山手線"
    item.station3 = "原宿駅"
    item.railwayWalkMinute3 = 10

    item.busStation2 = "神宮前六丁目"
    item.busWalkMinute2 = 2

    res = synthesize_traffic_str(item)
    assert "東京メトロ銀座線 表参道駅 徒歩5分" in res
    assert "東京メトロ千代田線 明治神宮前駅 徒歩7分" in res
    assert "JR山手線 原宿駅 徒歩10分" in res
    assert "バス停 神宮前六丁目 徒歩2分" in res
    # 区切り文字が / であること
    assert " / " in res


def test_get_all_target_property_models_covers_all_sites():
    """全アプリケーションから20社以上の全物件モデルが動的抽出されること"""
    models = get_all_target_property_models()
    assert len(models) >= 20

    # 代表的な各社モデルが含まれていること
    model_names = {m.__name__ for m in models}
    expected_prefixes = [
        "Mitsui",
        "Daikyo",
        "Sumirin",
        "Tokyu",
        "Nomura",
        "Sumifu",
        "Misawa",
        "Smtrc",
        "Sumai1",
        "Sekisui",
        "Afr",
        "Mizuho",
        "Odakyu",
        "Totate",
        "Daiwa",
        "Heim",
        "Rearie",
        "Keio",
        "Seibu",
        "Keikyu",
        "Sotetsu",
        "Keisei",
        "Homes",
        "Athome",
    ]
    for prefix in expected_prefixes:
        matched = any(name.startswith(prefix) for name in model_names)
        assert matched, (
            f"Expected model with prefix {prefix} not found in target models"
        )


def test_restore_traffic_blocks_when_local_executing_on_production(monkeypatch):
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
        restore_traffic_from_existing_fields(dry_run=False)


def test_restore_traffic_dry_run_does_not_modify_db():
    """ドライラン時はDB更新を行わず、走査結果辞書を返すこと"""
    with patch(
        "scripts.maintenance.restore_missing_traffic_data.assert_production_db_safety"
    ) as mock_safety:
        res = restore_traffic_from_existing_fields(dry_run=True)
        assert isinstance(res, dict)
        mock_safety.assert_not_called()
