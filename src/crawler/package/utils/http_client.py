# -*- coding: utf-8 -*-
"""
共通HTTPクライアントモジュール (package.utils.http_client)

クローラー・パーサーにおける HTTP リクエストの共通化、最適化ヘッダー自動付与、
MIMEタイプ (Content-Type) による早期切断 (Fast Abort)、サイズ上限ガードレールを提供する。
"""

import asyncio
import collections.abc
import logging
from typing import Any, Callable, Sequence
import aiohttp
import requests

logger = logging.getLogger(__name__)

# ブラウザ互換の最適化リクエストヘッダー
DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,application/json;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# クローラーが取得を許可する MIME タイプ（HTML, XML, JSON, テキスト）
ALLOWED_CONTENT_TYPES: Sequence[str] = (
    "text/html",
    "application/xhtml+xml",
    "application/json",
    "text/xml",
    "application/xml",
    "text/plain",
)

# デフォルトの最大ペイロードサイズ (10MB)
DEFAULT_MAX_PAYLOAD_BYTES = 10 * 1024 * 1024

# デフォルトの最大画像サイズ (5MB)
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024


class FastAbortNonHtmlException(Exception):
    """許可されていない Content-Type（PDF, 動画, アーカイブ等）を受信した際の早期切断例外"""
    def __init__(self, content_type: str, url: str):
        super().__init__(f"Aborted non-HTML/data resource with Content-Type '{content_type}': {url}")
        self.content_type = content_type
        self.url = url


class MaxPayloadExceededException(Exception):
    """レスポンスサイズが許容上限を超過した際の例外"""
    def __init__(self, size: int, max_size: int, url: str):
        super().__init__(f"Payload size {size} exceeded maximum limit {max_size} bytes: {url}")
        self.size = size
        self.max_size = max_size
        self.url = url


def is_allowed_content_type(content_type_header: str) -> bool:
    """Content-Type ヘッダー値がクローラーの許可リストに合致するか判定する"""
    if not content_type_header:
        # Content-Typeが省略されている場合、HTMLの可能性があるため許容
        return True
    lower_ct = content_type_header.lower()
    return any(allowed in lower_ct for allowed in ALLOWED_CONTENT_TYPES)


async def async_fetch_html_or_data(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: aiohttp.ClientTimeout | float | int | None = None,
    ssl: bool | object | None = None,
    raise_on_non_html: bool = False,
    max_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
    status_validator: Callable[[int, str], None] | None = None,
) -> bytes:
    """
    aiohttp.ClientSession を用いて非同期に HTML/JSON/XML データを取得する共通関数。

    - 最適化ヘッダーをマージして送信
    - asyncio.timeout コンテキストマネージャでタイムアウト管理 (Sonar S7483)
    - ステータスコードの検証 (status_validator 指定時)
    - Content-Type ヘッダーを確認し、許可リスト外（PDF・動画など）の場合は即座に Fast Abort
    - Content-Length または読み込みサイズが max_bytes を超える場合は即座に遮断
    """
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    timeout_sec = 20.0
    if isinstance(timeout, (int, float)):
        timeout_sec = float(timeout)
    elif isinstance(timeout, aiohttp.ClientTimeout) and timeout.total is not None:
        timeout_sec = float(timeout.total)

    kwargs: dict[str, Any] = {"headers": merged_headers}
    if ssl is not None:
        kwargs["ssl"] = ssl

    async with asyncio.timeout(timeout_sec):
        async with session.get(url, **kwargs) as response:
            if status_validator is not None and response.status not in (200, 202):
                status_validator(response.status, url)

            content_type = response.headers.get("Content-Type", "")

            # 1. Content-Type 早期判定 (Fast Abort)
            if not is_allowed_content_type(content_type):
                response.close()
                logger.warning(
                    "Fast Abort: Skipping non-allowed resource '%s' (Content-Type: %s)",
                    url,
                    content_type,
                )
                if raise_on_non_html:
                    raise FastAbortNonHtmlException(content_type, url)
                return b""

            # 2. Content-Length による事前サイズ上限チェック
            content_length = response.content_length
            if isinstance(content_length, (int, float)) and content_length > max_bytes:
                response.close()
                logger.warning(
                    "Payload Exceeded: Content-Length %d exceeds max_bytes %d for %s",
                    content_length,
                    max_bytes,
                    url,
                )
                raise MaxPayloadExceededException(int(content_length), max_bytes, url)

            # 3. 読み込み (read() による取得およびサイズガード)
            body = await response.read()
            if len(body) > max_bytes:
                response.close()
                logger.warning(
                    "Payload Exceeded: Read bytes %d exceeded max_bytes %d for %s",
                    len(body),
                    max_bytes,
                    url,
                )
                raise MaxPayloadExceededException(len(body), max_bytes, url)
            return body


def _is_valid_image_response(resp: Any, max_bytes: int, url: str) -> bool:
    """画像レスポンスのヘッダー（Content-Type, Content-Length）を検査する"""
    raw_headers = getattr(resp, "headers", None)
    if not isinstance(raw_headers, (dict, collections.abc.Mapping)):
        return True

    content_type = str(raw_headers.get("Content-Type", "")).lower()
    if content_type and not content_type.startswith("image/"):
        logger.warning("Rejected non-image Content-Type '%s' for URL: %s", content_type, url)
        return False

    content_length_str = raw_headers.get("Content-Length")
    if content_length_str and str(content_length_str).isdigit():
        content_length = int(content_length_str)
        if content_length > max_bytes:
            logger.warning("Rejected oversized image (%d bytes > max %d) for URL: %s", content_length, max_bytes, url)
            return False
    return True


def _read_image_payload(resp: Any, max_bytes: int, url: str) -> bytes | None:
    """レスポンスオブジェクトから安全に画像バイト列を読み出す"""
    raw_content = getattr(resp, "content", None)
    if isinstance(raw_content, (bytes, bytearray)):
        return bytes(raw_content) if len(raw_content) <= max_bytes else None

    if hasattr(resp, "iter_content") and callable(resp.iter_content):
        content = bytearray()
        for chunk in resp.iter_content(chunk_size=32 * 1024):
            if chunk and isinstance(chunk, (bytes, bytearray)):
                content.extend(chunk)
                if len(content) > max_bytes:
                    logger.warning("Oversized image stream (%d bytes > max %d) for URL: %s", len(content), max_bytes, url)
                    return None
        return bytes(content) if content else None
    return None


def fetch_image_bytes(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
    max_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
) -> bytes | None:
    """
    画像URLからバイナリを取得する共通関数。

    - Content-Length を事前チェックし、max_bytes（デフォルト5MB）を超える場合はスキップ
    - Content-Type が image/* であることを検証
    """
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    try:
        try:
            resp = requests.get(url, headers=merged_headers, timeout=timeout, stream=True)
        except TypeError:
            resp = requests.get(url, timeout=timeout)

        if resp.status_code != 200:
            return None

        if not _is_valid_image_response(resp, max_bytes, url):
            return None

        return _read_image_payload(resp, max_bytes, url)
    except Exception as e:
        logger.debug("Failed to fetch image from %s: %s", url, e)
        return None
