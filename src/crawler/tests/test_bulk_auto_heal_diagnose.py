import json
import os
import unittest
from unittest.mock import MagicMock, patch

from package.utils.html_sanitizer import sanitize_html_for_llm
from scripts.debug_tools.bulk_auto_heal_diagnose import (
    build_bulk_prompt,
    run_bulk_diagnosis_with_gemini,
)


class TestBulkAutoHealDiagnose(unittest.TestCase):
    def test_sanitize_html_for_llm(self):
        raw_html = """
        <html>
            <head><script>alert('bad');</script><style>.bad{color:red;}</style></head>
            <body>
                <nav><a href="#">Menu</a></nav>
                <div class="property-detail" style="display:block;">
                    <span class="price-value" onclick="track()">5,000万円</span>
                    <svg><path d="M0 0"/></svg>
                </div>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        cleaned = sanitize_html_for_llm(raw_html)
        self.assertNotIn("script", cleaned)
        self.assertNotIn("style", cleaned)
        self.assertNotIn("svg", cleaned)
        self.assertNotIn("footer", cleaned)
        self.assertNotIn("nav", cleaned)
        self.assertNotIn("onclick", cleaned)
        self.assertIn("5,000万円", cleaned)
        self.assertIn("property-detail", cleaned)

    def test_build_bulk_prompt_handles_up_to_200_items(self):
        failures = [
            {
                "url": f"https://example.com/property/{i}",
                "failed_field": "price",
                "reason": "Selector not found",
                "html": f"<div class='item'>Property {i} price 3000万</div>",
            }
            for i in range(250)
        ]
        prompt = build_bulk_prompt("mitsui", "mansion", failures, max_items=200)
        self.assertIn("mitsui", prompt)
        self.assertIn("mansion", prompt)
        self.assertIn("合計 200 件", prompt)
        self.assertIn("sample_id\": 200", prompt)
        # Should not include item 201
        self.assertNotIn("sample_id\": 201", prompt)

    @patch("scripts.debug_tools.bulk_auto_heal_diagnose.genai")
    def test_run_bulk_diagnosis_with_gemini_fallback_when_no_api_key(self, mock_genai):
        with patch.dict(os.environ, {}, clear=True):
            failures = [
                {
                    "url": "https://example.com/p1",
                    "failed_field": "price",
                    "reason": "NoneType has no text",
                    "html": "<div>error</div>",
                }
            ]
            result = run_bulk_diagnosis_with_gemini("mitsui", "mansion", failures)
            self.assertEqual(result["site"], "mitsui")
            self.assertEqual(result["property_type"], "mansion")
            self.assertEqual(result["total_analyzed"], 1)
            self.assertIn("patterns", result)

    @patch("scripts.debug_tools.bulk_auto_heal_diagnose.genai")
    def test_run_bulk_diagnosis_with_gemini_mocked_llm(self, mock_genai):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = json.dumps({
            "site": "mitsui",
            "property_type": "mansion",
            "total_analyzed": 5,
            "summary": "価格セレクターが変更された",
            "patterns": [
                {
                    "pattern_id": "P1",
                    "count": 5,
                    "failed_field": "price",
                    "root_cause": "span.price-val 消失",
                    "recommended_selector": "span.property-price",
                }
            ],
            "parser_file": "src/crawler/package/parser/mitsui/mansion_parser.py",
            "recommended_fix": "soup.select_one('span.property-price')",
        })
        mock_client.models.generate_content.return_value = mock_resp
        mock_genai.Client.return_value.__enter__.return_value = mock_client

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_key"}):
            failures = [{"url": f"https://example.com/{i}", "html": "test"} for i in range(5)]
            result = run_bulk_diagnosis_with_gemini("mitsui", "mansion", failures)
            self.assertEqual(result["site"], "mitsui")
            self.assertEqual(result["total_analyzed"], 5)
            self.assertEqual(len(result["patterns"]), 1)
            self.assertEqual(result["patterns"][0]["recommended_selector"], "span.property-price")


if __name__ == "__main__":
    unittest.main()
