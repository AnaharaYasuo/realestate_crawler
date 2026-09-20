import unittest
from unittest.mock import MagicMock, patch

import setup_env  # noqa: F401
from scripts.ops.dependabot_automerge import (
    DependabotAutoMerger,
    DependabotPrInspector,
    PRStatus,
)


class TestDependabotAutomerge(unittest.TestCase):
    def setUp(self):
        self.inspector = DependabotPrInspector()
        self.merger = DependabotAutoMerger(dry_run=True, auto_merge=True, auto_rebase=True)

    def test_evaluate_pr_merge_ready(self):
        pr_data = {
            "number": 101,
            "title": "chore(deps): bump certifi from 2024.2.2 to 2024.7.4",
            "mergeable": "MERGEABLE",
            "statusCheckRollup": [
                {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"name": "Snyk Analysis", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"name": "SonarCloud Scan", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
        }
        status, reason = self.inspector.evaluate_pr_status(pr_data)
        self.assertEqual(status, PRStatus.MERGE_READY)
        self.assertIn("All checks passed", reason)

    def test_evaluate_pr_conflicting(self):
        pr_data = {
            "number": 102,
            "title": "chore(deps): bump urllib3 from 2.0.0 to 2.2.2",
            "mergeable": "CONFLICTING",
            "statusCheckRollup": [
                {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"},
            ],
        }
        status, reason = self.inspector.evaluate_pr_status(pr_data)
        self.assertEqual(status, PRStatus.NEED_REBASE)
        self.assertIn("conflicts", reason.lower())

    def test_evaluate_pr_ci_running(self):
        pr_data = {
            "number": 103,
            "title": "chore(deps): bump requests from 2.31.0 to 2.32.3",
            "mergeable": "MERGEABLE",
            "statusCheckRollup": [
                {"name": "test", "status": "IN_PROGRESS", "conclusion": ""},
                {"name": "Snyk Analysis", "status": "QUEUED", "conclusion": ""},
            ],
        }
        status, reason = self.inspector.evaluate_pr_status(pr_data)
        self.assertEqual(status, PRStatus.CI_RUNNING)
        self.assertIn("in progress", reason.lower())

    def test_evaluate_pr_ci_failed(self):
        pr_data = {
            "number": 104,
            "title": "chore(deps): bump pydantic from 1.10.0 to 2.0.0",
            "mergeable": "MERGEABLE",
            "statusCheckRollup": [
                {"name": "test", "status": "COMPLETED", "conclusion": "FAILURE"},
                {"name": "Snyk Analysis", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
        }
        status, reason = self.inspector.evaluate_pr_status(pr_data)
        self.assertEqual(status, PRStatus.CI_FAILED)
        self.assertIn("failed", reason.lower())

    @patch("subprocess.run")
    def test_execute_merge_dry_run(self, mock_run):
        merger = DependabotAutoMerger(dry_run=True, auto_merge=True, auto_rebase=True)
        success = merger.execute_merge(101)
        self.assertTrue(success)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_execute_merge_live(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Merged", stderr="")
        merger = DependabotAutoMerger(dry_run=False, auto_merge=True, auto_rebase=True)
        success = merger.execute_merge(101)
        self.assertTrue(success)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:3], ["gh", "pr", "merge"])
        self.assertIn("101", args)
        self.assertIn("--squash", args)
        self.assertIn("--delete-branch", args)

    @patch("subprocess.run")
    def test_request_rebase_live(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Commented", stderr="")
        merger = DependabotAutoMerger(dry_run=False, auto_merge=True, auto_rebase=True)
        success = merger.request_rebase(102)
        self.assertTrue(success)
        # Should call gh pr comment
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:3], ["gh", "pr", "comment"])
        self.assertIn("102", args)
        self.assertIn("@dependabot rebase", args)

    def test_format_summary_markdown(self):
        merger = DependabotAutoMerger(dry_run=True)
        results = [
            {"number": 101, "title": "bump certifi", "status": PRStatus.MERGE_READY, "action": "Merged (Dry-Run)"},
            {"number": 102, "title": "bump urllib3", "status": PRStatus.NEED_REBASE, "action": "Rebase Requested (Dry-Run)"},
            {"number": 103, "title": "bump requests", "status": PRStatus.CI_RUNNING, "action": "Skipped (CI Running)"},
            {"number": 104, "title": "bump pydantic", "status": PRStatus.CI_FAILED, "action": "Skipped (CI Failed)"},
        ]
        md = merger.format_summary_markdown(results)
        self.assertIn("## Dependabot Auto-Merge Summary", md)
        self.assertIn("bump certifi", md)
        self.assertIn("Merged (Dry-Run)", md)
        self.assertIn("Rebase Requested (Dry-Run)", md)


    def test_evaluate_pr_ignore_unmerged_checks(self):
        """マージ後にしか解消されない Code Scanning / upload-sarif などのエラーがマージ可否判定で除外されることを検証"""
        pr_data = {
            "number": 105,
            "title": "chore(deps): bump certifi from 2024.2.2 to 2024.7.4",
            "mergeable": "MERGEABLE",
            "statusCheckRollup": [
                {"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"name": "Trivy Security Scan", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"name": "upload-sarif", "status": "COMPLETED", "conclusion": "FAILURE"},
            ],
        }
        status, reason = self.inspector.evaluate_pr_status(pr_data)
        self.assertEqual(status, PRStatus.MERGE_READY)
        self.assertIn("All checks passed", reason)

    def test_evaluate_pr_ignores_each_documented_non_blocking_context(self):
        for check_name in (
            "Upload-SARIF / Trivy",
            "Code Scanning Results",
            "security/snyk (pull_request)",
        ):
            with self.subTest(check_name=check_name):
                status, reason = self.inspector.evaluate_pr_status(
                    {
                        "mergeable": "MERGEABLE",
                        "statusCheckRollup": [
                            {
                                "name": check_name,
                                "status": "COMPLETED",
                                "conclusion": "FAILURE",
                            }
                        ],
                    }
                )

                self.assertEqual(status, PRStatus.MERGE_READY)
                self.assertIn("All checks passed", reason)

    def test_evaluate_pr_does_not_ignore_other_security_failures(self):
        status, reason = self.inspector.evaluate_pr_status(
            {
                "mergeable": "MERGEABLE",
                "statusCheckRollup": [
                    {
                        "name": "Trivy Security Scan",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                    }
                ],
            }
        )

        self.assertEqual(status, PRStatus.CI_FAILED)
        self.assertIn("Trivy Security Scan", reason)

    def test_evaluate_pr_running_check_takes_precedence_over_ignored_failure(self):
        status, reason = self.inspector.evaluate_pr_status(
            {
                "mergeable": "MERGEABLE",
                "statusCheckRollup": [
                    {
                        "name": "upload-sarif",
                        "status": "COMPLETED",
                        "conclusion": "FAILURE",
                    },
                    {
                        "name": "unit-tests",
                        "status": "IN_PROGRESS",
                        "conclusion": "",
                    },
                ],
            }
        )

        self.assertEqual(status, PRStatus.CI_RUNNING)
        self.assertIn("in progress", reason.lower())


if __name__ == "__main__":
    unittest.main()
