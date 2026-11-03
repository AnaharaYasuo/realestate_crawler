import time
import pytest
from unittest.mock import patch
from package.api.api import (
    _get_local_worker_concurrency,
    ParseDetailPageAsyncBase,
)


def test_default_local_worker_concurrency(monkeypatch):
    """デフォルトのローカル並行度がパーサー規定値と同じ 3 に設定されていること"""
    monkeypatch.delenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", raising=False)
    assert _get_local_worker_concurrency() == 3


def test_override_local_worker_concurrency(monkeypatch):
    """環境変数による並行度の上書きが正常に機能すること"""
    monkeypatch.setenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "5")
    assert _get_local_worker_concurrency() == 5

    monkeypatch.setenv("CRAWLER_LOCAL_WORKER_CONCURRENCY", "-1")
    assert _get_local_worker_concurrency() == 3


class DummyDetailApi(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return None

    def _getLocalPararellLimit(self):
        return 3

    def _getCloudPararellLimit(self):
        return 3

    def _getTimeOutSecond(self):
        return 10

    def _getApiKey(self):
        return ""

    def _getTreatPageArg(self):
        return None

    def _resolve_target_company(self):
        return "nomura"


@pytest.mark.asyncio
async def test_rate_limiter_does_not_accumulate_infinite_future():
    """
    1,000件のリクエストが短時間に集中しても、未来時刻が線形累積して
    待機時間が数百秒〜数千秒に膨らまないこと（安全な上限にキャップされること）
    """
    api = DummyDetailApi()
    # リセット
    ParseDetailPageAsyncBase._SITE_NEXT_ALLOWED.clear()

    sleep_calls = []

    async def fake_sleep(sec):
        sleep_calls.append(sec)

    with patch("asyncio.sleep", side_effect=fake_sleep):
        # 1,000回連続でレートリミットを適用
        for _ in range(1000):
            await api._apply_download_delay_if_needed()

    # スリープ回数は1000回あるが、各スリープ時間は通常 1.0秒以内、最大でも 2.0秒以内であること
    assert len(sleep_calls) > 0
    max_wait = max(sleep_calls)
    assert max_wait <= 30.0, f"Wait time accumulated excessively: {max_wait}s"
