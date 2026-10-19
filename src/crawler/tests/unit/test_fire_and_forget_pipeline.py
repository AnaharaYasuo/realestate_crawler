import time
from unittest.mock import MagicMock, patch

from package.api.api import ApiAsyncProcBase, ApiRegistry


class DummyMiddleApi(ApiAsyncProcBase):
    def _generateParser(self):
        return None

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 10

    def _getApiKey(self):
        return "/dummy/child"

    async def _treatPage(self, session, *arg):
        return []

    async def _callApi(self, url_list):
        return []

    def _getTreatPageArg(self):
        return None


def test_fire_and_forget_returns_immediately_when_enabled(monkeypatch):
    """CRAWLER_FIRE_AND_FORGET=true の場合、子タスク完了を待たずに即座に200 FireAndForgetLocal を返す"""
    monkeypatch.setenv("CRAWLER_FIRE_AND_FORGET", "true")

    api = DummyMiddleApi()

    # モック対象の子APIクラス。実行に時間がかかるシミュレーション
    mock_child_class = MagicMock()
    def slow_main(url):
        time.sleep(2.0)
    mock_child_class.return_value.main.side_effect = slow_main

    with patch.object(ApiRegistry, "get", return_value=mock_child_class):
        start_t = time.monotonic()
        url, status, msg = api._handle_local_execution("http://localhost/dummy/child", "https://example.com/item1")
        elapsed = time.monotonic() - start_t

        # 2秒待たずに即時復帰すること
        assert elapsed < 0.5
        assert url == "https://example.com/item1"
        assert status == 202
        assert msg == "FireAndForgetLocal"


def test_sync_mode_waits_for_completion_when_disabled(monkeypatch):
    """CRAWLER_FIRE_AND_FORGET=false の場合、スレッド完了を同期待機して LocalSync を返す"""
    monkeypatch.setenv("CRAWLER_FIRE_AND_FORGET", "false")
    monkeypatch.setenv("LOCAL_EXECUTION_TIMEOUT_SEC", "5.0")

    api = DummyMiddleApi()

    mock_child_class = MagicMock()
    def quick_main(url):
        time.sleep(0.1)
    mock_child_class.return_value.main.side_effect = quick_main

    with patch.object(ApiRegistry, "get", return_value=mock_child_class):
        start_t = time.monotonic()
        url, status, msg = api._handle_local_execution("http://localhost/dummy/child", "https://example.com/item1")
        elapsed = time.monotonic() - start_t

        assert elapsed >= 0.08
        assert url == "https://example.com/item1"
        assert status == 200
        assert msg == "LocalSync"


def test_sync_mode_times_out(monkeypatch):
    """CRAWLER_FIRE_AND_FORGET=false かつタイムアウト秒数超過時に 504 LocalTimeout を返す"""
    monkeypatch.setenv("CRAWLER_FIRE_AND_FORGET", "false")
    monkeypatch.setenv("LOCAL_EXECUTION_TIMEOUT_SEC", "0.2")

    api = DummyMiddleApi()

    mock_child_class = MagicMock()
    def slow_main(url):
        time.sleep(1.0)
    mock_child_class.return_value.main.side_effect = slow_main

    with patch.object(ApiRegistry, "get", return_value=mock_child_class):
        start_t = time.monotonic()
        url, status, msg = api._handle_local_execution("http://localhost/dummy/child", "https://example.com/item1")
        elapsed = time.monotonic() - start_t

        assert elapsed >= 0.2
        assert url == "https://example.com/item1"
        assert status == 504
        assert msg == "LocalTimeout"

