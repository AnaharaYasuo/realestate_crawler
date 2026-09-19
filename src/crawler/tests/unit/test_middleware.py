import pytest
from package.api.middleware import RateLimitMiddleware, LoggingMiddleware

@pytest.mark.asyncio
async def test_rate_limit_middleware():
    mw = RateLimitMiddleware(delay=0.1)
    context = {"url": "http://test.com"}
    
    import time
    start = time.time()
    result = await mw.process_request(context)
    end = time.time()
    
    assert result is None
    assert end - start >= 0.1

@pytest.mark.asyncio
async def test_logging_middleware_request():
    from unittest.mock import patch
    mw = LoggingMiddleware()
    context = {"method": "POST", "url": "http://test.com", "payload": {"key": "value"}}
    with patch("package.api.middleware.logger.info") as mock_log:
        result = await mw.process_request(context)
        assert result is None
        mock_log.assert_called_once()
        log_str = mock_log.call_args[0][0]
        assert "POST" in log_str
        assert "http://test.com" in log_str
        assert "key" in log_str


@pytest.mark.asyncio
async def test_logging_middleware_response():
    from unittest.mock import patch
    mw = LoggingMiddleware()
    context = {"status": 200, "url": "http://test.com", "data": "<html>success</html>"}
    with patch("package.api.middleware.logger.info") as mock_log:
        result = await mw.process_response(context)
        assert result["status"] == 200
        mock_log.assert_called_once()
        log_str = mock_log.call_args[0][0]
        assert "200" in log_str
        assert "http://test.com" in log_str
        assert "success" in log_str
