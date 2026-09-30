import os
from unittest.mock import MagicMock, patch
from package.utils.newrelic_helper import (
    record_http_request,
    record_database_operation,
    record_parser_metrics,
    record_ml_inference_metrics,
)
from scripts.setup_new_relic_dashboard import (
    build_dashboard_create_payload,
    build_dashboard_delete_payload,
)


def test_record_http_request_without_license_key():
    """NEW_RELIC_LICENSE_KEY未設定時はFalseを返し記録をスキップすること"""
    with patch.dict(os.environ, {}, clear=True):
        res = record_http_request(
            domain="homes.co.jp",
            method="GET",
            status_code=200,
            duration_ms=120.5,
            response_bytes=10240,
            site_name="homes",
        )
        assert res is False


def test_record_http_request_success():
    """HttpRequestEventカスタムイベントが正しく記録されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_http_request(
                domain="www.athome.co.jp",
                method="GET",
                status_code=403,
                duration_ms=45.2,
                response_bytes=512,
                site_name="athome",
                is_blocked=True,
                metadata={"url": "https://www.athome.co.jp/test"},
            )
            assert res is True
            mock_agent.record_custom_event.assert_called_once()
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "HttpRequestEvent"
            assert params["domain"] == "www.athome.co.jp"
            assert params["method"] == "GET"
            assert params["status_code"] == 403
            assert params["duration_ms"] == 45.2
            assert params["response_bytes"] == 512
            assert params["site_name"] == "athome"
            assert params["is_blocked"] is True
            assert params["url"] == "https://www.athome.co.jp/test"
            assert params["is_blocked"] is True


def test_record_http_request_auto_blocked_and_site_name_fallback():
    """status_code 429で自動的にis_blocked=Trueになり、site_name未指定時にdomainにフォールバックすること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_http_request(
                domain="suumo.jp",
                method="GET",
                status_code=429,
                duration_ms=250.0,
            )
            assert res is True
            mock_agent.record_custom_event.assert_called_once()
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "HttpRequestEvent"
            assert params["domain"] == "suumo.jp"
            assert params["site_name"] == "suumo.jp"
            assert params["status_code"] == 429
            assert params["is_blocked"] is True


def test_record_database_operation_success():
    """DatabaseEventカスタムイベントが正しく記録されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_database_operation(
                table_name="mansion_properties",
                operation="upsert",
                duration_ms=85.4,
                row_count=25,
                status="success",
            )
            assert res is True
            mock_agent.record_custom_event.assert_called_once()
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "DatabaseEvent"
            assert params["table_name"] == "mansion_properties"
            assert params["operation"] == "upsert"
            assert params["duration_ms"] == 85.4
            assert params["row_count"] == 25
            assert params["status"] == "success"


def test_record_parser_metrics_success():
    """ParserEventカスタムイベントが正しく記録されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_parser_metrics(
                site_name="tokyu",
                property_type="mansion",
                duration_ms=35.0,
                total_fields=20,
                extracted_fields=18,
                missing_fields=2,
                missing_ratio=10.0,
                status="success",
            )
            assert res is True
            mock_agent.record_custom_event.assert_called_once()
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "ParserEvent"
            assert params["site_name"] == "tokyu"
            assert params["property_type"] == "mansion"
            assert params["duration_ms"] == 35.0
            assert params["total_fields"] == 20
            assert params["extracted_fields"] == 18
            assert params["missing_fields"] == 2
            assert params["missing_ratio"] == 10.0
            assert params["status"] == "success"


def test_record_ml_inference_metrics_success():
    """MlInferenceEventカスタムイベントが正しく記録されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_ml_inference_metrics(
                model_type="mansion",
                duration_ms=420.0,
                evaluated_count=150,
                bargain_count=12,
                skipped_count=3,
                status="success",
            )
            assert res is True
            mock_agent.record_custom_event.assert_called_once()
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "MlInferenceEvent"
            assert params["model_type"] == "mansion"
            assert params["duration_ms"] == 420.0
            assert params["evaluated_count"] == 150
            assert params["bargain_count"] == 12
            assert params["skipped_count"] == 3
            assert params["status"] == "success"


def test_build_dashboard_create_payload():
    """統合ダッシュボード作成のGraphQLペイロードが正しく構築されること"""
    payload = build_dashboard_create_payload(
        account_id=8553111,
        dashboard_name="Test Unified Dashboard",
    )
    assert "mutation" in payload["query"]
    assert payload["variables"]["accountId"] == 8553111
    assert payload["variables"]["dashboard"]["name"] == "Test Unified Dashboard"
    pages = payload["variables"]["dashboard"]["pages"]
    assert len(pages) > 0
    widgets = pages[0]["widgets"]
    assert len(widgets) >= 8
    nrql_queries = []
    for w in widgets:
        cfg = w.get("configuration", {})
        for chart_type in ("billboard", "line", "table", "bar", "pie", "area"):
            if chart_type in cfg and "nrqlQueries" in cfg[chart_type]:
                for nq in cfg[chart_type]["nrqlQueries"]:
                    nrql_queries.append(nq["query"])
    assert any("CrawlerExecution" in q for q in nrql_queries)
    assert any("ContainerSample" in q for q in nrql_queries)
    assert any("HttpRequestEvent" in q for q in nrql_queries)
    assert any("DatabaseEvent" in q for q in nrql_queries)
    assert any("ParserEvent" in q for q in nrql_queries)
    assert any("MlInferenceEvent" in q for q in nrql_queries)
    assert any("LlmEvent" in q for q in nrql_queries)
    assert any("Log" in q for q in nrql_queries)



def test_build_dashboard_delete_payload():
    """ダッシュボード削除のGraphQLペイロードが正しく構築されること"""
    payload = build_dashboard_delete_payload(guid="test-guid-12345")
    assert "dashboardDelete" in payload["query"]
    assert payload["variables"]["guid"] == "test-guid-12345"
