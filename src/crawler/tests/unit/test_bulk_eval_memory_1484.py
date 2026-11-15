import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from package.parser.kenbiyaParser import KenbiyaInvestmentApartmentParser


@pytest.mark.asyncio
async def test_kenbiya_playwright_blocks_static_assets():
    """KenbiyaParserBase._fetch_with_playwright において静的アセット遮断ルートが登録されることを検証 (Issue #1484)"""
    parser = KenbiyaInvestmentApartmentParser()

    mock_page = AsyncMock()
    mock_page.route = AsyncMock()
    mock_page.content = AsyncMock(return_value="<html><body>Kenbiya Test</body></html>")
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.add_init_script = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_playwright_ctx = AsyncMock()
    mock_playwright_ctx.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_async_pw = MagicMock()
    mock_async_pw.return_value.__aenter__.return_value = mock_playwright_ctx
    mock_async_pw.return_value.__aexit__.return_value = None

    with patch.dict(
        "sys.modules",
        {"playwright.async_api": MagicMock(async_playwright=mock_async_pw)},
    ):
        result = await parser._fetch_with_playwright(
            "https://www.kenbiya.com/pp1/test/"
        )

    assert b"Kenbiya Test" in result
    assert mock_page.route.call_count >= 1
    args, _kwargs = mock_page.route.call_args
    pattern, _handler = args
    assert isinstance(pattern, re.Pattern)
    # 静的アセットの拡張子に一致することを確認
    assert pattern.search("https://www.kenbiya.com/images/sample.jpg") is not None
    assert pattern.search("https://www.kenbiya.com/images/sample.png") is not None
    assert pattern.search("https://www.kenbiya.com/css/main.css") is not None
    assert pattern.search("https://www.kenbiya.com/fonts/fontawesome.woff2") is not None
    # HTMLページやAPIリクエストには一致しないことを確認
    assert pattern.search("https://www.kenbiya.com/pp1/s/tokyo/re_12345/") is None


def test_run_ml_pipeline_eval_concurrency_arg():
    """run_ml_pipeline.py が eval_cmd に --concurrency 2 を渡すことを検証 (Issue #1484)"""
    import inspect
    from scripts.ops import run_ml_pipeline

    source = inspect.getsource(run_ml_pipeline.main)
    assert "--concurrency" in source
    assert "eval_concurrency" in source
