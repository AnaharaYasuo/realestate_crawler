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

    # 1. 200 OK -> INFO
    context_200 = {"status": 200, "url": "http://test.com", "data": "<html>success</html>"}
    with patch("package.api.middleware.logger.info") as mock_info:
        result = await mw.process_response(context_200)
        assert result["status"] == 200
        mock_info.assert_called_once()
        log_str = mock_info.call_args[0][0]
        assert "200" in log_str

    # 2. 404 Not Found -> WARNING
    context_404 = {"status": 404, "url": "http://test.com/missing", "data": "<html>not found</html>"}
    with patch("package.api.middleware.logger.warning") as mock_warn:
        result = await mw.process_response(context_404)
        assert result["status"] == 404
        mock_warn.assert_called_once()
        log_str = mock_warn.call_args[0][0]
        assert "404" in log_str

    # 3. 500 Internal Server Error -> ERROR
    context_500 = {"status": 500, "url": "http://test.com/error", "data": "<html>server error</html>"}
    with patch("package.api.middleware.logger.error") as mock_err:
        result = await mw.process_response(context_500)
        assert result["status"] == 500
        mock_err.assert_called_once()
        log_str = mock_err.call_args[0][0]
        assert "500" in log_str

