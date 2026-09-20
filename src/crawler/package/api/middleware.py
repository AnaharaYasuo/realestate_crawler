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
        logger.debug(f"RateLimitMiddleware: sleeping {self.delay}s for {request_context.get('url')}")
        await asyncio.sleep(self.delay)
        return None
    
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        return response_context

class RetryMiddleware(CrawlerMiddleware):
    """リトライ判断ミドルウェア（簡易版）"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 10.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def process_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        return None
    
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
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
    
    async def process_request(self, request_context: Dict[str, Any]) -> Optional[Any]:
        method = request_context.get('method')
        url = request_context.get('url')
        payload = (
            request_context.get('payload')
            or request_context.get('data')
            or request_context.get('params')
            or request_context.get('detailUrl')
        )
        logger.info(f"Middleware Request: {method} {url} | Payload: {payload}")
        return None
    
    async def process_response(self, response_context: Dict[str, Any]) -> Dict[str, Any]:
        """Log a response summary by HTTP status and return the context unchanged.

        Server errors are logged as errors, other 4xx responses as warnings, and
        all remaining responses as informational messages.
        """
        status = response_context.get('status')
        url = response_context.get('url')
        data = response_context.get('data') or response_context.get('text')
        data_preview = str(data)[:1000] if data is not None else None
        log_msg = f"Middleware Response: {status} {url} | Body: {data_preview}"
        if status and status >= 500:
            logger.error(log_msg)
        elif status and status >= 400:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        return response_context

