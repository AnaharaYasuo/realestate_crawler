# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError
from package.ml.evaluation.runner import evaluate_single_model


def test_evaluate_single_model_retry_on_transient_db_error():
    """DB瞬断エラー時に close_old_connections を呼び出し、リトライして救済成功すること"""
    mock_model = MagicMock()
    mock_model.__name__ = "SmtrcMansion"

    chunk_items = [MagicMock()]
    mock_iter = [([chunk_items[0]], 0)]

    with patch("package.ml.evaluation.runner.resolve_company_and_type", return_value=("smtrc", "mansion")), \
         patch("package.ml.evaluation.runner.iter_unprocessed_chunks", return_value=mock_iter), \
         patch("package.ml.evaluation.runner.bulk_predict_first_stage", return_value=[50000000]), \
         patch("package.ml.evaluation.runner.close_old_connections") as mock_close_conn, \
         patch("time.sleep") as mock_sleep, \
         patch("package.ml.evaluation.runner.save_chunk") as mock_save:

        # 1回目は OperationalError (MySQL gone away)、2回目は成功
        mock_save.side_effect = [
            OperationalError(2006, "MySQL server has gone away"),
            (1, 0),
        ]

        evaluated, skipped, passed, dup = evaluate_single_model(
            model=mock_model,
            existing_eval_map={},
            force=False,
            limit_per_model=10,
        )

        assert evaluated == 1
        assert passed == 1
        assert mock_save.call_count == 2
        assert mock_close_conn.call_count >= 2
        mock_sleep.assert_called_once_with(1)
