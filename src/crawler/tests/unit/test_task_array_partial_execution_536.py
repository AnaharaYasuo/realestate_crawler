"""
Issue #536: タスクアレイ実行時に Coordinator が他タスク実行中の共有 ProxySQL を停止しないこと、
および全タスクが同時起動する parallelism 設定であることの回帰テスト。
Issue #537: 一覧ページから抽出した詳細 URL の重複ディスパッチ防止の回帰テスト。
"""

import asyncio
import os
import re
import signal
import sys
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401

        break
    _cur = _parent

from package.api import api as api_module
from package.api.api import ParseMiddlePageAsyncBase
from scripts.ops import run_pipeline

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../terraform")
)


def _records(status_by_index):
    return [SimpleNamespace(task_index=i, status=s) for i, s in status_by_index.items()]


@pytest.fixture
def task_array(monkeypatch):
    """Coordinator (task 0) / 全 4 タスクのタスクアレイ状態を設定し、DB 取得結果を差し替える"""
    monkeypatch.setattr(run_pipeline, "_task_index", 0)
    monkeypatch.setattr(run_pipeline, "_task_count", 4)
    monkeypatch.setattr(run_pipeline, "bound_mysql_timeouts", MagicMock())
    model = MagicMock()
    monkeypatch.setattr(run_pipeline, "CrawlerTaskExecution", model)
    return model


# ---------------------------------------------------------------------------
# Issue #536: parallelism
# ---------------------------------------------------------------------------


def _tf_default(content, name):
    m = re.search(
        r'variable\s+"' + name + r'"\s*\{[^}]*?default\s*=\s*(\d+)', content, re.DOTALL
    )
    assert m, f"{name} default not found"
    return int(m.group(1))


def test_crawler_parallelism_equals_task_count():
    with open(os.path.join(TERRAFORM_DIR, "variables.tf"), encoding="utf-8") as f:
        content = f.read()
    task_count = _tf_default(content, "crawler_task_count")
    parallelism = _tf_default(content, "crawler_parallelism")
    assert task_count == 8
    assert parallelism == task_count


# ---------------------------------------------------------------------------
# Issue #536: _can_stop_shared_proxysql
# ---------------------------------------------------------------------------


def test_single_task_can_stop_without_db_query(monkeypatch):
    monkeypatch.setattr(run_pipeline, "_task_index", None)
    monkeypatch.setattr(run_pipeline, "_task_count", 1)
    model = MagicMock()
    monkeypatch.setattr(run_pipeline, "CrawlerTaskExecution", model)
    assert run_pipeline._can_stop_shared_proxysql() is True
    model.objects.filter.assert_not_called()


def test_all_other_tasks_terminal_can_stop(task_array):
    task_array.objects.filter.return_value = _records(
        {0: "RUNNING", 1: "COMPLETED", 2: "FAILED", 3: "COMPLETED"}
    )
    assert run_pipeline._can_stop_shared_proxysql() is True


def test_queries_local_execution_date_like_run_all_crawlers(task_array):
    task_array.objects.filter.return_value = _records(
        {1: "COMPLETED", 2: "COMPLETED", 3: "COMPLETED"}
    )
    run_pipeline._can_stop_shared_proxysql()
    kwargs = task_array.objects.filter.call_args.kwargs
    dt = run_pipeline.datetime
    assert kwargs == {"execution_date": dt.datetime.now(dt.timezone.utc).astimezone().date()}


def test_bounds_mysql_timeouts_before_query(task_array):
    task_array.objects.filter.return_value = _records(
        {1: "COMPLETED", 2: "COMPLETED", 3: "COMPLETED"}
    )
    run_pipeline._can_stop_shared_proxysql()
    run_pipeline.bound_mysql_timeouts.assert_called_once()


@pytest.mark.parametrize("pending_status", ["RUNNING", "PENDING", ""])
def test_other_task_not_terminal_blocks_stop(task_array, pending_status):
    task_array.objects.filter.return_value = _records(
        {0: "RUNNING", 1: "COMPLETED", 2: pending_status, 3: "COMPLETED"}
    )
    assert run_pipeline._can_stop_shared_proxysql() is False


