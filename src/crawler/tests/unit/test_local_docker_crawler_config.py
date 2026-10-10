# -*- coding: utf-8 -*-
"""Unit tests for local docker crawler configuration and concurrency controls (Issue #857)."""
import os
import unittest
from unittest.mock import patch

from package.api.adaptive_concurrency import AdaptiveConcurrencyController
from scripts.ops.run_all_crawlers import parse_args


class TestLocalDockerCrawlerConfig(unittest.TestCase):
    """Test environment variable fallbacks for crawler parallelism and adaptive concurrency."""

    def test_parse_args_defaults_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["run_all_crawlers.py"]):
                args = parse_args()
                self.assertEqual(args.parallel, 9)
                self.assertEqual(args.playwright_parallel, 3)

    def test_parse_args_env_overrides_defaults(self):
        env_vars = {
            "CRAWLER_PARALLEL": "4",
            "CRAWLER_PLAYWRIGHT_PARALLEL": "1",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("sys.argv", ["run_all_crawlers.py"]):
                args = parse_args()
                self.assertEqual(args.parallel, 4)
                self.assertEqual(args.playwright_parallel, 1)

    def test_parse_args_cli_flags_win_over_env(self):
        env_vars = {
            "CRAWLER_PARALLEL": "4",
            "CRAWLER_PLAYWRIGHT_PARALLEL": "1",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("sys.argv", ["run_all_crawlers.py", "--parallel=2", "--playwright-parallel=0"]):
                args = parse_args()
                self.assertEqual(args.parallel, 2)
                self.assertEqual(args.playwright_parallel, 0)

    def test_adaptive_concurrency_detail_concurrency_env(self):
        with patch.dict(os.environ, {"DETAIL_CONCURRENCY": "3"}, clear=True):
            concurrency = AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=1)
            self.assertEqual(concurrency, 3)

    def test_adaptive_concurrency_fallback_to_cloud_env(self):
        with patch.dict(os.environ, {"CLOUD_DETAIL_CONCURRENCY": "6"}, clear=True):
            concurrency = AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=1)
            self.assertEqual(concurrency, 6)


if __name__ == "__main__":
    unittest.main()
