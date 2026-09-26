import os
from unittest.mock import MagicMock, patch
from package.utils.newrelic_helper import (
    record_llm_event,
    record_crawler_metrics,
    notice_error,
)
from scripts.notify_new_relic_deployment import create_deployment_payload
from scripts.setup_new_relic_crawler_alerts import (
    build_alert_policy_payload,
    build_nrql_conditions,
)


def test_record_llm_event_without_license_key():
    """NEW_RELIC_LICENSE_KEY未設定時はFalseを返し記録をスキップすること"""
    with patch.dict(os.environ, {}, clear=True):
        res = record_llm_event(
            model_name="gemini-1.5-flash",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=450.0,
            status="success",
        )
        assert res is False


def test_record_llm_event_success():
    """NEW_RELIC_LICENSE_KEY設定時にLlmEventカスタムイベントが正しく記録されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_llm_event(
                model_name="gemini-1.5-flash",
                prompt_tokens=150,
                completion_tokens=60,
                duration_ms=520.5,
                status="success",
                cost_usd=0.00012,
                metadata={"property_id": "12345", "parser": "mansion"},
            )
            assert res is True
            mock_agent.record_custom_event.assert_called_once()
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "LlmEvent"
            assert params["model"] == "gemini-1.5-flash"
            assert params["prompt_tokens"] == 150
            assert params["completion_tokens"] == 60
            assert params["total_tokens"] == 210
            assert params["duration_ms"] == 520.5
            assert params["cost_usd"] == 0.00012
            assert params["status"] == "success"
            assert params["property_id"] == "12345"


def test_record_llm_event_failure_with_error():
    """LLM呼び出し失敗時にエラー内容を含めてイベント送信されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_llm_event(
                model_name="gemini-1.5-pro",
                prompt_tokens=200,
                completion_tokens=0,
                duration_ms=1200.0,
                status="rate_limited_429",
                error_msg="Quota exceeded",
            )
            assert res is True
            _, params = mock_agent.record_custom_event.call_args[0]
            assert params["status"] == "rate_limited_429"
            assert params["error_msg"] == "Quota exceeded"


def test_record_crawler_metrics_without_license_key():
    """NEW_RELIC_LICENSE_KEY未設定時はFalseを返すこと"""
    with patch.dict(os.environ, {}, clear=True):
        res = record_crawler_metrics(
            site_name="mitsui",
            property_type="mansion",
            count=15,
            duration_sec=12.5,
        )
        assert res is False


def test_record_crawler_metrics_success():
    """クローラー実行メトリクスがCrawlerExecutionカスタムイベントとして正常に記録されること"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_crawler_metrics(
                site_name="sumifu",
                property_type="kodate",
                count=20,
                duration_sec=10.0,
                zero_count=False,
                status="success",
                metadata={"worker_id": "w-1"},
            )
            assert res is True
            event_type, params = mock_agent.record_custom_event.call_args[0]
            assert event_type == "CrawlerExecution"
            assert params["site_name"] == "sumifu"
            assert params["property_type"] == "kodate"
            assert params["count"] == 20
            assert params["duration_sec"] == 10.0
            assert params["items_per_sec"] == 2.0
            assert params["zero_count"] is False
            assert params["status"] == "success"
            assert params["worker_id"] == "w-1"


def test_notice_error():
    """notice_errorがnewrelic.agent.notice_errorを正しく呼び出すこと"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            err = ValueError("Invalid HTML response")
            res = notice_error(err, {"site": "athome", "page": 3})
            assert res is True
            mock_agent.notice_error.assert_called_once_with(err, parameters={"site": "athome", "page": 3})


def test_create_deployment_payload():
    """Change Tracking デプロイ用ペイロードの構築検証"""
    payload = create_deployment_payload(
        version="v1.2.0",
        commit="abcdef123456",
        changelog="Add New Relic Full Stack",
        user="dev-agent",
        entity_guid="ABC123GUID",
    )
    assert "query" in payload
    assert "variables" in payload
    dep = payload["variables"]["deployment"]
    assert dep["version"] == "v1.2.0"
    assert dep["commit"] == "abcdef123456"
    assert dep["description"] == "Add New Relic Full Stack"
    assert dep["user"] == "dev-agent"
    assert dep["entityGuid"] == "ABC123GUID"


def test_build_alert_policy_payload():
    """アラートポリシーのペイロード構造検証"""
    payload = build_alert_policy_payload(account_id=8553111, policy_name="RealEstate Operations")
    assert payload["variables"]["accountId"] == 8553111
    assert payload["variables"]["policy"]["name"] == "RealEstate Operations"
    assert payload["variables"]["policy"]["incidentPreference"] == "PER_CONDITION"


