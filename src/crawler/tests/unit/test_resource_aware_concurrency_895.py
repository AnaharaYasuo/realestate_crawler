"""
Unit tests for Issue #895: Dynamic host resource awareness for crawler concurrency
"""
import os
import unittest
from unittest.mock import patch

from package.utils.resource_limiter import get_resource_aware_concurrency
from scripts.ops.run_all_crawlers import parse_args


class TestResourceAwareConcurrency895(unittest.TestCase):
    """Test dynamic concurrency calculation based on available machine/container memory."""

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=300)
    def test_critical_memory_concurrency(self, mock_mem):
        """利用可能メモリ < 512MB 時は parallel=0, playwright_parallel=0 に設定されること"""
        with patch.dict(os.environ, {}, clear=True):
            p, pw, reason = get_resource_aware_concurrency()
            self.assertEqual(p, 0)
            self.assertEqual(pw, 0)
            self.assertIn("300MB", reason)
            self.assertIn("CriticalMemory", reason)

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=3500)
    def test_low_memory_concurrency(self, mock_mem):
        """利用可能メモリ <= 4GB 時は parallel=3, playwright_parallel=1 に安全調整されること"""
        with patch.dict(os.environ, {}, clear=True):
            p, pw, reason = get_resource_aware_concurrency()
            self.assertEqual(p, 3)
            self.assertEqual(pw, 1)
            self.assertIn("3500MB", reason)

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=7000)
    def test_medium_memory_concurrency(self, mock_mem):
        """利用可能メモリ <= 8GB 時は parallel=5, playwright_parallel=2 に調整されること"""
        with patch.dict(os.environ, {}, clear=True):
            p, pw, reason = get_resource_aware_concurrency()
            self.assertEqual(p, 5)
            self.assertEqual(pw, 2)
            self.assertIn("7000MB", reason)

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=16000)
    def test_high_memory_concurrency(self, mock_mem):
        """利用可能メモリ > 8GB 時は既定並列度 (9 / 3) となること"""
        with patch.dict(os.environ, {}, clear=True):
            p, pw, reason = get_resource_aware_concurrency()
            self.assertEqual(p, 9)
            self.assertEqual(pw, 3)
            self.assertIn("16000MB", reason)

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=3500)
    def test_env_var_overrides_resource_detection(self, mock_mem):
        """環境変数 CRAWLER_PARALLEL が指定されている場合はリソース判定より優先されること"""
        env_vars = {
            "CRAWLER_PARALLEL": "6",
            "CRAWLER_PLAYWRIGHT_PARALLEL": "2",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            p, pw, reason = get_resource_aware_concurrency()
            self.assertEqual(p, 6)
            self.assertEqual(pw, 2)
            self.assertIn("overridden by environment variables", reason)

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=3500)
    def test_parse_args_uses_safe_concurrency_by_default(self, mock_mem):
        """run_all_crawlers.py の parse_args が低メモリ環境で安全並列度をデフォルトとすること"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["run_all_crawlers.py"]):
                args = parse_args()
                self.assertEqual(args.parallel, 3)
                self.assertEqual(args.playwright_parallel, 1)

    @patch("package.utils.resource_limiter.detect_available_memory_mb", return_value=3500)
    def test_parse_args_cli_flags_override_safe_concurrency(self, mock_mem):
        """CLI 引数指定時はリソース判定・環境変数より優先されること"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["run_all_crawlers.py", "--parallel=7", "--playwright-parallel=4"]):
                args = parse_args()
                self.assertEqual(args.parallel, 7)
                self.assertEqual(args.playwright_parallel, 4)


if __name__ == "__main__":
    unittest.main()
