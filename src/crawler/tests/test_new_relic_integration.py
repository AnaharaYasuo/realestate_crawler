import os
from unittest.mock import MagicMock, patch
from main import app
from package.utils.newrelic_helper import init_new_relic


def test_init_new_relic_without_license_key():
    """NEW_RELIC_LICENSE_KEY未設定時は初期化をスキップしFalseを返すこと"""
    with patch.dict(os.environ, {}, clear=True):
        if "NEW_RELIC_LICENSE_KEY" in os.environ:
            del os.environ["NEW_RELIC_LICENSE_KEY"]
        result = init_new_relic()
        assert result is False


def test_init_new_relic_with_license_key():
    """NEW_RELIC_LICENSE_KEY設定時はnewrelic.agent.initialize()を呼び出しTrueを返すこと"""
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent
    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_license_key", "NEW_RELIC_APP_NAME": "test-app"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            result = init_new_relic()
            assert result is True
            mock_agent.initialize.assert_called_once()


def test_init_new_relic_exception_handling():
    """newrelic.agent.initialize()が例外をスローした場合、安全に例外を補足してFalseを返すこと"""
    mock_agent = MagicMock()
    mock_agent.initialize.side_effect = RuntimeError("Initialization error")
    mock_module = MagicMock()
    mock_module.agent = mock_agent
    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": "fake_key", "NEW_RELIC_APP_NAME": "test-app"}):
        with patch.dict("sys.modules", {"newrelic": mock_module, "newrelic.agent": mock_agent}):
            result = init_new_relic()
            assert result is False


def test_health_check_endpoint():
    """GET /health が200 OKとJSONステータスを返すこと"""
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data.get("status") == "ok"
    assert "timestamp" in data


def test_root_endpoint_health():
    """GET / が200 OKとJSONステータスを返すこと"""
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert data.get("status") == "ok"


def test_health_check_bypasses_auth_in_cloud_mode():
    """IS_CLOUD環境下でもヘルスチェックエンドポイントが認証なしで200を返すこと"""
    with patch.dict(os.environ, {"IS_CLOUD": "true", "ESTIMATION_API_KEY": "secret-key-123"}):
        client = app.test_client()
        # ヘルスチェックはキーなしでアクセス可能
        resp_health = client.get("/health")
        assert resp_health.status_code == 200
        assert resp_health.get_json()["status"] == "ok"

        # 通常のAPIは認証キーなしだと401/403/500等で拒否される
        resp_api = client.get("/api/sumifu/mansion/start")
        assert resp_api.status_code in (401, 403)
