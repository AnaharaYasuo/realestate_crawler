import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from package.parser.smtrcParser import SmtrcMansionParser
from package.parser.baseParser import ServerDownException, LoadPropertyPageException

@pytest.mark.asyncio
async def test_smtrc_get_content_timeout_fallback():
    parser = SmtrcMansionParser()
    session = MagicMock()
    test_url = "https://www.smtrc.jp/mansion/test"

    # super()._getContent raises ServerDownException
    with patch("package.parser.baseParser.ParserBase._getContent", side_effect=ServerDownException("Target server down")), \
         patch.object(parser, "_smtrc_fetch_with_playwright", new_callable=AsyncMock) as mock_pw:
        mock_pw.return_value = b"<html><head><title>Success</title></head><body>" + b"x" * 1500 + b"</body></html>"
        content = await parser._getContent(session, test_url)
        assert len(content) > 1000
        mock_pw.assert_called_once_with(test_url)

@pytest.mark.asyncio
async def test_smtrc_get_content_waf_fallback():
    parser = SmtrcMansionParser()
    session = MagicMock()
    test_url = "https://www.smtrc.jp/mansion/test"

    with patch("package.parser.baseParser.ParserBase._getContent", side_effect=LoadPropertyPageException("HTTP Status 403 Forbidden")), \
         patch.object(parser, "_smtrc_fetch_with_playwright", new_callable=AsyncMock) as mock_pw:
        mock_pw.return_value = b"<html><head><title>Success</title></head><body>" + b"x" * 1500 + b"</body></html>"
        content = await parser._getContent(session, test_url)
        assert len(content) > 1000
        mock_pw.assert_called_once_with(test_url)
