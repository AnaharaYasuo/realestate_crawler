# -*- coding: utf-8 -*-
"""evaluation_routes.py の例外ログパスのカバレッジテスト"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from routes.evaluation_routes import _execute_predict_by_url


@pytest.mark.asyncio
async def test_execute_predict_by_url_cache_query_exception_logs():
    """PropertyEvaluation.objects.filter が例外を投げた場合 logging.exception でログ出力されることを検証"""
    with patch("routes.evaluation_routes.PropertyEvaluation.objects.filter", side_effect=Exception("cache query failed")):
        with patch("routes.evaluation_routes.logging") as mock_logging:
            with patch("routes.evaluation_routes.UrlRouter.resolve", return_value=None):
                with patch(
                    "routes.evaluation_routes.UrlSecurityValidator.check_property_content_and_reachability",
                    new_callable=AsyncMock,
                    return_value=(False, None, [])
                ):
                    res, status = await _execute_predict_by_url(
                        url="https://example.com/prop1",
                        force_refresh=False,
                        interior_score=3.0,
                        layout_score=3.0
                    )

            mock_logging.exception.assert_called_once()
            assert "PropertyEvaluation cache query failed: cache query failed" in mock_logging.exception.call_args[0][0]
            assert status == 400


@pytest.mark.asyncio
async def test_execute_predict_by_url_model_info_fetch_exception_logs():
    """cached eval の model info fetch 例外時に logging.exception が呼ばれることを検証"""
    mock_eval = MagicMock()
    mock_eval.first_stage_predicted_price = 50000000
    mock_eval.second_stage_predicted_price = 52000000
    mock_eval.company = "test_site"
    mock_eval.property_type = "mansion"

    with patch("routes.evaluation_routes.logging") as mock_logging:
        with patch("routes.evaluation_routes.PropertyEvaluation.objects.filter") as mock_filter:
            mock_filter.return_value.first.return_value = mock_eval
            # 存在しないクラス名を指定して getattr で例外を発生させる
            with patch("routes.evaluation_routes.UrlRouter.resolve", return_value={
                "site": "test_site",
                "property_type": "mansion",
                "model_module": "package.models.mansion",
                "model_cls": "NonExistentModelClass"
            }):
                res, status = await _execute_predict_by_url(
                    url="https://example.com/prop2",
                    force_refresh=False,
                    interior_score=3.0,
                    layout_score=3.0
                )

        mock_logging.exception.assert_called_once()
        assert "Failed to fetch model info for cached eval" in mock_logging.exception.call_args[0][0]
        assert status == 200
        assert res["success"] is True
