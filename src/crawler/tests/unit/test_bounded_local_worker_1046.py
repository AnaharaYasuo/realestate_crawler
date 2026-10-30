import time
import threading
from unittest.mock import MagicMock, patch

from package.api.api import (
    ApiRegistry,
    ApiAsyncProcBase,
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


def test_local_worker_executor_bounds_threads(monkeypatch):
    """
    Issue #1046: ディスパッチが大量（例: 50件）に発生しても、
    無制限にthreading.Threadを生成せず、固定ワーカープール(ThreadPoolExecutor)
    によって実行され、OSスレッド乱立が防止されること
    """
    limit = 5
    monkeypatch.setenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", str(limit))
    monkeypatch.setenv("CRAWLER_FIRE_AND_FORGET", "true")

    from package.api import api as api_module
    # エグゼキュータのリセット
    if api_module._local_worker_executor is not None:
        api_module._local_worker_executor.shutdown(wait=False)
        api_module._local_worker_executor = None

    api = DummyMiddleApi()

    active_count = 0
    max_observed_active = 0
    created_thread_names = set()
    lock = threading.Lock()

    def slow_task(url):
        nonlocal active_count, max_observed_active
        curr_name = threading.current_thread().name
        with lock:
            created_thread_names.add(curr_name)
            active_count += 1
            max_observed_active = max(max_observed_active, active_count)
        time.sleep(0.05)
        with lock:
            active_count -= 1

    mock_child = MagicMock()
    mock_child.return_value.main.side_effect = slow_task

    with patch.object(ApiRegistry, "get", return_value=mock_child):
        # 50件のディスパッチを発行
        for i in range(50):
            api._handle_local_execution("http://localhost/dummy/child", f"https://example.com/item{i}")

        # 全タスク完了待機
        _wait_for_active_fire_and_forget_threads(timeout=10.0)

    # 同時実行スレッド数がlimit以下であること
    assert max_observed_active <= limit
    assert max_observed_active > 0
    # スレッドが50本作られず、固定プール（ワーカー名 crawler-worker-*）で使い回されていること
    assert len(created_thread_names) <= limit + 1