def test_last_task_not_terminal_blocks_stop(task_array):
    task_array.objects.filter.return_value = _records(
        {1: "COMPLETED", 2: "COMPLETED", 3: "RUNNING"}
    )
    assert run_pipeline._can_stop_shared_proxysql() is False


def test_unregistered_task_blocks_stop(task_array):
    task_array.objects.filter.return_value = _records(
        {0: "RUNNING", 1: "COMPLETED", 2: "COMPLETED"}
    )
    assert run_pipeline._can_stop_shared_proxysql() is False


def test_own_task_status_is_ignored(task_array, monkeypatch):
    monkeypatch.setattr(run_pipeline, "_task_index", 2)
    task_array.objects.filter.return_value = _records(
        {0: "COMPLETED", 1: "FAILED", 3: "COMPLETED"}
    )
    assert run_pipeline._can_stop_shared_proxysql() is True


def test_db_error_blocks_stop(task_array):
    task_array.objects.filter.side_effect = RuntimeError("db down")
    assert run_pipeline._can_stop_shared_proxysql() is False


# ---------------------------------------------------------------------------
# Issue #536: teardown 経路 (finally / atexit / SIGTERM)
# ---------------------------------------------------------------------------


@pytest.fixture
def cloud_coordinator(monkeypatch):
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setattr(run_pipeline, "_is_coordinator", True)
    monkeypatch.setattr(run_pipeline, "_teardown_done", False)
    monkeypatch.setattr(run_pipeline, "_active_proc", None)


@pytest.mark.parametrize("can_stop", [True, False])
def test_safety_teardown_respects_guard(cloud_coordinator, can_stop):
    with patch.object(run_pipeline, "_can_stop_shared_proxysql", return_value=can_stop), \
         patch.object(run_pipeline, "_inline_stop_proxysql") as mock_stop, \
         patch.object(run_pipeline, "run_command") as mock_cmd:
        run_pipeline._execute_safety_teardown(is_coordinator=True, scripts_dir="/fake")
    assert mock_stop.called is can_stop
    assert mock_cmd.called is can_stop
    assert run_pipeline._teardown_done is True


@pytest.mark.parametrize("can_stop", [True, False])
def test_atexit_teardown_respects_guard(cloud_coordinator, can_stop):
    with patch.object(run_pipeline, "_can_stop_shared_proxysql", return_value=can_stop), \
         patch.object(run_pipeline, "_inline_stop_proxysql") as mock_stop:
        run_pipeline._atexit_teardown()
    assert mock_stop.called is can_stop
    assert run_pipeline._teardown_done is True


@pytest.mark.parametrize("can_stop", [True, False])
def test_sigterm_handler_respects_guard(cloud_coordinator, can_stop):
    with patch.object(run_pipeline, "_can_stop_shared_proxysql", return_value=can_stop), \
         patch.object(run_pipeline, "_inline_stop_proxysql") as mock_stop, \
         pytest.raises(SystemExit):
        run_pipeline._sigterm_handler(signal.SIGTERM, None)
    assert mock_stop.called is can_stop
    assert run_pipeline._teardown_done is True


def test_atexit_teardown_skips_guard_when_already_done(cloud_coordinator, monkeypatch):
    monkeypatch.setattr(run_pipeline, "_teardown_done", True)
    with patch.object(run_pipeline, "_can_stop_shared_proxysql") as mock_guard, \
         patch.object(run_pipeline, "_inline_stop_proxysql") as mock_stop:
        run_pipeline._atexit_teardown()
    mock_guard.assert_not_called()
    mock_stop.assert_not_called()


# ---------------------------------------------------------------------------
# Issue #537: 詳細 URL 重複ディスパッチ防止
# ---------------------------------------------------------------------------


class _DummyMiddlePage(ParseMiddlePageAsyncBase):
    api_url = "http://api.example.com/detail"

    def _getStartUrl(self):
        return "http://test.example.com"

    def _generateParser(self):
        return None

    def _getApiKey(self):
        return "dummy"

    def _getCloudPararellLimit(self):
        return 1

    def _getLocalPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 10

    def _getParserFunc(self):
        return None

    def _getApiUrl(self):
        return self.api_url


@pytest.fixture
def run_keys():
    """独立した main() 実行中の状態 (実行単位のディスパッチ済みキー集合) を再現する"""
    owns = api_module._enter_crawl_run()
    yield api_module._current_dispatch_keys()
    api_module._exit_crawl_run(owns)


