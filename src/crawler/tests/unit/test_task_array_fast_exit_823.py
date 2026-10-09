import os
import sys
from unittest.mock import MagicMock, patch

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

from scripts.ops.run_all_crawlers import is_last_completing_task


def test_is_last_completing_task_single_task():
    """task_count <= 1 の場合は常に最終タスク（単一実行）として判定される"""
    assert is_last_completing_task(None, 1) is True
    assert is_last_completing_task(0, 1) is True
    assert is_last_completing_task(None, 0) is True


def test_is_last_completing_task_no_execution_id():
    """実行 ID が取得できない環境では安全のため True (集計実行) と判定"""
    with patch("scripts.ops.run_all_crawlers.get_execution_id", return_value=""):
        assert is_last_completing_task(1, 5) is True


def test_is_last_completing_task_other_tasks_running():
    """他タスクに RUNNING が存在する場合、False（先行タスク）と判定"""
    with patch("scripts.ops.run_all_crawlers.get_execution_id", return_value="exec-123"), \
         patch("scripts.ops.run_all_crawlers.get_execution_date", return_value="20261010"):
        
        # モックレコード: task 0, 1, 2, 4 は COMPLETED だが task 3 が RUNNING
        rec0 = MagicMock(task_index=0, status="COMPLETED")
        rec1 = MagicMock(task_index=1, status="COMPLETED")
        rec2 = MagicMock(task_index=2, status="COMPLETED")
        rec3 = MagicMock(task_index=3, status="RUNNING")
        rec4 = MagicMock(task_index=4, status="COMPLETED")
        
        mock_objects = MagicMock()
        mock_objects.filter.return_value = [rec0, rec1, rec2, rec3, rec4]
        
        with patch("scripts.ops.run_all_crawlers.CrawlerTaskExecution.objects", mock_objects):
            # 自タスクが 1 の場合、他タスク 3 が RUNNING なので False
            assert is_last_completing_task(1, 5) is False
            # 自タスクが 4 の場合も False
            assert is_last_completing_task(4, 5) is False


def test_is_last_completing_task_all_other_tasks_finished():
    """他タスクがすべて COMPLETED または FAILED の場合、True（最終完了タスク）と判定"""
    with patch("scripts.ops.run_all_crawlers.get_execution_id", return_value="exec-123"), \
         patch("scripts.ops.run_all_crawlers.get_execution_date", return_value="20261010"):
        
        # モックレコード: task 0, 1, 2, 4 はすべて COMPLETED/FAILED
        rec0 = MagicMock(task_index=0, status="COMPLETED")
        rec1 = MagicMock(task_index=1, status="COMPLETED")
        rec2 = MagicMock(task_index=2, status="FAILED")
        rec3 = MagicMock(task_index=3, status="COMPLETED")
        rec4 = MagicMock(task_index=4, status="COMPLETED")
        
        mock_objects = MagicMock()
        mock_objects.filter.return_value = [rec0, rec1, rec2, rec3, rec4]
        
        with patch("scripts.ops.run_all_crawlers.CrawlerTaskExecution.objects", mock_objects):
            # 自タスクが 3 の場合、自分以外の 0, 1, 2, 4 はすべて終了済みなので自分が最後 (True)
            assert is_last_completing_task(3, 5) is True


def test_is_last_completing_task_db_error_fallback():
    """DB 取得失敗時は安全のため False（不要な集計重複を避ける）"""
    with patch("scripts.ops.run_all_crawlers.get_execution_id", return_value="exec-123"), \
         patch("scripts.ops.run_all_crawlers.get_execution_date", return_value="20261010"):
        
        mock_objects = MagicMock()
        mock_objects.filter.side_effect = RuntimeError("DB connection timeout")
        
        with patch("scripts.ops.run_all_crawlers.CrawlerTaskExecution.objects", mock_objects):
            assert is_last_completing_task(1, 5) is False
