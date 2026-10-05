import datetime
from unittest.mock import MagicMock, patch
import pytest
from scripts.maintenance.validate_data import validate_data


def test_validate_data_sends_alert_and_logs_error(monkeypatch):
    """異常データ検出時に send_dev_report が呼ばれ #dev-agent へ報告されることをテスト"""
    monkeypatch.setenv("SLACK_DEV_CHANNEL", "C0BKBHWD26T")

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
         patch("scripts.maintenance.validate_data.verify_url_active", return_value=True), \
         patch("scripts.maintenance.validate_data.send_dev_report") as mock_send_dev, \
         patch("subprocess.run"):
        
        validate_data()

        # send_dev_report が呼ばれたことを検証
        assert mock_send_dev.called
        call_msg = str(mock_send_dev.call_args)
        assert "データ整合性検証" in call_msg
        assert "needs_parser_fix=True" in call_msg



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


def test_validate_data_parallel_concurrency_execution(monkeypatch):
    """並行実行時に _run_parallel_validation が指定された並行度で呼ばれること"""
    mock_item = MagicMock()
    mock_item.id = 201
    mock_item.pageUrl = "https://example.com/property/201"
    mock_item.propertyName = "並行テスト物件"
    mock_item.price = 50000000
    mock_item.senyuMenseki = 60.0

    mock_qs = MagicMock()
    mock_qs.__iter__.return_value = [mock_item]
    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
    del mock_model.inputDate
    mock_model.objects.all.return_value = mock_qs

    with patch("scripts.maintenance.validate_data.get_all_models_flat", return_value=[(mock_model, "mitsui", "mansion")]), \
         patch("scripts.maintenance.validate_data.PropertyEvaluation.objects.filter") as mock_eval_filter, \
         patch("scripts.maintenance.validate_data._run_parallel_validation") as mock_parallel_run, \
         patch("scripts.maintenance.validate_data.send_dev_report"), \
         patch("subprocess.run"):
        
        mock_eval_filter.return_value.first.return_value = None
        mock_parallel_run.return_value = [
            ({"status": "valid", "reasons": [], "company": "mitsui", "property_type": "mansion", "url": mock_item.pageUrl, "name": mock_item.propertyName, "is_critical": False}, None)
        ]

        # 1. デフォルト並行度 (15)
        validate_data()
        assert mock_parallel_run.called
        assert mock_parallel_run.call_args[1]["concurrency"] == 15

        # 2. 引数で concurrency=20 指定
        mock_parallel_run.reset_mock()
        validate_data(concurrency=20)
        assert mock_parallel_run.called
        assert mock_parallel_run.call_args[1]["concurrency"] == 20

        # 3. 環境変数 VALIDATE_DATA_CONCURRENCY=10
        mock_parallel_run.reset_mock()
        monkeypatch.setenv("VALIDATE_DATA_CONCURRENCY", "10")
        validate_data()
        assert mock_parallel_run.called
        assert mock_parallel_run.call_args[1]["concurrency"] == 10


@pytest.mark.asyncio
async def test_run_parallel_validation_executes_all_items():
    """_run_parallel_validation がすべてのタスクを非同期処理し結果を返すこと"""
    from scripts.maintenance.validate_data import _run_parallel_validation

    item1 = MagicMock()
    item1.pageUrl = "https://example.com/prop1"
    item2 = MagicMock()
    item2.pageUrl = "https://example.com/prop2"

    tasks = [
        (item1, "mansion", "mitsui", None),
        (item2, "kodate", "sumifu", None),
    ]

    with patch("scripts.maintenance.validate_data.process_property_validation") as mock_validate:
        mock_validate.side_effect = [
            {"status": "valid", "reasons": []},
            {"status": "delisted", "reasons": []},
        ]

        results = await _run_parallel_validation(tasks, concurrency=5)
        assert len(results) == 2
        assert results[0][0]["status"] == "valid"
        assert results[1][0]["status"] == "delisted"
        assert mock_validate.call_count == 2


@pytest.mark.asyncio
async def test_process_property_validation_skip_url_check():
    """skip_url_check=True の時 verify_url_active を呼ばずにデータ妥当性のみ検証すること"""
    from scripts.maintenance.validate_data import process_property_validation

    item = MagicMock()
    item.pageUrl = "https://example.com/prop_valid"
    item.propertyName = "正常マンション"
    item.price = 50000000
    item.senyuMenseki = 70.0

    with patch("scripts.maintenance.validate_data.verify_url_active") as mock_url_active, \
         patch("scripts.maintenance.validate_data.PropertyDataValidator.validate_property", return_value=(True, [])):
        
        # 1. skip_url_check=True: verify_url_active is NOT called
        res = await process_property_validation(item, "mansion", "mitsui", skip_url_check=True)
        assert not mock_url_active.called
        assert res["status"] == "valid"

        # 2. skip_url_check=False: verify_url_active is called
        mock_url_active.return_value = True
        res = await process_property_validation(item, "mansion", "mitsui", skip_url_check=False)
        assert mock_url_active.called
        assert res["status"] == "valid"


def test_validate_data_skip_url_check_env_and_arg(monkeypatch):
    """validate_data で skip_url_check の引数および環境変数が正しく反映されること"""
    mock_item = MagicMock()
    mock_item.id = 301
    mock_item.pageUrl = "https://example.com/property/301"
    mock_item.propertyName = "テスト物件"

    mock_qs = MagicMock()
    mock_qs.__iter__.return_value = [mock_item]
    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
    del mock_model.inputDate
    mock_model.objects.all.return_value = mock_qs

    with patch("scripts.maintenance.validate_data.get_all_models_flat", return_value=[(mock_model, "mitsui", "mansion")]), \
         patch("scripts.maintenance.validate_data.PropertyEvaluation.objects.filter") as mock_eval_filter, \
         patch("scripts.maintenance.validate_data._run_parallel_validation") as mock_parallel_run, \
         patch("scripts.maintenance.validate_data.send_dev_report"), \
         patch("subprocess.run"):
        
        mock_eval_filter.return_value.first.return_value = None
        mock_parallel_run.return_value = [
            ({"status": "valid", "reasons": [], "company": "mitsui", "property_type": "mansion", "url": mock_item.pageUrl, "name": mock_item.propertyName, "is_critical": False}, None)
        ]

        # 1. デフォルト: skip_url_check=False
        monkeypatch.delenv("VALIDATE_DATA_SKIP_URL_CHECK", raising=False)
        validate_data()
        assert mock_parallel_run.call_args[1]["skip_url_check"] is False

        # 2. 引数で skip_url_check=True
        mock_parallel_run.reset_mock()
        validate_data(skip_url_check=True)
        assert mock_parallel_run.call_args[1]["skip_url_check"] is True

        # 3. 環境変数 VALIDATE_DATA_SKIP_URL_CHECK=true
        mock_parallel_run.reset_mock()
        monkeypatch.setenv("VALIDATE_DATA_SKIP_URL_CHECK", "true")
        validate_data()
        assert mock_parallel_run.call_args[1]["skip_url_check"] is True





