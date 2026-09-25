# -*- coding: utf-8 -*-
"""Unit tests for setup_strict_quality_gate.py (Issue #436)."""
from unittest.mock import patch

from scripts.debug_tools.setup_strict_quality_gate import (
    DEFAULT_CONDITIONS,
    ensure_strict_quality_gate,
    main,
)


def test_default_conditions_structure():
    """デフォルト条件に new_violations GT 0 が含まれ、カバレッジ条件が含まれないこと"""
    metrics = {c["metric"]: c for c in DEFAULT_CONDITIONS}
    assert "new_violations" in metrics
    assert metrics["new_violations"]["op"] == "GT"
    assert metrics["new_violations"]["error"] == "0"
    # coverage 関連が含まれていないこと
    assert "new_coverage" not in metrics
    assert "branch_coverage" not in metrics


def test_ensure_strict_quality_gate_create_new():
    """ゲートが存在しない場合、作成・条件追加・プロジェクト選択が行われること"""
    list_resp = {"qualitygates": []}
    create_resp = {"id": 12345, "name": "Strict Gate"}

    with patch("scripts.debug_tools.setup_strict_quality_gate.api_request") as mock_api:
        mock_api.side_effect = [
            list_resp,    # list
            create_resp,  # create
            {},           # create_condition 1
            {},           # create_condition 2
            {},           # create_condition 3
            {},           # create_condition 4
            {},           # create_condition 5
            {},           # create_condition 6
            {},           # select
        ]

        gate_id = ensure_strict_quality_gate(
            token="dummy_token",
            org="anaharayasuo",
            project="AnaharaYasuo_realestate_crawler",
            gate_name="Strict Gate",
            dry_run=False,
        )

        assert gate_id == 12345
        assert mock_api.call_count == 9


def test_ensure_strict_quality_gate_update_existing():
    """既存ゲートがある場合、不足している条件の追加と不要条件の削除・選択が行われること"""
    list_resp = {
        "qualitygates": [
            {
                "id": 156760,
                "name": "Strict Gate",
                "conditions": [
                    {"id": 1, "metric": "new_coverage", "op": "LT", "error": "80"},
                    {"id": 2, "metric": "new_violations", "op": "GT", "error": "0"},
                ],
            }
        ]
    }

    with patch("scripts.debug_tools.setup_strict_quality_gate.api_request") as mock_api:
        mock_api.side_effect = [
            list_resp,  # list
            {},         # delete_condition (new_coverage)
            {},         # create_condition (missing 1)
            {},         # create_condition (missing 2)
            {},         # create_condition (missing 3)
            {},         # create_condition (missing 4)
            {},         # create_condition (missing 5)
            {},         # select
        ]

        gate_id = ensure_strict_quality_gate(
            token="dummy_token",
            org="anaharayasuo",
            project="AnaharaYasuo_realestate_crawler",
            gate_name="Strict Gate",
            dry_run=False,
        )

        assert gate_id == 156760


def test_main_cli_dry_run(capsys):
    """--dry-run 実行時に API 変更を行わず計画のみ出力すること"""
    list_resp = {"qualitygates": [{"id": 999, "name": "Strict Gate", "conditions": []}]}

    with patch("scripts.debug_tools.setup_strict_quality_gate.api_request", return_value=list_resp):
        code = main(["--token", "test", "--dry-run"])
        assert code == 0
        captured = capsys.readouterr()
        assert "[DRY-RUN]" in captured.out
