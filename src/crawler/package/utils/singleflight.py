# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Any, Callable, Dict


class SingleflightGroup:
    """
    同一キー（URL等）に対する並行処理を合流させ、
    重複実行を防止して先行処理の結果を後続処理へ共有する機構
    """
    def __init__(self):
        self._calls: Dict[str, asyncio.Future] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def do(self, key: str, fn: Callable, *args, **kwargs) -> Any:
        """
        key に対して処理を実行。すでに同一 key が実行中であれば完了を待機して結果を返却
        """
        async with self._lock:
            if key in self._calls:
                future = self._calls[key]
                # 先行タスクの完了を待機
                logging.debug(f"[Singleflight] Coalescing request for key: {key}")
                return await asyncio.shield(future)

            # 先頭リクエスト: Future を作成
            loop = asyncio.get_event_loop()
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
            raise e
        finally:
            async with self._lock:
                self._calls.pop(key, None)
