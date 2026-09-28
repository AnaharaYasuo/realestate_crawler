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
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
    assert kwargs == {"execution_date": run_pipeline.datetime.date.today()}


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


@pytest.fixture(autouse=True)
def _clear_dispatched():
    api_module._dispatched_detail_keys.clear()
    yield
    api_module._dispatched_detail_keys.clear()


def _dispatch(page, urls):
    page.parser = None
    fetch = AsyncMock(side_effect=lambda url, api_url, loop: url)
    with patch.object(page, "_fetchWithEachSession", fetch), \
         patch.object(page, "_getActiveEventLoop", return_value=None):
        result = asyncio.run(page._callApi(urls))
    return [c.args[0] for c in fetch.call_args_list], result


def test_duplicate_urls_within_page_dispatched_once():
    called, result = _dispatch(
        _DummyMiddlePage(), ["https://a/1", "https://a/2", "https://a/1"]
    )
    assert called == ["https://a/1", "https://a/2"]
    assert result == ["https://a/1", "https://a/2"]


def test_already_dispatched_url_skipped_across_instances():
    _dispatch(_DummyMiddlePage(), ["https://a/1"])
    called, _ = _dispatch(_DummyMiddlePage(), ["https://a/1", "https://a/3"])
    assert called == ["https://a/3"]


def test_same_url_for_different_detail_api_is_dispatched():
    _dispatch(_DummyMiddlePage(), ["https://a/1"])
    other = _DummyMiddlePage()
    other.api_url = "http://api.example.com/other"
    called, _ = _dispatch(other, ["https://a/1"])
    assert called == ["https://a/1"]


def test_tuple_and_list_items_use_first_element_as_url():
    called, _ = _dispatch(
        _DummyMiddlePage(), [("https://a/1", 100), ["https://a/1", 200], "https://a/2"]
    )
    assert called == ["https://a/1", "https://a/2"]


def test_claim_detail_dispatch_records_key():
    assert api_module._claim_detail_dispatch("api", "u") is True
    assert api_module._claim_detail_dispatch("api", "u") is False
    assert ("api", "u") in api_module._dispatched_detail_keys


def test_failed_fetch_releases_key_for_retry():
    page = _DummyMiddlePage()
    page.parser = None
    failing = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(page, "_fetchWithEachSession", failing), \
         patch.object(page, "_getActiveEventLoop", return_value=None), \
         pytest.raises(RuntimeError):
        asyncio.run(page._callApi(["https://a/1"]))
    assert (page.api_url, "https://a/1") not in api_module._dispatched_detail_keys

    called, _ = _dispatch(_DummyMiddlePage(), ["https://a/1"])
    assert called == ["https://a/1"]


@pytest.fixture
def _reset_active_runs(monkeypatch):
    monkeypatch.setattr(api_module, "_active_crawl_runs", 0)


def test_top_level_run_clears_previous_run_keys(_reset_active_runs):
    api_module._claim_detail_dispatch("api", "old")
    api_module._enter_crawl_run()
    assert api_module._dispatched_detail_keys == set()
    assert api_module._active_crawl_runs == 1
    api_module._exit_crawl_run()
    assert api_module._active_crawl_runs == 0


def test_nested_run_keeps_keys_of_active_run(_reset_active_runs):
    api_module._enter_crawl_run()
    api_module._claim_detail_dispatch("api", "u")
    api_module._enter_crawl_run()
    assert ("api", "u") in api_module._dispatched_detail_keys
    assert api_module._active_crawl_runs == 2
    api_module._exit_crawl_run()
    api_module._exit_crawl_run()
    assert api_module._active_crawl_runs == 0


def test_exit_without_enter_does_not_go_negative(_reset_active_runs):
    api_module._exit_crawl_run()
    assert api_module._active_crawl_runs == 0


def test_main_wraps_run_with_enter_and_exit(_reset_active_runs):
    page = _DummyMiddlePage()
    seen = []

    async def fake_run(url):
        seen.append(api_module._active_crawl_runs)
        return []

    loop = asyncio.new_event_loop()
    with patch.object(page, "_run", side_effect=fake_run), \
         patch.object(page, "_getActiveEventLoop", return_value=loop):
        page.main("http://test.example.com")
    assert seen == [1]
    assert api_module._active_crawl_runs == 0
