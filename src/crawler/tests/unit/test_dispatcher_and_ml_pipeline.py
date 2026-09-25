# -*- coding: utf-8 -*-
import pytest
from unittest.mock import patch


def test_dispatcher_mig_start_and_enqueue():
    """run_dispatcher.py が ProxySQL MIG を起動し、ヘルスチェック疎通後に Cloud Tasks へ全タスク投入することを検証"""
    from scripts.ops import run_dispatcher

    with patch.object(run_dispatcher, "scale_proxysql_mig") as mock_scale, \
         patch.object(run_dispatcher, "wait_for_proxysql_health") as mock_health, \
         patch.object(run_dispatcher, "enqueue_crawl_tasks") as mock_enqueue, \
         patch.object(run_dispatcher, "run_db_migration") as mock_migrate:

        mock_scale.return_value = True
        mock_health.return_value = True
        mock_enqueue.return_value = 45
        mock_migrate.return_value = True

        exit_code = run_dispatcher.main(argv=[])
        assert exit_code == 0
        mock_scale.assert_called_once_with(target_size=1, dry_run=False)
        mock_health.assert_called_once()
        mock_migrate.assert_called_once()
        mock_enqueue.assert_called_once()


def test_ml_pipeline_execution_and_mig_stop():
    """run_ml_pipeline.py がバリア検証後に ML パイプラインを実行し、終了フックで ProxySQL MIG を確実に停止することを検証"""
    from scripts.ops import run_ml_pipeline

    with patch.object(run_ml_pipeline, "verify_barrier_completion") as mock_barrier, \
         patch.object(run_ml_pipeline, "run_command") as mock_run_cmd, \
         patch.object(run_ml_pipeline, "scale_proxysql_mig") as mock_scale:

        mock_barrier.return_value = (True, [])
        mock_scale.return_value = True

        exit_code = run_ml_pipeline.main(argv=[])
        assert exit_code == 0
        mock_barrier.assert_called_once()
        assert mock_run_cmd.call_count >= 4
        # finally で必ず scale_proxysql_mig(target_size=0, dry_run=False) が呼ばれること
        mock_scale.assert_called_with(target_size=0, dry_run=False)


def test_ml_pipeline_stops_mig_even_on_failure():
    """run_ml_pipeline.py は ML 実行途中でエラーが発生した場合でも、finally で必ず MIG を size=0 に停止することを検証"""
    from scripts.ops import run_ml_pipeline

    with patch.object(run_ml_pipeline, "verify_barrier_completion") as mock_barrier, \
         patch.object(run_ml_pipeline, "run_command") as mock_run_cmd, \
         patch.object(run_ml_pipeline, "scale_proxysql_mig") as mock_scale:

        mock_barrier.return_value = (True, [])
        mock_run_cmd.side_effect = RuntimeError("Training failed")

        with pytest.raises(RuntimeError):
            run_ml_pipeline.main(argv=[])

        # 失敗時でも必ず停止が実行されること
        mock_scale.assert_called_with(target_size=0, dry_run=False)


def test_scale_proxysql_mig_rest_fallback(monkeypatch):
    """When compute_v1 is None in Cloud Run, scale_proxysql_mig uses REST API fallback without FileNotFoundError."""
    from unittest.mock import MagicMock
    from scripts.ops import run_dispatcher, run_ml_pipeline

    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.setenv("GCP_PROJECT", "sumifu")
    monkeypatch.setenv("GCP_REGION", "asia-northeast1")
    monkeypatch.setenv("PROXYSQL_MIG_NAME", "proxysql-mig-prod")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"targetSize": 0}

    # Test dispatcher scale_proxysql_mig
    with patch.object(run_dispatcher, "compute_v1", None), \
         patch.object(run_dispatcher, "_get_gcp_access_token", return_value="fake-token", create=True), \
         patch("requests.get", return_value=mock_get_resp), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        res = run_dispatcher.scale_proxysql_mig(target_size=1, dry_run=False)
        assert res is True
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        assert "instanceGroupManagers/proxysql-mig-prod/resize?size=1" in url

    # Test ml_pipeline scale_proxysql_mig
    with patch.object(run_ml_pipeline, "compute_v1", None), \
         patch.object(run_ml_pipeline, "_get_gcp_access_token", return_value="fake-token", create=True), \
         patch("requests.get", return_value=mock_get_resp), \
         patch("requests.post", return_value=mock_resp) as mock_post_ml:
        res = run_ml_pipeline.scale_proxysql_mig(target_size=0, dry_run=False)
        assert res is True
        mock_post_ml.assert_called_once()
        url = mock_post_ml.call_args[0][0]
        assert "instanceGroupManagers/proxysql-mig-prod/resize?size=0" in url


