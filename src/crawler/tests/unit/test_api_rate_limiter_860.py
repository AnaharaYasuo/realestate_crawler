import asyncio
import threading
import time
import pytest

from package.api.api import ParseDetailPageAsyncBase


class DummyDetailApi(ParseDetailPageAsyncBase):
    def __init__(self, company_name: str):
        super().__init__()
        self.company = company_name

    def _generateParser(self):
        return None

    def _getLocalPararellLimit(self) -> int:
        return 1

    def _getCloudPararellLimit(self) -> int:
        return 1

    def _getTimeOutSecond(self) -> int:
        return 30

    def _getApiKey(self):
        return "/test"

    async def _treatPage(self, _session, *arg):
        return None

    def _getTreatPageArg(self):
        return None

    async def _callApi(self, url_list):
        return []

    def _getParserFunc(self):
        return None


@pytest.mark.asyncio
async def test_apply_download_delay_multi_event_loop_concurrency():
    """異なるスレッド・異なるイベントループから並行呼び出しされても RuntimeError が起きないことを検証 (Issue #860)"""
    errors = []
    durations = []

    def run_in_thread(company: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def worker():
            api = DummyDetailApi(company)
            t0 = time.monotonic()
            await api._apply_download_delay_if_needed()
            t1 = time.monotonic()
            durations.append(t1 - t0)

        try:
            loop.run_until_complete(worker())
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        finally:
            loop.close()

    threads = []
    for _ in range(4):
        t = threading.Thread(target=run_in_thread, args=("mitsui",))
        threads.append(t)

    delay = ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS.get("mitsui", 0.5)
    t_start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t_end = time.monotonic()

    # エラーが1件も発生していないこと（Lock is bound to a different event loop 等）
    assert len(errors) == 0, f"Errors occurred during multi-loop rate limiting: {errors}"
    # レートリミットにより、4スレッド順次実行で最低3 * delay - 0.2 秒以上分散されていること
    total_elapsed = t_end - t_start
    min_expected = max(0.8, 3 * delay - 0.3)
    assert total_elapsed >= min_expected, f"Rate limiting delay not respected: total_elapsed={total_elapsed}, min_expected={min_expected}"
