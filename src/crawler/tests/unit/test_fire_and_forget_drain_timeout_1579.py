import pytest
from unittest.mock import patch, MagicMock
from package.api.api import (
    _get_fire_and_forget_drain_timeout,
    _wait_for_active_fire_and_forget_threads,
)


def test_get_fire_and_forget_drain_timeout_defaults_and_env():
    with patch.dict("os.environ", {}, clear=True):
        assert _get_fire_and_forget_drain_timeout() == 300.0

    with patch.dict("os.environ", {"CRAWLER_FIRE_AND_FORGET_DRAIN_TIMEOUT": "60.0"}):
        assert _get_fire_and_forget_drain_timeout() == 60.0

    with patch.dict("os.environ", {"CRAWLER_FIRE_AND_FORGET_DRAIN_TIMEOUT": "invalid"}):
        assert _get_fire_and_forget_drain_timeout() == 300.0


def test_wait_for_active_threads_applies_drain_timeout():
    mock_fut = MagicMock()
    mock_fut.done.return_value = False

    with patch("package.api.api._poll_active_threads", return_value=[mock_fut]), \
         patch("package.api.api._cancel_unstarted_futures_on_stop") as mock_cancel, \
         patch("package.api.api._check_wait_results") as mock_check, \
         patch("package.api.api._get_fire_and_forget_wait_timeout", return_value=7200.0), \
         patch("package.api.api._get_fire_and_forget_drain_timeout", return_value=0.1), \
         patch("time.sleep", return_value=None):
        _wait_for_active_fire_and_forget_threads()
        assert mock_cancel.called
        assert mock_check.called
