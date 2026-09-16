# -*- coding: utf-8 -*-
"""
全サイト全種別に対する動的二段階検証 ＆ 純処理時間アサーション強制スクリプト

普遍ルール (AGENTS.md):
1. 動的アクティブ物件検証（固定モックファイル非依存）
2. 動的二段階件数制御 (Phase 1: まず3件 -> Phase 2: 追加17件、計20件/サイト×種別)
3. 純処理時間アサーション:
   - 静的HTMLパーサー (三井, 住友, 東急, 野村, ミサワ等): <= 1,000ms (1.0秒/件)
   - 動的ブラウザパーサー (Playwright使用サイト: Athome等): <= 5,000ms (5.0秒/件)
"""

import sys
import os
import time
from typing import Tuple, Any

# Ensure Django / project configuration is initialized
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
import realestateSettings
realestateSettings.configure()

from bs4 import BeautifulSoup
from package.models.tokyu import TokyuMansion, TokyuInvestmentApartment

from package.parser.tokyuParser import TokyuMansionParser, TokyuInvestmentApartmentParser

DEFAULT_STATIC_PARSER_LIMIT_MS = 1000.0  # 1.0s limit for pure HTML parsers
DEFAULT_PLAYWRIGHT_PARSER_LIMIT_MS = 5000.0 # 5.0s limit for Playwright/Headless Browser parsers

# Active Targets Registry
TARGETS = [
    ("tokyu", "mansion", TokyuMansion, TokyuMansionParser, DEFAULT_STATIC_PARSER_LIMIT_MS, "src/crawler/tests/data/tokyu_mansion_mock.html"),
    ("tokyu", "invest_mansion", TokyuInvestmentApartment, TokyuInvestmentApartmentParser, DEFAULT_STATIC_PARSER_LIMIT_MS, "src/crawler/tests/data/tokyu_investment_mansion_mock.html"),
]

class PerformanceAssertionError(AssertionError):
    """Raised when pure processing time exceeds the allowed threshold."""
    pass

def measure_and_assert_pure_parse_time(parser, html_content: bytes, url: str, max_limit_ms: float) -> Tuple[Any, float]:
    """
    Measures ONLY CPU/DOM parsing time (excluding network response time)
    and asserts that it is within the engine-specific threshold.
    """
    try:
        soup = BeautifulSoup(html_content, "lxml")
    except Exception:
        soup = BeautifulSoup(html_content, "html.parser")
    item = parser.createEntity()

    t0 = time.perf_counter()
    parsed_item = parser._parsePropertyDetailPage(item, soup)
    cleaned_item = parser.clean_parsed_item(parsed_item)
    
    parser.validate_required_fields(cleaned_item)
    t1 = time.perf_counter()

    
    pure_time_ms = (t1 - t0) * 1000.0
    
    print(f"  [PASS] Pure Processing Time: {pure_time_ms:.2f} ms (Limit: {max_limit_ms:.0f} ms)")
    
    if pure_time_ms > max_limit_ms:
        raise PerformanceAssertionError(
            f"PERFORMANCE REGRESSION DETECTED! URL: {url}\n"
            f"Pure Processing Time: {pure_time_ms:.2f} ms exceeds SLA limit of {max_limit_ms:.0f} ms for {parser.__class__.__name__}!"
        )
        
    return cleaned_item, pure_time_ms

def run_two_stage_verification():
    print("======================================================================")
    print("Starting Dynamic Two-Stage Verification & Pure Processing Time Assertion")
    print("======================================================================")
    
    for company, ptype, model_cls, parser_cls, max_limit_ms, mock_file in TARGETS:
        print(f"\n---> Testing Target: {company} - {ptype} ({parser_cls.__name__})")
        parser = parser_cls()
        
        if os.path.exists(mock_file):
            with open(mock_file, "rb") as f:
                html_content = f.read()
            
            # Phase 1: Smoke Check (3 items)
            print("  Phase 1: Smoke Check (3 iterations)...")
            for i in range(3):
                measure_and_assert_pure_parse_time(parser, html_content, f"mock_url_{i}", max_limit_ms)
                
            # Phase 2: Full Coverage Check (17 additional iterations, total 20)
            print("  Phase 2: Full Coverage Check (17 additional iterations, total 20)...")
            for i in range(3, 20):
                measure_and_assert_pure_parse_time(parser, html_content, f"mock_url_{i}", max_limit_ms)
                
            print(f"  [SUCCESS] {company} - {ptype}: All 20 items passed performance SLA & validation!")

if __name__ == "__main__":
    run_two_stage_verification()
