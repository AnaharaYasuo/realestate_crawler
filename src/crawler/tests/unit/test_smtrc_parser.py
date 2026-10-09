import pytest
from unittest.mock import AsyncMock, patch
from package.parser.smtrcParser import SmtrcMansionParser, SmtrcKodateParser, SmtrcInvestmentParser
from package.models.smtrc import SmtrcMansion, SmtrcKodate, SmtrcInvestment
from package.parser.baseParser import LoadPropertyPageException

def test_smtrc_mansion_parser():
    parser = SmtrcMansionParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcMansion)

def test_smtrc_kodate_parser():
    parser = SmtrcKodateParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcKodate)

def test_smtrc_investment_parser():
    parser = SmtrcInvestmentParser()
    item = parser.createEntity()
    assert isinstance(item, SmtrcInvestment)

@pytest.mark.asyncio
async def test_smtrc_get_content_waf_403_fallback():
    parser = SmtrcMansionParser()
    session = AsyncMock()
    test_url = "https://smtrc.jp/list/listViewLive/index?search=city&prefcode=13&bukenkind=1"

    # Simulate base _getContent raising 403 LoadPropertyPageException
    with patch("package.parser.baseParser.ParserBase._getContent", side_effect=LoadPropertyPageException("HTTP Status 403 Forbidden (Possible WAF/Bot Protection)")) as mock_base_get:
        with patch.object(parser, "_smtrc_fetch_with_playwright", new_callable=AsyncMock) as mock_playwright:
            expected_content = b"<html><body>Playwright Content" + b"x" * 1000 + b"</body></html>"
            mock_playwright.return_value = expected_content
            result = await parser._getContent(session, test_url)
            assert result == expected_content
            mock_base_get.assert_called_once_with(session, test_url)
            mock_playwright.assert_called_once_with(test_url)

