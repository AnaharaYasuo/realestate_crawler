# -*- coding: utf-8 -*-
import sys
import os

_cur_dir = os.path.dirname(os.path.abspath(__file__))
_crawler_dir = os.path.dirname(_cur_dir)
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import setup_env  # noqa: F401
import unittest
from unittest.mock import patch
from package.api.differential import _detect_company_and_type_from_model
from package.models.daikyo import DaikyoMansion, DaikyoKodate, DaikyoTochi
from package.models.sumifu import SumifuKodate
from package.models.smtrc import SmtrcMansion


class TestIssue1062Fixes(unittest.TestCase):
    def test_detect_company_and_type_from_model(self):
        self.assertEqual(_detect_company_and_type_from_model(DaikyoMansion), ("daikyo", "mansion"))
        self.assertEqual(_detect_company_and_type_from_model(DaikyoKodate), ("daikyo", "kodate"))
        self.assertEqual(_detect_company_and_type_from_model(DaikyoTochi), ("daikyo", "tochi"))
        self.assertEqual(_detect_company_and_type_from_model(SumifuKodate), ("sumifu", "kodate"))
        self.assertEqual(_detect_company_and_type_from_model(SmtrcMansion), ("smtrc", "mansion"))

    @patch("package.api.differential.touch_crawler_progress")
    def test_differential_chunk_touches_watchdog(self, mock_touch):
        from package.api.differential import _touch_differential_progress
        _touch_differential_progress(DaikyoMansion)
        mock_touch.assert_called_once_with("daikyo", "mansion")


if __name__ == "__main__":
    unittest.main()
