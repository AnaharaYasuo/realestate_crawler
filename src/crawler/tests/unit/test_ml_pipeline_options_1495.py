"""Unit tests for --skip-recrawl and --property-type flags in run_ml_pipeline.py (Issue #1495)"""

import os
import unittest
from unittest.mock import MagicMock, patch

from scripts.ops.run_ml_pipeline import (
    _run_self_healing_recrawl_and_validation,
    main,
)


class TestRunMLPipelineOptions1495(unittest.TestCase):
    @patch("scripts.ops.run_ml_pipeline.run_command")
    def test_skip_recrawl_bypasses_recrawl_anomalies(self, mock_run_command):
        # When skip_recrawl=True, recrawl_anomalies.py should not be executed
        _run_self_healing_recrawl_and_validation(
            maintenance_dir="/fake/maintenance",
            debug_tools_dir="/fake/debug_tools",
            skip_url_check=True,
            skip_recrawl=True,
        )

        executed_cmds = [call_args[0][0] for call_args in mock_run_command.call_args_list]
        for cmd in executed_cmds:
            self.assertNotIn("recrawl_anomalies.py", " ".join(cmd))

    @patch("scripts.ops.run_ml_pipeline.run_command")
    def test_no_skip_recrawl_executes_recrawl_anomalies(self, mock_run_command):
        # When skip_recrawl=False, recrawl_anomalies.py must be called
        _run_self_healing_recrawl_and_validation(
            maintenance_dir="/fake/maintenance",
            debug_tools_dir="/fake/debug_tools",
            skip_url_check=True,
            skip_recrawl=False,
        )

        executed_cmds = [call_args[0][0] for call_args in mock_run_command.call_args_list]
        recrawl_called = any("recrawl_anomalies.py" in " ".join(cmd) for cmd in executed_cmds)
        self.assertTrue(recrawl_called)

    @patch("scripts.ops.run_ml_pipeline._run_self_healing_recrawl_and_validation")
    @patch("scripts.ops.run_ml_pipeline.verify_barrier_completion", return_value=(True, []))
    @patch("scripts.ops.run_ml_pipeline.filter_crawl_jobs", return_value=[])
    @patch("scripts.ops.run_ml_pipeline.send_aggregated_crawl_report")
    @patch("scripts.ops.run_ml_pipeline.start_on_demand_resources")
    @patch("scripts.ops.run_ml_pipeline.run_command")
    def test_main_cli_property_type_and_skip_recrawl(
        self,
        mock_run_cmd,
        mock_start_res,
        mock_report,
        mock_filter,
        mock_barrier,
        mock_recrawl_val,
    ):
        argv = [
            "--force",
            "--train",
            "--skip-recrawl",
            "--property-type",
            "tochi",
            "--skip-potentials-sync",
            "--dry-run",
        ]

        exit_code = main(argv)
        self.assertEqual(exit_code, 0)

        # 1. Verify skip_recrawl passed to _run_self_healing_recrawl_and_validation
        mock_recrawl_val.assert_called_once()
        _, kwargs = mock_recrawl_val.call_args
        self.assertTrue(kwargs.get("skip_recrawl"))

        # 2. Verify train_cmd received --property-type tochi
        train_calls = [
            call_args[0][0]
            for call_args in mock_run_cmd.call_args_list
            if any("train.py" in str(part) for part in call_args[0][0])
        ]
        self.assertEqual(len(train_calls), 1)
        train_cmd = train_calls[0]
        self.assertIn("--property-type", train_cmd)
        prop_idx = train_cmd.index("--property-type")
        self.assertEqual(train_cmd[prop_idx + 1], "tochi")

    @patch("scripts.ops.run_ml_pipeline._run_self_healing_recrawl_and_validation")
    @patch("scripts.ops.run_ml_pipeline.verify_barrier_completion", return_value=(True, []))
    @patch("scripts.ops.run_ml_pipeline.filter_crawl_jobs", return_value=[])
    @patch("scripts.ops.run_ml_pipeline.send_aggregated_crawl_report")
    @patch("scripts.ops.run_ml_pipeline.start_on_demand_resources")
    @patch("scripts.ops.run_ml_pipeline.run_command")
    def test_main_cli_property_type_all(
        self,
        mock_run_cmd,
        mock_start_res,
        mock_report,
        mock_filter,
        mock_barrier,
        mock_recrawl_val,
    ):
        argv = [
            "--force",
            "--train",
            "--skip-recrawl",
            "--property-type",
            "all",
            "--skip-potentials-sync",
            "--dry-run",
        ]

        exit_code = main(argv)
        self.assertEqual(exit_code, 0)

        train_calls = [
            call_args[0][0]
            for call_args in mock_run_cmd.call_args_list
            if any("train.py" in str(part) for part in call_args[0][0])
        ]
        self.assertEqual(len(train_calls), 1)
        train_cmd = train_calls[0]
        # Should include mansion, kodate, apartment, tochi
        for pt in ["mansion", "kodate", "apartment", "tochi"]:
            self.assertIn(pt, train_cmd)

    @patch("scripts.ops.run_ml_pipeline._run_self_healing_recrawl_and_validation")
    @patch("scripts.ops.run_ml_pipeline.verify_barrier_completion", return_value=(True, []))
    @patch("scripts.ops.run_ml_pipeline.filter_crawl_jobs", return_value=[])
    @patch("scripts.ops.run_ml_pipeline.send_aggregated_crawl_report")
    @patch("scripts.ops.run_ml_pipeline.start_on_demand_resources")
    @patch("scripts.ops.run_ml_pipeline.run_command")
    def test_main_cli_concurrency_argument(
        self,
        mock_run_cmd,
        mock_start_res,
        mock_report,
        mock_filter,
        mock_barrier,
        mock_recrawl_val,
    ):
        argv = [
            "--force",
            "--skip-train",
            "--skip-recrawl",
            "--concurrency",
            "4",
            "--skip-potentials-sync",
            "--dry-run",
        ]

        exit_code = main(argv)
        self.assertEqual(exit_code, 0)

        eval_calls = [
            call_args[0][0]
            for call_args in mock_run_cmd.call_args_list
            if any("run_bulk_ml_evaluation.py" in str(part) for part in call_args[0][0])
        ]
        self.assertEqual(len(eval_calls), 1)
        eval_cmd = eval_calls[0]
        self.assertIn("--concurrency", eval_cmd)
        c_idx = eval_cmd.index("--concurrency")
        self.assertEqual(eval_cmd[c_idx + 1], "4")