def _dispatch(page, urls, result=None):
    page.parser = None
    fetch = AsyncMock(side_effect=lambda url, api_url, loop: result or url)
    with patch.object(page, "_fetchWithEachSession", fetch), \
         patch.object(page, "_getActiveEventLoop", return_value=None):
        responses = asyncio.run(page._callApi(urls))
    return [c.args[0] for c in fetch.call_args_list], responses


def test_duplicate_urls_within_page_dispatched_once_without_run():
    assert api_module._current_dispatch_keys() is None
    called, result = _dispatch(
        _DummyMiddlePage(), ["https://a/1", "https://a/2", "https://a/1"]
    )
    assert called == ["https://a/1", "https://a/2"]
    assert result == ["https://a/1", "https://a/2"]


def test_calls_outside_run_do_not_share_keys():
    _dispatch(_DummyMiddlePage(), ["https://a/1"])
    called, _ = _dispatch(_DummyMiddlePage(), ["https://a/1"])
    assert called == ["https://a/1"]


def test_already_dispatched_url_skipped_across_instances_in_run(run_keys):
    _dispatch(_DummyMiddlePage(), ["https://a/1"])
    called, _ = _dispatch(_DummyMiddlePage(), ["https://a/1", "https://a/3"])
    assert called == ["https://a/3"]
    assert run_keys == {
        (_DummyMiddlePage.api_url, "https://a/1"),
        (_DummyMiddlePage.api_url, "https://a/3"),
    }


def test_same_url_for_different_detail_api_is_dispatched(run_keys):
    _dispatch(_DummyMiddlePage(), ["https://a/1"])
    other = _DummyMiddlePage()
    other.api_url = "http://api.example.com/other"
    called, _ = _dispatch(other, ["https://a/1"])
    assert called == ["https://a/1"]


def test_tuple_and_list_items_use_first_element_as_url(run_keys):
    called, _ = _dispatch(
        _DummyMiddlePage(), [("https://a/1", 100), ["https://a/1", 200], "https://a/2"]
    )
    assert called == ["https://a/1", "https://a/2"]


def test_claim_and_release_detail_dispatch():
    keys = set()
    assert api_module._claim_detail_dispatch(keys, "api", "u") is True
    assert api_module._claim_detail_dispatch(keys, "api", "u") is False
    assert keys == {("api", "u")}
    api_module._release_detail_dispatch(keys, "api", "u")
    assert keys == set()


def test_failed_fetch_releases_key_for_retry(run_keys):
    page = _DummyMiddlePage()
    page.parser = None
    failing = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(page, "_fetchWithEachSession", failing), \
         patch.object(page, "_getActiveEventLoop", return_value=None), \
         pytest.raises(RuntimeError):
        asyncio.run(page._callApi(["https://a/1"]))
    assert run_keys == set()

    called, _ = _dispatch(_DummyMiddlePage(), ["https://a/1"])
    assert called == ["https://a/1"]


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_retryable_status_releases_key(run_keys, status):
    _dispatch(_DummyMiddlePage(), ["https://a/1"], result=("https://a/1", status, "busy"))
    assert run_keys == set()


@pytest.mark.parametrize("status", [200, 404])
def test_final_status_keeps_key(run_keys, status):
    _dispatch(_DummyMiddlePage(), ["https://a/1"], result=("https://a/1", status, "ok"))
    assert run_keys == {(_DummyMiddlePage.api_url, "https://a/1")}


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (("u", 503, "x"), True),
        (("u", 499, "x"), False),
        (("u", 200, "LocalSync"), False),
        (("u", "503", "x"), False),
        (("u",), False),
        ("u", False),
        (None, False),
    ],
)
def test_is_retryable_dispatch_result(result, expected):
    assert api_module._is_retryable_dispatch_result(result) is expected


def test_independent_runs_get_separate_keys():
    owns = api_module._enter_crawl_run()
    first = api_module._current_dispatch_keys()
    api_module._exit_crawl_run(owns)
    assert api_module._current_dispatch_keys() is None

    owns = api_module._enter_crawl_run()
    second = api_module._current_dispatch_keys()
    api_module._exit_crawl_run(owns)
    assert owns is True
    assert first is not second


