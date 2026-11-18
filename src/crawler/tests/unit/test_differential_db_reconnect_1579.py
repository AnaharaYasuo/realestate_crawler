import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError


def test_differential_query_reconnects_on_lost_connection():
    from package.api.differential import _query_existing_records_sync

    mock_model = MagicMock()
    mock_qs = MagicMock()
    # 1回目は Lost connection、2回目は成功
    mock_qs.values.side_effect = [
        OperationalError(2013, "Lost connection to server during query"),
        [{"pageUrl": "https://example.com/item1", "price": 1000, "updateDateTime": None, "inputDateTime": None}],
    ]
    mock_model.objects.filter.return_value = mock_qs

    with patch("django.db.connection.close") as mock_close:
        res = _query_existing_records_sync(mock_model, ["https://example.com/item1"])
        assert "https://example.com/item1" in res
        assert mock_close.call_count == 1
        assert mock_model.objects.filter.call_count == 2


def test_differential_query_raises_if_reconnect_also_fails():
    from package.api.differential import _query_existing_records_sync

    mock_model = MagicMock()
    mock_qs = MagicMock()
    # 2回連続で失敗
    mock_qs.values.side_effect = [
        OperationalError(2013, "Lost connection to server during query"),
        OperationalError(2013, "Lost connection to server during query"),
    ]
    mock_model.objects.filter.return_value = mock_qs

    with patch("django.db.connection.close") as mock_close:
        with pytest.raises(OperationalError) as exc_info:
            _query_existing_records_sync(mock_model, ["https://example.com/item1"])
        assert "Lost connection" in str(exc_info.value)
        assert mock_close.call_count == 1
        assert mock_model.objects.filter.call_count == 2
