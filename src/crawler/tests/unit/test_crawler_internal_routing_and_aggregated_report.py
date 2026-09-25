# -*- coding: utf-8 -*-
import os
import unittest
from unittest.mock import patch, MagicMock

import setup_env  # noqa: F401
from package.api.api import ApiAsyncProcBase
from package.api.registry import ApiRegistry
from package.models.crawler_task_execution import CrawlerTaskExecution
from package.ml.predict import get_api_base_url as predict_get_api_base_url
from scripts.ops.run_pipeline import aggregate_task_array_reports


class DummyApi(ApiAsyncProcBase):
    def _generateParser(self):
        return MagicMock()

    def _getPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 10

    def _generateConnector(self, loop):
        return None

    def _getApiKey(self):
        return "/test"


DummyApi.__abstractmethods__ = frozenset()


class TestCrawlerInternalRoutingAndAggregatedReport(unittest.TestCase):
    """Unit tests for Issue #445: Cloud routing and aggregated crawl report."""

    def test_get_url_returns_api_base_url_in_cloud_not_cloudfunctions(self):
        """Verify _getUrl() returns local default or API_BASE_URL even when IS_CLOUD=true."""
        api = DummyApi()
        with patch.dict(os.environ, {"IS_CLOUD": "true", "API_BASE_URL": ""}, clear=False):
            url = api._getUrl()
            self.assertEqual(url, "http://127.0.0.1:8000")
            self.assertNotIn("cloudfunctions.net", url)

        with patch.dict(os.environ, {"IS_CLOUD": "true", "API_BASE_URL": "http://internal-api:8080"}, clear=False):
            url = api._getUrl()
            self.assertEqual(url, "http://internal-api:8080")

    def test_handle_local_execution_allowed_in_cloud_when_registered(self):
        """Verify _handle_local_execution does not immediately return None when IS_CLOUD=true."""
        api = DummyApi()
        mock_handler = MagicMock()
        mock_handler.__name__ = "MockHandler"
        mock_handler.return_value.main = MagicMock()

        test_path = "/api/test/mock_route"
        ApiRegistry.register(test_path, mock_handler)
        try:
            with patch.dict(os.environ, {"IS_CLOUD": "true"}, clear=False):
                res = api._handle_local_execution(f"http://127.0.0.1:8000{test_path}", "http://example.com/item1")
                self.assertIsNotNone(res)
                self.assertEqual(res[1], 200)
                self.assertEqual(res[2], "LocalSync")
                mock_handler.return_value.main.assert_called_once_with("http://example.com/item1")
        finally:
            if test_path in ApiRegistry._registry:
                del ApiRegistry._registry[test_path]

    def test_predict_api_base_url_no_cloudfunctions(self):
        """Verify predict.py get_api_base_url does not point to dead Cloud Functions URL."""
        with patch.dict(os.environ, {"IS_CLOUD": "true", "EVALUATION_API_URL": "", "API_BASE_URL": ""}, clear=False):
            url = predict_get_api_base_url()
            self.assertEqual(url, "http://localhost:8000/api/evaluation/predict/")
            self.assertNotIn("cloudfunctions.net", url)

    def test_aggregate_task_array_reports_all_success(self):
        """Verify aggregation when all tasks finish with success."""
        task_0 = {
            "task_index": 0,
            "status": "COMPLETED",
            "results_json": [
                {"company": "mitsui", "property_type": "mansion", "status": "success", "exit_code": 0, "duration": "10s"},
                {"company": "mitsui", "property_type": "kodate", "status": "success", "exit_code": 0, "duration": "12s"},
            ],
        }
        task_1 = {
            "task_index": 1,
            "status": "COMPLETED",
            "results_json": [
                {"company": "sumifu", "property_type": "mansion", "status": "success", "exit_code": 0, "duration": "15s"},
            ],
        }

        agg = aggregate_task_array_reports([task_0, task_1], total_jobs=3)
        self.assertEqual(agg["total_jobs"], 3)
        self.assertEqual(agg["executed_jobs"], 3)
        self.assertEqual(agg["success_jobs"], 3)
        self.assertEqual(agg["failed_jobs"], 0)
        self.assertEqual(agg["missing_jobs"], 0)
        self.assertIn("全 3 ジョブが正常に実行・完了しました", agg["slack_message"])

    def test_aggregate_task_array_reports_with_failure_and_missing(self):
        """Verify aggregation accurately reports failures and unexecuted/missing jobs."""
        task_0 = {
            "task_index": 0,
            "status": "FAILED",
            "results_json": [
                {"company": "tokyu", "property_type": "mansion", "status": "failed", "exit_code": 1, "duration": "5s"},
                {"company": "tokyu", "property_type": "kodate", "status": "success", "exit_code": 0, "duration": "8s"},
            ],
        }
        task_1 = {
            "task_index": 1,
            "status": "COMPLETED",
            "results_json": [
                {"company": "nomura", "property_type": "mansion", "status": "timeout", "exit_code": 124, "duration": "300s"},
            ],
        }

        agg = aggregate_task_array_reports([task_0, task_1], total_jobs=5)
        self.assertEqual(agg["total_jobs"], 5)
        self.assertEqual(agg["executed_jobs"], 3)
        self.assertEqual(agg["success_jobs"], 1)
        self.assertEqual(agg["failed_jobs"], 2)
        self.assertEqual(agg["missing_jobs"], 2)
        self.assertIn("tokyu - mansion: failed (Code: 1", agg["slack_message"])
        self.assertIn("nomura - mansion: timeout (Code: 124", agg["slack_message"])
        self.assertIn("未実行: 2", agg["slack_message"])

    def test_crawler_task_execution_results_json_field(self):
        """Verify CrawlerTaskExecution model can persist and load results_json."""
        field = CrawlerTaskExecution._meta.get_field("results_json")
        self.assertIsNotNone(field)
        self.assertEqual(field.default, list)


if __name__ == "__main__":
    unittest.main()
