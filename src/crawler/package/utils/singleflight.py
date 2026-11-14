import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class SingleflightGroup:
    """
    同一キー（URL等）に対する並行処理を合流させ、
    重複実行を防止して先行処理の結果を後続処理へ共有する機構
    """
    def __init__(self):
        self._calls: dict[str, asyncio.Future] = {}
        self._lock: asyncio.Lock | None = None
        self._lock_loop: asyncio.AbstractEventLoop | None = None

    def _get_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop or self._lock_loop.is_closed():
            self._lock = asyncio.Lock()
            self._lock_loop = loop
            self._calls.clear()
        return self._lock

    async def do(self, key: str, fn: Callable, *args, **kwargs) -> Any:
        """
        key に対して処理を実行。すでに同一 key が実行中であれば完了を待機して結果を返却
        """
        lock = self._get_lock()
        async with lock:
            if key in self._calls:
                future = self._calls[key]
                if not future.cancelled() and getattr(future, "get_loop", lambda: None)() is asyncio.get_running_loop():
                    # 先行タスクの完了を待機
                    logger.debug("[Singleflight] Coalescing request for key: %s", key)
                    return await asyncio.shield(future)

            # 先頭リクエスト: Future を作成
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._calls[key] = future

        try:
            # 実際の非同期処理を実行
            if asyncio.iscoroutinefunction(fn):
                res = await fn(*args, **kwargs)
            else:
                res = fn(*args, **kwargs)

            if not future.done():
                future.set_result(res)
            return res
        except Exception as e:
            if not future.done():
                future.set_exception(e)
            raise
        finally:
            async with self._get_lock():
                self._calls.pop(key, None)
