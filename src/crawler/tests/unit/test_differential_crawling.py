# -*- coding: utf-8 -*-
import asyncio
import datetime
from unittest.mock import MagicMock, patch
import pytest
from django.utils import timezone

from package.api.differential import filter_differential_items, ListItem


class MockPropertyModel:
    """Mock Django model for testing differential filter"""
    objects = MagicMock()


@pytest.fixture
def mock_db_items():
    now = timezone.now()
    yesterday = now - datetime.timedelta(days=1)
    ten_days_ago = now - datetime.timedelta(days=10)

    # In DB:
    # url1: 5000万円, crawled yesterday
    # url2: 3000万円, crawled 10 days ago (expired TTL)
    # url3: 4000万円, crawled yesterday
    records = {
        "https://example.com/item1": {"price": 50000000, "inputDateTime": yesterday},
        "https://example.com/item2": {"price": 30000000, "inputDateTime": ten_days_ago},
        "https://example.com/item3": {"price": 40000000, "inputDateTime": yesterday},
    }
    return records


def test_list_item_normalization():
    # String
    item_str = "https://example.com/prop1"
    normalized = ListItem.from_raw(item_str)
    assert normalized.url == "https://example.com/prop1"
    assert normalized.price is None

    # Tuple (url, price)
    item_tuple = ("https://example.com/prop2", 45000000)
    normalized = ListItem.from_raw(item_tuple)
    assert normalized.url == "https://example.com/prop2"
    assert normalized.price == 45000000

    # Dict
    item_dict = {"url": "https://example.com/prop3", "price": 60000000}
    normalized = ListItem.from_raw(item_dict)
    assert normalized.url == "https://example.com/prop3"
    assert normalized.price == 60000000


@pytest.mark.asyncio
async def test_filter_differential_items(mock_db_items):
    # Setup mock query
    mock_model = MagicMock()
    
    # Return dictionary of values_list for matching URLs
    def mock_filter(pageUrl__in):
        matching = []
        for u in pageUrl__in:
            if u in mock_db_items:
                matching.append({
                    "pageUrl": u,
                    "price": mock_db_items[u]["price"],
                    "inputDateTime": mock_db_items[u]["inputDateTime"],
                })
        qs = MagicMock()
        qs.values.return_value = matching
        qs.update = MagicMock(return_value=len(matching))
        return qs

    mock_model.objects.filter = mock_filter

    items = [
        "https://example.com/item_new",                      # Case 1: Brand new URL -> Fetch
        ("https://example.com/item1", 50000000),             # Case 2: Existing, price unchanged, recent -> Skip
        ("https://example.com/item3", 38000000),             # Case 3: Existing, price dropped (4000 -> 3800) -> Fetch
        "https://example.com/item2",                         # Case 4: Existing, TTL expired (10 days ago > 7 days) -> Fetch
    ]

    to_fetch, to_skip = await filter_differential_items(
        items=items,
        model_class=mock_model,
        ttl_days=7,
        force_full=False,
        enabled=True
    )

    assert "https://example.com/item_new" in to_fetch
    assert "https://example.com/item3" in to_fetch
    assert "https://example.com/item2" in to_fetch
    assert "https://example.com/item1" in to_skip
    assert len(to_fetch) == 3
    assert len(to_skip) == 1


@pytest.mark.asyncio
async def test_filter_differential_force_full(mock_db_items):
    mock_model = MagicMock()
    items = [
        "https://example.com/item1",
        "https://example.com/item_new",
    ]

    # When force_full=True, everything must be fetched
    to_fetch, to_skip = await filter_differential_items(
        items=items,
        model_class=mock_model,
        force_full=True,
        enabled=True
    )

    assert len(to_fetch) == 2
    assert len(to_skip) == 0


@pytest.mark.asyncio
async def test_filter_differential_disabled(mock_db_items):
    mock_model = MagicMock()
    items = [
        "https://example.com/item1",
        "https://example.com/item_new",
    ]

    # When enabled=False, everything must be fetched
    to_fetch, to_skip = await filter_differential_items(
        items=items,
        model_class=mock_model,
        force_full=False,
        enabled=False
    )

    assert len(to_fetch) == 2
    assert len(to_skip) == 0


@pytest.mark.asyncio
async def test_detail_page_in_place_update_and_price_history():
    from package.api.api import ParseDetailPageAsyncBase

    class DummyModel:
        objects = MagicMock()
        def __init__(self, **kwargs):
            self.id = None
            self.pageUrl = kwargs.get("pageUrl")
            self.price = kwargs.get("price")
            self.propertyName = kwargs.get("propertyName", "Test")
            self.inputDate = None
            self.inputDateTime = None
            self.updateDateTime = None
            self._state = MagicMock()
            self._state.adding = True

        def save(self):
            pass

    class DummyParser:
        def __init__(self, item):
            self._item = item
        async def parsePropertyDetailPage(self, session, url):
            return self._item
        def createEntity(self):
            return DummyModel()

    class TestDetailPage(ParseDetailPageAsyncBase):
        def __init__(self, parser, url):
            self.parser = parser
            self.url = url
            self.semaphore = asyncio.Semaphore(1)
            self._loop = None

        def _generateParser(self):
            return self.parser
        def _getCloudPararellLimit(self):
            return 1
        def _getLocalPararellLimit(self):
            return 1
        def _getTimeOutSecond(self):
            return 10
        def _getApiKey(self):
            return ""

    existing = DummyModel(pageUrl="https://example.com/prop1", price=50000000)
    existing.id = 123
    existing.inputDate = datetime.date(2026, 1, 1)
    existing.inputDateTime = datetime.datetime(2026, 1, 1, 12, 0, 0)
    DummyModel.objects.filter = MagicMock(return_value=MagicMock(first=MagicMock(return_value=existing)))

    # Parsed item with reduced price: 50000000 -> 48000000
    new_item = DummyModel(pageUrl="https://example.com/prop1", price=48000000)
    parser = DummyParser(new_item)
    proc = TestDetailPage(parser, "https://example.com/prop1")

    with patch("package.api.api.PropertyPriceHistory.objects.create") as mock_hist_create, \
         patch.object(proc, "_getActiveEventLoop", return_value=asyncio.get_event_loop()), \
         patch("aiohttp.ClientSession"):
        
        saved_item = await proc._treatPage(MagicMock())

        assert saved_item is not None
        assert saved_item.id == 123
        assert saved_item._state.adding is False
        assert saved_item.inputDate == datetime.date(2026, 1, 1)
        assert saved_item.inputDateTime == datetime.datetime(2026, 1, 1, 12, 0, 0)
        assert saved_item.updateDateTime is not None
        mock_hist_create.assert_called_once()
        call_kwargs = mock_hist_create.call_args[1]
        assert call_kwargs["property_url"] == "https://example.com/prop1"
        assert call_kwargs["old_price"] == 50000000
        assert call_kwargs["new_price"] == 48000000
        assert call_kwargs["price_diff"] == -2000000

