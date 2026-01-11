import pytest
import asyncio
from package.api.middleware import RateLimitMiddleware, LoggingMiddleware
from typing import Dict, Any

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
    mw = LoggingMiddleware()
    context = {"method": "GET", "url": "http://test.com"}
    result = await mw.process_request(context)
    assert result is None

@pytest.mark.asyncio
async def test_logging_middleware_response():
    mw = LoggingMiddleware()
    context = {"status": 200, "url": "http://test.com"}
    result = await mw.process_response(context)
    assert result["status"] == 200
