from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

class CrawlerMiddleware(ABC):
    """ミドルウェアの基底クラス"""
    
    @abstractmethod
    async def process_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        """リクエスト前処理。None以外を返すと処理を中断しその値を返却します。"""
        pass
    
    @abstractmethod
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        """レスポンス後処理"""
        pass

class RateLimitMiddleware(CrawlerMiddleware):
    """レート制限ミドルウェア"""
    
    def __init__(self, delay: float = 1.0):
        self.delay = delay
    
    async def process_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        """リクエスト送信前に指定秒数ウェイトします。"""
        logger.debug(f"RateLimitMiddleware: sleeping {self.delay}s for {request_context.get('url')}")
        await asyncio.sleep(self.delay)
        return None
    
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        """レスポンスコンテキストをそのまま返却します。"""
        return response_context

class RetryMiddleware(CrawlerMiddleware):
    """リトライ判断ミドルウェア（簡易版）"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 10.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def process_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        """リクエスト送信前の前処理を行います。"""
        return None
    
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        """5xxサーバーエラー時にリトライ判定を行います。"""
        status = response_context.get('status')
        if status and status >= 500:
            retry_count = response_context.get('retry_count', 0)
            if retry_count < self.max_retries:
                logger.warning(f"RetryMiddleware: Server error {status}, retrying {retry_count + 1}/{self.max_retries}")
                await asyncio.sleep(self.retry_delay)
                response_context['should_retry'] = True
                response_context['retry_count'] = retry_count + 1
        return response_context

class LoggingMiddleware(CrawlerMiddleware):
    """ログ記録ミドルウェア（リクエスト・レスポンスの送受信ペイロードを出力）"""
    
    @staticmethod
    def _sanitize_log_body(body: Any, max_len: int = 1000) -> str | None:
        if body is None:
            return None
        # 改行・連続空白を単一スペースに圧縮して、Cloud Loggingでの複数行分割を防ぐ
        cleaned = " ".join(str(body).split())
        if len(cleaned) > max_len:
            suffix = f"... (truncated, total {len(cleaned)} chars)"
            avail = max_len - len(suffix)
            if avail > 0:
                return cleaned[:avail] + suffix
            return cleaned[:max_len]
        return cleaned

    async def process_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        """リクエスト送信内容をINFOログに出力します。"""
        method = request_context.get('method')
        url = request_context.get('url')
        raw_payload = (
            request_context.get('payload')
            or request_context.get('data')
            or request_context.get('params')
            or request_context.get('detailUrl')
        )
        payload = self._sanitize_log_body(raw_payload, max_len=1000)
        logger.info(f"Middleware Request: {method} {url} | Payload: {payload}")
        return None
    
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        """レスポンスステータスに応じて適切な重大度 (2xx/3xx: INFO, 4xx: WARNING, 5xx: ERROR) でログ出力します。"""
        status = response_context.get('status')
        url = response_context.get('url')
        data = response_context.get('data') or response_context.get('text')
        data_preview = self._sanitize_log_body(data, max_len=1000)
        log_msg = f"Middleware Response: {status} {url} | Body: {data_preview}"
        if status and status >= 500:
            logger.error(log_msg)
        elif status and status >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        return response_context

