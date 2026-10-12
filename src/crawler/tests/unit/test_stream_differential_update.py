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