def test_build_nrql_conditions():
    """NRQLアラート条件の生成と構文検証"""
    conditions = build_nrql_conditions(account_id=8553111, policy_id=12345)
    assert len(conditions) >= 4

    names = [c["name"] for c in conditions]
    assert "Crawler Zero-Count Scraping Failure" in names
    assert "Crawler Parser Latency Degradation (>1.0s/item)" in names
    assert "Target Portal Blocked (403/429 Spike)" in names
    assert "Container High Memory Usage Warning" in names

    # 全クエリにNRQLが含まれていること
    for cond in conditions:
        assert "SELECT " in cond["nrql"]["query"]
        assert cond["policyId"] == 12345


def test_record_crawler_metrics_metadata_precedence():
    """metadataがstatusやcountなどのコア属性を上書きできないこと"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_crawler_metrics(
                site_name="mitsui",
                property_type="mansion",
                count=10,
                duration_sec=5.0,
                status="success",
                metadata={"status": "malicious_override", "count": 999, "extra_info": "preserved"},
            )
            assert res is True
            _, params = mock_agent.record_custom_event.call_args[0]
            assert params["status"] == "success"
            assert params["count"] == 10
            assert params["extra_info"] == "preserved"


def test_record_llm_event_metadata_precedence():
    """metadataがmodelやprompt_tokensなどのコア属性を上書きできないこと"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent

    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            res = record_llm_event(
                model_name="gemini-1.5-flash",
                prompt_tokens=100,
                completion_tokens=50,
                duration_ms=300.0,
                status="success",
                metadata={"model": "fake-model", "prompt_tokens": 0, "session_id": "sess-99"},
            )
            assert res is True
            _, params = mock_agent.record_custom_event.call_args[0]
            assert params["model"] == "gemini-1.5-flash"
            assert params["prompt_tokens"] == 100
            assert params["session_id"] == "sess-99"


def test_notify_deployment_missing_deployment_id():
    """レスポンスにdeploymentIdが存在しない場合はFalseを返すこと"""
    with patch.dict(os.environ, {"NEW_RELIC_API_KEY": "fake_api_key"}):
        with patch("scripts.notify_new_relic_deployment.send_nerdgraph_request") as mock_req:
            mock_req.return_value = {"data": {"changeTrackingCreateDeployment": {}}}
            from scripts.notify_new_relic_deployment import notify_deployment
            res = notify_deployment(version="v1.0.0", commit="123456", entity_guid="TEST_GUID")
            assert res is False


def test_notify_deployment_missing_entity_guid():
    """entity_guidが未設定の場合は送信せずにFalseを返すこと"""
    with patch.dict(os.environ, {"NEW_RELIC_API_KEY": "fake_api_key"}, clear=True):
        from scripts.notify_new_relic_deployment import notify_deployment
        res = notify_deployment(version="v1.0.0", commit="123456", entity_guid=None)
        assert res is False


def test_provision_alerts_reuses_existing_policy():
    """既存のアラートポリシーが存在する場合に再利用して正常完了すること"""
    with patch.dict(os.environ, {"NEW_RELIC_API_KEY": "fake_api_key"}):
        with patch("scripts.setup_new_relic_crawler_alerts.find_existing_policy_id", return_value=99999):
            with patch("scripts.setup_new_relic_crawler_alerts.find_existing_condition_names", return_value=set()):
                with patch("scripts.setup_new_relic_crawler_alerts.run_nerdgraph_query") as mock_query:
                    mock_query.return_value = {"data": {"alertsNrqlConditionStaticCreate": {"id": "1", "name": "c1"}}}
                    from scripts.setup_new_relic_crawler_alerts import provision_alerts
                    res = provision_alerts(account_id=8553111, policy_name="RealEstate Crawler Operations")
                    assert res is True


def test_provision_alerts_skips_existing_conditions():
    """既存の条件がすでにポリシー内に存在する場合、重複作成をスキップすること"""
    with patch.dict(os.environ, {"NEW_RELIC_API_KEY": "fake_api_key"}):
        with patch("scripts.setup_new_relic_crawler_alerts.find_existing_policy_id", return_value=99999):
            existing = {
                "Crawler Zero-Count Scraping Failure",
                "Crawler Parser Latency Degradation (>1.0s/item)",
                "Target Portal Blocked (403/429 Spike)",
                "Container High Memory Usage Warning",
            }
            with patch("scripts.setup_new_relic_crawler_alerts.find_existing_condition_names", return_value=existing):
                with patch("scripts.setup_new_relic_crawler_alerts.run_nerdgraph_query") as mock_query:
                    from scripts.setup_new_relic_crawler_alerts import provision_alerts
                    res = provision_alerts(account_id=8553111, policy_name="RealEstate Crawler Operations")
                    assert res is True
                    mock_query.assert_not_called()

