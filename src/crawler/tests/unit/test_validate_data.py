import datetime
from unittest.mock import MagicMock, patch
import pytest
from scripts.maintenance.validate_data import validate_data


def test_validate_data_sends_alert_and_logs_error(monkeypatch):
    """異常データ検出時に logging.error および send_slack_message が呼ばれることをテスト"""
    monkeypatch.setenv("SLACK_ALERT_MANSION", "C0BJWUCTRNU")

    # 1件の異常物件をシミュレート
    mock_item = MagicMock()
    mock_item.id = 101
    mock_item.pageUrl = "https://example.com/property/101"
    mock_item.propertyName = "テストマンション"
    mock_item.price = 500000  # 50万円 (< 100万円で異常値判定)
    mock_item.senyuMenseki = 2.0  # 2㎡ (<= 5㎡で異常値判定)

    mock_qs = MagicMock()
    mock_qs.__iter__.return_value = [mock_item]
    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
    del mock_model.inputDate  # test without date filter on model
    mock_model.objects.all.return_value = mock_qs

    with patch("scripts.maintenance.validate_data.get_all_models_flat", return_value=[(mock_model, "mitsui", "mansion")]), \
         patch("scripts.maintenance.validate_data.logging.error") as mock_log_error, \
         patch("scripts.maintenance.validate_data.send_slack_message") as mock_send_slack, \
         patch("subprocess.run"):
        
        validate_data()

        # logging.error が呼ばれたことを検証
        assert mock_log_error.called
        call_args_str = str(mock_log_error.call_args)
        assert "MANSION" in call_args_str
        assert "C0BJWUCTRNU" in call_args_str

        # send_slack_message が呼ばれたことを検証
        assert mock_send_slack.called



def test_validate_data_recent_days_filtering(monkeypatch):
    """inputDate を持つモデルで直近指定日数のフィルタ（inputDate__gte）が適用されること"""
    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
    mock_model.inputDate = True  # hasattr(mock_model, "inputDate") == True
    
    mock_all_qs = MagicMock()
    mock_filtered_qs = MagicMock()
    mock_filtered_qs.__iter__.return_value = []
    mock_all_qs.filter.return_value = mock_filtered_qs
    mock_model.objects.all.return_value = mock_all_qs

    fixed_now = datetime.datetime(2026, 10, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    fixed_today = fixed_now.date()

    with patch("scripts.maintenance.validate_data.get_all_models_flat", return_value=[(mock_model, "mitsui", "mansion")]), \
         patch("scripts.maintenance.validate_data.datetime.datetime") as mock_datetime, \
         patch("subprocess.run"):
        mock_datetime.now.return_value = fixed_now
        
        # 1. 指定日数 (days=7)
        validate_data(days=7)
        mock_all_qs.filter.assert_called_once_with(
            inputDate__gte=fixed_today - datetime.timedelta(days=7)
        )

        # 2. 全件スキャンモード (scan_all=True)
        mock_all_qs.filter.reset_mock()
        mock_all_qs.__iter__.return_value = []
        validate_data(scan_all=True)
        assert not mock_all_qs.filter.called

        # 3. days=0 (全件走査)
        mock_all_qs.filter.reset_mock()
        validate_data(days=0)
        assert not mock_all_qs.filter.called

        # 4. 環境変数 VALIDATE_DATA_DAYS=14
        mock_all_qs.filter.reset_mock()
        monkeypatch.setenv("VALIDATE_DATA_DAYS", "14")
        validate_data()
        mock_all_qs.filter.assert_called_once_with(
            inputDate__gte=fixed_today - datetime.timedelta(days=14)
        )

        # 5. 引数なし・環境変数なし (デフォルト7日)
        mock_all_qs.filter.reset_mock()
        monkeypatch.delenv("VALIDATE_DATA_DAYS", raising=False)
        validate_data()
        mock_all_qs.filter.assert_called_once_with(
            inputDate__gte=fixed_today - datetime.timedelta(days=7)
        )

        # 6. 負の日数は例外送出
        with pytest.raises(ValueError, match="days must be non-negative"):
            validate_data(days=-1)


