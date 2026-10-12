# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from package.api.differential import ListItem, filter_differential_items, DIFFERENTIAL_CHUNK_SIZE


@pytest.mark.asyncio
async def test_filter_differential_items_chunk_size_constant():
    assert DIFFERENTIAL_CHUNK_SIZE == 200


@pytest.mark.asyncio
async def test_filter_differential_items_batches_in_chunks_of_200():
    # 550 items: should be processed in chunks (200, 200, 150)
    items = [ListItem(url=f"https://example.com/prop_{i}", price=50000000) for i in range(550)]
    mock_model = MagicMock()
    mock_model.__name__ = "TestModel"

    # Simulate existing items
    existing_records = {
        item.url: {
            "pageUrl": item.url,
            "price": item.price,
            "updateDateTime": None,
            "inputDateTime": None,
        }
        for item in items
    }

    batch_update_calls = []

    async def fake_batch_update(model_class, to_skip, now):
        batch_update_calls.append(list(to_skip))

    with patch("package.api.differential._batch_update_cached", side_effect=fake_batch_update), \
         patch("package.api.differential.sync_to_async") as mock_sync:
        mock_sync.return_value = AsyncMock(return_value=existing_records)
        
        to_fetch, to_skip = await filter_differential_items(
            items=items,
            model_class=mock_model,
            ttl_days=30,
            force_full=False,
            enabled=True,
            chunk_size=200,
        )

        assert len(to_fetch) == 0
        assert len(to_skip) == 550
        # Check that updates occurred in 3 batches: 200, 200, 150
        assert len(batch_update_calls) == 3
        assert len(batch_update_calls[0]) == 200
        assert len(batch_update_calls[1]) == 200
        assert len(batch_update_calls[2]) == 150


@pytest.mark.asyncio
async def test_middle_page_streams_in_200_chunks():
    from package.api.api import ParseMiddlePageAsyncBase

    class DummyMiddlePage(ParseMiddlePageAsyncBase):
        def _getLocalPararellLimit(self):
            return 1
        def _getCloudPararellLimit(self):
            return 1
        def _generateParser(self):
            return None
        def _getTimeOutSecond(self):
            return 60
        def _getApiKey(self):
            return "detail"
        def _getTreatPageArg(self):
            return None
        def _getParserFunc(self):
            async def generator(_response):
                for i in range(450):
                    yield f"https://example.com/prop_{i}"
            return generator

    instance = DummyMiddlePage()
    call_api_chunks = []

    async def fake_call_api(chunk):
        call_api_chunks.append(list(chunk))
        return ["ok"] * len(chunk)

    instance._callApi = fake_call_api
    instance._fetch_middle_page_response = AsyncMock(return_value="<html></html>")
    instance._extract_next_page_url = AsyncMock(return_value="")

    results = await instance._run("https://example.com/middle")

    assert len(results) == 450
    # 450 items streamed in chunks: 200, 200, 50
    assert len(call_api_chunks) == 3
    assert len(call_api_chunks[0]) == 200
    assert len(call_api_chunks[1]) == 200
    assert len(call_api_chunks[2]) == 50

