"""Unit tests for Kenbiya start routes target areas (Issue #1762)."""

from unittest.mock import patch

from flask import Flask
from routes.kenbiya_routes import (
    kenbiya_bp,
    kenbiya_invest_apartment_start,
    kenbiya_invest_building_start,
    kenbiya_kodate_start,
    kenbiya_mansion_start,
    kenbiya_tochi_start,
)


def test_kenbiya_mansion_start_crawls_four_areas():
    with patch("routes.kenbiya_routes.ParseKenbiyaMansionStartAsync") as mock_cls:
        mock_cls.return_value.main.return_value = "ok"
        res = kenbiya_mansion_start()
        assert res == "ok"
        called_urls = [call.args[0] for call in mock_cls.return_value.main.call_args_list]
        assert called_urls == [
            "https://www.kenbiya.com/pp1/s/tokyo/",
            "https://www.kenbiya.com/pp1/s/kanagawa/",
            "https://www.kenbiya.com/pp1/s/saitama/",
            "https://www.kenbiya.com/pp1/t/aichi/",
        ]


def test_kenbiya_kodate_start_crawls_four_areas():
    with patch("routes.kenbiya_routes.ParseKenbiyaKodateStartAsync") as mock_cls:
        mock_cls.return_value.main.return_value = "ok"
        res = kenbiya_kodate_start()
        assert res == "ok"
        called_urls = [call.args[0] for call in mock_cls.return_value.main.call_args_list]
        assert called_urls == [
            "https://www.kenbiya.com/pp8/s/tokyo/",
            "https://www.kenbiya.com/pp8/s/kanagawa/",
            "https://www.kenbiya.com/pp8/s/saitama/",
            "https://www.kenbiya.com/pp8/t/aichi/",
        ]


def test_kenbiya_tochi_start_crawls_four_areas():
    with patch("routes.kenbiya_routes.ParseKenbiyaTochiStartAsync") as mock_cls:
        mock_cls.return_value.main.return_value = "ok"
        res = kenbiya_tochi_start()
        assert res == "ok"
        called_urls = [call.args[0] for call in mock_cls.return_value.main.call_args_list]
        assert called_urls == [
            "https://www.kenbiya.com/pp5/s/tokyo/",
            "https://www.kenbiya.com/pp5/s/kanagawa/",
            "https://www.kenbiya.com/pp5/s/saitama/",
            "https://www.kenbiya.com/pp5/t/aichi/",
        ]


def test_kenbiya_invest_apartment_start_crawls_four_areas():
    with patch("routes.kenbiya_routes.ParseKenbiyaInvestApartmentStartAsync") as mock_cls:
        mock_cls.return_value.main.return_value = "ok"
        res = kenbiya_invest_apartment_start()
        assert res == "ok"
        called_urls = [call.args[0] for call in mock_cls.return_value.main.call_args_list]
        assert called_urls == [
            "https://www.kenbiya.com/pp2/s/tokyo/",
            "https://www.kenbiya.com/pp2/s/kanagawa/",
            "https://www.kenbiya.com/pp2/s/saitama/",
            "https://www.kenbiya.com/pp2/t/aichi/",
        ]


def test_kenbiya_invest_building_start_crawls_four_areas():
    with patch("routes.kenbiya_routes.ParseKenbiyaInvestBuildingStartAsync") as mock_cls:
        mock_cls.return_value.main.return_value = "ok"
        res = kenbiya_invest_building_start()
        assert res == "ok"
        called_urls = [call.args[0] for call in mock_cls.return_value.main.call_args_list]
        assert called_urls == [
            "https://www.kenbiya.com/pp3/s/tokyo/",
            "https://www.kenbiya.com/pp3/s/kanagawa/",
            "https://www.kenbiya.com/pp3/s/saitama/",
            "https://www.kenbiya.com/pp3/t/aichi/",
        ]


def test_kenbiya_blueprint_registers_routes():
    app = Flask(__name__)
    app.register_blueprint(kenbiya_bp)
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert len(rules) >= 10
