from unittest.mock import patch, MagicMock
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

    mock_qs = [mock_item]
    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
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
