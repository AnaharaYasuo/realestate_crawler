"""
`gemini-2.5-flash` 向けスレッドセーフ低速レートリミッタ ＆ 指数バックオフ多重リトライ制御 (Issue #1380)

方針:
- デフォルト最低リクエスト間隔 `2.0秒`（30 RPM以下、環境変数 `GEMINI_MIN_INTERVAL_SEC` で調整可能）を
  プロセス内全スレッドで共有ロック制御し、無料/低速枠でもバースト `429 RESOURCE_EXHAUSTED` を予防する。
- `429`・クォータ制限・`500/502/503/504`・タイムアウト等の一時障害時は、ジッター付き指数バックオフで
  最大 `max_retries` 回まで粘り強く自動リトライする。
- 認証エラーや不正引数などの非リトライ例外はスリープせず即座に送出する。
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 全 Gemini 呼び出し箇所の共通モデル SSOT (Issue #1782)
# 最も安定応答する gemini-flash-lite-latest をプライマリとし、段階的にフォールバックする
DEFAULT_GEMINI_PRIMARY_MODEL = "gemini-flash-lite-latest"
DEFAULT_GEMINI_FALLBACK_MODELS: tuple[str, ...] = (
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-3.8-flash",
)
DEPRECATED_GEMINI_MODELS: frozenset[str] = frozenset({
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
})


def resolve_gemini_model_chain(
    primary_model: str | None = None,
    fallback_models: Sequence[str] = DEFAULT_GEMINI_FALLBACK_MODELS,
) -> list[str]:
    """廃止モデルを自動除外し、プライマリから段階的に落とす重複なしモデル列を返す。"""
    raw_candidates: list[str] = []
    if primary_model and primary_model.strip():
        cand = primary_model.strip()
        if cand not in DEPRECATED_GEMINI_MODELS:
            raw_candidates.append(cand)
    raw_candidates.append(DEFAULT_GEMINI_PRIMARY_MODEL)
    raw_candidates.extend(fallback_models)

    chain: list[str] = []
    seen: set[str] = set()
    for model in raw_candidates:
        m = (model or "").strip()
        if not m or m in seen or m in DEPRECATED_GEMINI_MODELS:
            continue
        seen.add(m)
        chain.append(m)
    return chain


def generate_content_with_fallback(
    client: Any,
    contents: Any,
    *,
    primary_model: str | None = None,
    fallback_models: Sequence[str] = DEFAULT_GEMINI_FALLBACK_MODELS,
    config: Any = None,
    limiter: GeminiFlashRateLimiter | None = None,
) -> tuple[Any, str]:
    """google-genai SDK の generate_content を段階的フォールバックチェーンで実行する。"""
    chain = resolve_gemini_model_chain(primary_model=primary_model, fallback_models=fallback_models)
    last_exc: Exception | None = None
    for idx, model_name in enumerate(chain):
        try:
            call_kwargs: dict[str, Any] = {"model": model_name, "contents": contents}
            if config is not None:
                call_kwargs["config"] = config
            if limiter is not None:
                resp = limiter.execute(client.models.generate_content, **call_kwargs)
            else:
                resp = client.models.generate_content(**call_kwargs)
            return resp, model_name
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if idx + 1 < len(chain):
                logger.warning(
                    "Gemini call failed on %s (%s); falling back to %s",
                    model_name,
                    exc,
                    chain[idx + 1],
                )
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No valid Gemini model available in fallback chain")

_RETRYABLE_TOKENS: tuple[str, ...] = (
    "429",
    "resource_exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "500",
    "502",
    "503",
    "504",
    "unavailable",
    "deadline",
    "timed out",
    "timeout",
    "connection",
    "temporarily",
)


def is_retryable_gemini_exception(exc: BaseException) -> bool:
    """Gemini SDK / HTTP 例外がレート制限または一時障害（リトライ対象）か判定する。"""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in (429, 500, 502, 503, 504):
        return True
    msg = str(exc).lower()
    return any(tok in msg for tok in _RETRYABLE_TOKENS)


class GeminiFlashRateLimiter:
    """`gemini-2.5-flash` 呼び出し間隔と多重リトライを一元制御するスレッドセーフ・リミッタ。"""

    def __init__(
        self,
        min_interval_sec: float = 2.0,
        max_retries: int = 4,
        base_backoff_sec: float = 4.0,
        max_backoff_sec: float = 60.0,
    ) -> None:
        self.min_interval_sec = max(0.0, float(min_interval_sec))
        self.max_retries = max(0, int(max_retries))
        self.base_backoff_sec = max(0.01, float(base_backoff_sec))
        self.max_backoff_sec = max(self.base_backoff_sec, float(max_backoff_sec))
        self._lock = threading.Lock()
        self._next_allowed_mono = 0.0

    def _effective_interval(self) -> float:
        env_val = os.getenv("GEMINI_MIN_INTERVAL_SEC")
        if env_val is not None:
            try:
                return max(0.0, float(env_val))
            except ValueError:
                pass
        return self.min_interval_sec

    def wait_for_slot(self) -> None:
        """次回呼び出し許可時刻まで待機し、スロットを予約する。"""
        interval = self._effective_interval()
        if interval <= 0.0:
            return
        with self._lock:
            now = time.perf_counter()
            wait_sec = max(0.0, self._next_allowed_mono - now)
            reserved_time = max(now, self._next_allowed_mono)
            self._next_allowed_mono = reserved_time + interval
        if wait_sec > 0.0:
            time.sleep(wait_sec)

    def execute(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """最低間隔スロットを確保した上で関数を実行し、429/一時障害時は指数バックオフで再試行する。"""
        attempt = 0
        while True:
            self.wait_for_slot()
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if not is_retryable_gemini_exception(exc) or attempt >= self.max_retries:
                    raise
                backoff = min(
                    self.max_backoff_sec,
                    self.base_backoff_sec * (2 ** attempt) * random.uniform(0.85, 1.15),
                )
                attempt += 1
                logger.warning(
                    "Gemini 2.5 Flash transient/rate-limit error (%s); retry %d/%d in %.2fs",
                    exc,
                    attempt,
                    self.max_retries,
                    backoff,
                )
                time.sleep(backoff)


_DEFAULT_LIMITER = GeminiFlashRateLimiter(min_interval_sec=2.0, max_retries=4, base_backoff_sec=4.0)


def get_gemini_flash_limiter() -> GeminiFlashRateLimiter:
    """プロセス共有の既定 `GeminiFlashRateLimiter` シングルトンを返す。"""
    return _DEFAULT_LIMITER