def test_nested_run_reuses_parent_keys(run_keys):
    assert api_module._enter_crawl_run() is False
    assert api_module._current_dispatch_keys() is run_keys
    api_module._exit_crawl_run(False)
    assert api_module._current_dispatch_keys() is run_keys


def test_concurrent_thread_runs_are_isolated(run_keys):
    seen = {}

    def other_run():
        seen["before"] = api_module._current_dispatch_keys()
        owns = api_module._enter_crawl_run()
        seen["owns"] = owns
        seen["keys"] = api_module._current_dispatch_keys()
        api_module._exit_crawl_run(owns)

    t = threading.Thread(target=other_run)
    t.start()
    t.join()
    assert seen["before"] is None
    assert seen["owns"] is True
    assert seen["keys"] is not run_keys


def test_local_execution_child_thread_inherits_parent_keys(run_keys):
    seen = {}

    class _Child:
        def main(self, url):
            seen["keys"] = api_module._current_dispatch_keys()
            seen["url"] = url

    page = _DummyMiddlePage()
    with patch.object(api_module.ApiRegistry, "get", return_value=_Child):
        result = page._handle_local_execution("http://api.example.com/detail", "https://a/9")
    assert result == ("https://a/9", 200, "LocalSync")
    assert seen == {"keys": run_keys, "url": "https://a/9"}


def test_local_execution_failure_returns_retryable_status(run_keys):
    class _Child:
        def main(self, url):
            raise RuntimeError("boom")

    page = _DummyMiddlePage()
    with patch.object(api_module.ApiRegistry, "get", return_value=_Child):
        result = page._handle_local_execution("http://api.example.com/detail", "https://a/10")
    assert result[0] == "https://a/10"
    assert result[1] == 500
    assert result[2] != "LocalSync"
    assert api_module._is_retryable_dispatch_result(result) is True
    assert api_module._current_dispatch_keys() is run_keys


def test_local_execution_failure_releases_dispatch_key(run_keys):
    class _Child:
        def main(self, url):
            raise RuntimeError("boom")

    page = _DummyMiddlePage()
    api_url = "http://api.example.com/detail"

    async def _fetch_via_local(detail_url, _api_url, _loop):
        return page._handle_local_execution(_api_url, detail_url)

    assert api_module._claim_detail_dispatch(run_keys, api_url, "https://a/11") is True
    with patch.object(api_module.ApiRegistry, "get", return_value=_Child), patch.object(
        page, "_fetchWithEachSession", side_effect=_fetch_via_local
    ):
        asyncio.run(page._fetchDetailOnce(run_keys, "https://a/11", api_url, None))
    assert (api_url, "https://a/11") not in run_keys


def _fetch_with_post_error(page, exc):
    session = MagicMock()
    session.post = AsyncMock(side_effect=exc)
    with patch.object(page, "_handle_local_execution", return_value=None), patch.object(
        page, "_apply_middlewares_request", AsyncMock(return_value=None)
    ), patch.object(api_module.os.path, "exists", return_value=False):
        return asyncio.run(page._fetch(session, "https://a/12", "http://api.example.com/detail", None, 0))


def test_connect_timeout_is_retryable_and_not_fire_and_forget():
    result = _fetch_with_post_error(_DummyMiddlePage(), aiohttp.ConnectionTimeoutError("connect"))
    assert result[0] == "https://a/12"
    assert result[2] != "FireAndForget"
    assert api_module._is_retryable_dispatch_result(result) is True


def test_read_timeout_after_send_stays_fire_and_forget():
    result = _fetch_with_post_error(_DummyMiddlePage(), asyncio.TimeoutError())
    assert result == ("https://a/12", 200, "FireAndForget")
    assert api_module._is_retryable_dispatch_result(result) is False


def test_main_owns_run_state_only_while_running():
    page = _DummyMiddlePage()
    seen = []

    async def fake_run(url):
        seen.append(api_module._current_dispatch_keys())
        return []

    loop = asyncio.new_event_loop()
    with patch.object(page, "_run", side_effect=fake_run), \
         patch.object(page, "_getActiveEventLoop", return_value=loop):
        page.main("http://test.example.com")
    assert seen == [set()]
    assert api_module._current_dispatch_keys() is None

