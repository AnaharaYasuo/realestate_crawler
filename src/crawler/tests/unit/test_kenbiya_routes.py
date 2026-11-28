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


def _extract_called_urls(mock_main):
    urls = []
    for call in mock_main.call_args_list:
        urls.append(call.args[0])
        urls.extend(call.kwargs.get("extra_urls", ()))
    return urls


def test_kenbiya_mansion_start_crawls_four_areas():
    with patch("routes.kenbiya_routes.ParseKenbiyaMansionStartAsync") as mock_cls:
        mock_cls.return_value.main.return_value = "ok"
        res = kenbiya_mansion_start()
        assert res == "ok"
        assert _extract_called_urls(mock_cls.return_value.main) == [
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
        assert _extract_called_urls(mock_cls.return_value.main) == [
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
        assert _extract_called_urls(mock_cls.return_value.main) == [
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
        assert _extract_called_urls(mock_cls.return_value.main) == [
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
        assert _extract_called_urls(mock_cls.return_value.main) == [
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


def test_kenbiya_detail_cooldown_disabled_by_default(monkeypatch):
    from package.api import kenbiya as kenbiya_api

    monkeypatch.setattr(kenbiya_api, "COOLDOWN_WORK_SECONDS", 0.0)
    detail = kenbiya_api.ParseKenbiyaMansionDetailFuncAsync()
    assert detail._get_cooldown_config() is None

    monkeypatch.setattr(kenbiya_api, "COOLDOWN_WORK_SECONDS", 3600.0)
    assert detail._get_cooldown_config() == (3600.0, kenbiya_api.COOLDOWN_REST_SECONDS)


def test_differential_query_recovers_proxysql_on_2013():
    from django.db import OperationalError
    from package.api.differential import _query_existing_records_sync

    calls = {"n": 0}

    class FakeQS:
        def values(self, *args):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OperationalError(2013, "Lost connection to server at 'handshake'")
            return [{"pageUrl": "https://www.kenbiya.com/pp1/re_1/", "price": 1000, "updateDateTime": None, "inputDateTime": None}]

    class FakeModel:
        class objects:
            @staticmethod
            def filter(**kwargs):
                return FakeQS()

    with patch("package.api.kenbiya._ensure_proxysql_tunnel_ready", return_value=True) as mock_recover:
        res = _query_existing_records_sync(FakeModel, ["https://www.kenbiya.com/pp1/re_1/"])
        assert mock_recover.call_count == 1
        assert calls["n"] == 2
        assert "https://www.kenbiya.com/pp1/re_1/" in res
