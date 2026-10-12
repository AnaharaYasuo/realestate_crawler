# -*- coding: utf-8 -*-
"""
Issue #883: Bulk ML iterator connection timeout & crawler fast-fail tests
"""
from unittest.mock import MagicMock

from package.ml.evaluation.targets import iter_unprocessed_chunks


def test_iter_active_items_refreshes_connections(monkeypatch):
    """チャンク取得・走査時に close_old_connections が定期的に呼ばれることの検証"""
    mock_items = []
    for i in range(25):
        m = MagicMock()
        m.pk = i + 1
        m.pageUrl = f"https://example.com/property/{i + 1}"
        mock_items.append(m)

    mock_model = MagicMock()
    mock_model.objects.all.return_value.order_by.return_value.iterator.return_value = iter(mock_items)

    close_conn_called = []
    monkeypatch.setattr("package.ml.evaluation.targets.close_old_connections", lambda: close_conn_called.append(True))

    chunks = list(iter_unprocessed_chunks(
        model=mock_model,
        existing_eval_map={},
        force=False,
        limit=None,
        chunk_size=10,
    ))

    assert len(chunks) == 3
    # チャンクごとに close_old_connections が呼ばれていること
    assert len(close_conn_called) >= 3


def test_watchdog_killed_failure_classification():
    """Watchdogでキルされた子プロセスが正しく判定されることの検証"""
    from package.utils.crawler_watchdog import check_job_hung

    # 600秒経過
    assert check_job_hung(last_activity_time=100.0, current_time=705.0, threshold_sec=600.0) is True
    # 599秒経過
    assert check_job_hung(last_activity_time=100.0, current_time=699.0, threshold_sec=600.0) is False
