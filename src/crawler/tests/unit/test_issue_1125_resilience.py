import pytest
from package.parser.baseParser import ParserBase, ListingEndedException, RateLimitedException, ServerBusyException, LoadPropertyPageException

def test_validate_http_status_allows_200_and_202():
    # Should not raise for 200 or 202
    ParserBase._validate_http_status(200, "https://example.com/item")
    ParserBase._validate_http_status(202, "https://example.com/item")

def test_validate_http_status_raises_for_errors():
    with pytest.raises(ListingEndedException):
        ParserBase._validate_http_status(404, "https://example.com/item")
    with pytest.raises(ListingEndedException):
        ParserBase._validate_http_status(410, "https://example.com/item")
    with pytest.raises(RateLimitedException):
        ParserBase._validate_http_status(429, "https://example.com/item")
    with pytest.raises(LoadPropertyPageException):
        ParserBase._validate_http_status(403, "https://example.com/item")
    with pytest.raises(ServerBusyException):
        ParserBase._validate_http_status(503, "https://example.com/item")
    with pytest.raises(LoadPropertyPageException):
        ParserBase._validate_http_status(505, "https://example.com/item")
