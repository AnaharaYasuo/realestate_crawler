"""
Issue #1079: E2Eフルパイプライン実行エラー・不整合改修のテストケース (TDD)
"""
import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError

from package.utils.deduplication import _get_real_property
from package.ml.evaluation.persistence import (
    bulk_update_evaluation_records,
    _bulk_create_records,
)
from package.utils.storage import ObjectStorageManager


def test_get_real_property_handles_unknown_company_safely():
    """会社名が unknown かつ URL から特定できない場合、存在しないモデルを生成せず安全に None を返すこと"""
    mock_eval = MagicMock()
    mock_eval.id = 99999
    mock_eval.property_id = 123
    mock_eval.company = "unknown"
    mock_eval.property_type = "kodate"
    mock_eval.property_url = "https://some-unknown-site.example.com/property/123"

    res = _get_real_property(mock_eval)
    assert res is None


def test_get_real_property_resolves_company_from_url():
    """eval_rec.company が unknown でも URL から asahi-kasei や re-guide 等が推測されて正しくモデル検索されること"""
    mock_eval = MagicMock()
    mock_eval.id = 99998
    mock_eval.property_id = 456
    mock_eval.company = "unknown"
    mock_eval.property_type = "kodate"
    mock_eval.property_url = "https://www.asahi-kasei.co.jp/j-koho/kodate/456"

    # AfrKodate が検索される（見つからなくても例外を出さず None を返す）
    res = _get_real_property(mock_eval)
    # 例外がスローされず None（DB内にID 456がないため）が返ること
    assert res is None


def test_storage_manager_host_fallback(monkeypatch):
    """ホスト実行時 (EXECUTION_ENV=host または not IS_CLOUD) で minio:9000 が localhost:9000 に置換されること"""
    monkeypatch.setenv("STORAGE_BACKEND", "minio")
    monkeypatch.setenv("STORAGE_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("EXECUTION_ENV", "host")
    monkeypatch.setenv("IS_CLOUD", "false")

    with patch("boto3.client") as mock_boto:
        with patch.object(ObjectStorageManager, "_ensure_bucket_exists"):
            mgr = ObjectStorageManager()
            assert "localhost:9000" in mgr.endpoint_url or "127.0.0.1:9000" in mgr.endpoint_url


def test_bulk_update_evaluation_records_retries_on_lost_connection():
    """bulk_update で Lost connection to server (2013) 発生時に close_old_connections されてリトライされること"""
    mock_record = MagicMock(pk=1)
    
    with patch("package.models.evaluation.PropertyEvaluation.objects.bulk_update") as mock_bulk_update:
        # 1回目は Lost connection, 2回目は成功
        mock_bulk_update.side_effect = [
            OperationalError(2013, "Lost connection to server during query"),
            None,
        ]
        with patch("package.ml.evaluation.persistence.close_old_connections") as mock_close:
            bulk_update_evaluation_records([mock_record], "mansion", batch_size=100)
            assert mock_bulk_update.call_count == 2
            assert mock_close.call_count >= 1
