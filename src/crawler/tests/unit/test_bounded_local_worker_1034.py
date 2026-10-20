import time
import threading
from unittest.mock import MagicMock, patch

from package.api.api import (
    ApiRegistry,
    ApiAsyncProcBase,
    _get_local_worker_concurrency,
    _wait_for_active_fire_and_forget_threads,
)


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


def test_local_worker_concurrency_config(monkeypatch):
    """CRAWLER_LOCAL_WORKER_CONCURRENCY 環境変数が正しく解釈されること"""
    monkeypatch.setenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "15")
    assert _get_local_worker_concurrency() == 15

    monkeypatch.setenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "invalid")
    assert _get_local_worker_concurrency() == 10

    monkeypatch.delenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", raising=False)
    assert _get_local_worker_concurrency() == 10


def test_local_worker_concurrency_bounds_active_threads(monkeypatch):
    """
    ディスパッチが大量に発生しても、同時に実行状態にあるスレッド数が
    CRAWLER_LOCAL_WORKER_CONCURRENCY 上限以下に保たれること
    """
    limit = 5
    monkeypatch.setenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", str(limit))
    monkeypatch.setenv("CRAWLER_FIRE_AND_FORGET", "true")

    # セマフォのリセット
    from package.api import api as api_module
    api_module._local_worker_semaphore = None

    api = DummyMiddleApi()

    active_count = 0
    max_observed_active = 0
    lock = threading.Lock()

    def slow_task(url):
        nonlocal active_count, max_observed_active
        with lock:
            active_count += 1
            max_observed_active = max(max_observed_active, active_count)
        time.sleep(0.1)
        with lock:
            active_count -= 1

    mock_child = MagicMock()
    mock_child.return_value.main.side_effect = slow_task

    with patch.object(ApiRegistry, "get", return_value=mock_child):
        # 20件のディスパッチを発行
        for i in range(20):
            api._handle_local_execution("http://localhost/dummy/child", f"https://example.com/item{i}")

        # 全スレッド完了待機
        _wait_for_active_fire_and_forget_threads(timeout=10.0)

    assert max_observed_active <= limit
    assert max_observed_active > 0
