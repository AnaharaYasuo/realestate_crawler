# -*- coding: utf-8 -*-
"""
Unit tests for run_mutation_testing.py helper functions
"""
import argparse
import os
import tempfile

from scripts import run_mutation_testing as rmt
from scripts.run_mutation_testing import (
    DEFAULT_DETECTOR_FILE,
    DEFAULT_DETECTOR_TEST_FILE,
    _find_matched_source,
    _resolve_paths,
    _resolve_unit_abs_path,
    _save_mutation_report,
    find_pr_changed_units,
)


def test_resolve_paths_defaults():
    crawler_root = "/app/src/crawler"
    target, test = _resolve_paths(crawler_root, None, None)
    assert DEFAULT_DETECTOR_FILE in target
    assert DEFAULT_DETECTOR_TEST_FILE in test


def test_resolve_unit_abs_path():
    crawler_root = os.path.abspath(".")
    p1 = _resolve_unit_abs_path(crawler_root, "src/crawler/package/utils/url_router.py")
    assert os.path.isabs(p1)

    abs_p = os.path.abspath("test.py")
    assert _resolve_unit_abs_path(crawler_root, abs_p) == abs_p


def test_find_matched_source():
    crawler_root = os.path.abspath(".")
    source_files = [os.path.join("package", "utils", "url_router.py")]

    # Exact match
    matched = _find_matched_source(crawler_root, "url_router.py", source_files)
    assert matched is not None

    # Detector fallback
    matched_det = _find_matched_source(crawler_root, "property_type_detector.py", [])
    assert matched_det is not None
    assert DEFAULT_DETECTOR_FILE in matched_det

    # Router fallback
    matched_rt = _find_matched_source(crawler_root, "router.py", [])
    assert matched_rt is not None
    assert "url_router.py" in matched_rt


def test_find_pr_changed_units_empty_fallback():
    crawler_root = os.path.abspath(".")
    pairs = find_pr_changed_units(crawler_root)
    assert isinstance(pairs, list)


def test_run_pr_code_mutations_skips_when_no_pairs(monkeypatch):
    """Issue #345: 変異対象ペアが無い PR では detector フォールバックせずスキップ合格する"""
    monkeypatch.setattr(rmt, "find_pr_changed_units", lambda _root: [])
    args = argparse.Namespace(threshold=80.0, max_mutants=15)
    report_data = {"results": {}}
    assert rmt._run_pr_code_mutations("/app/src/crawler", args, report_data) is True
    pr_results = report_data["results"]["level2_code_mutation_pr"]
    assert len(pr_results) == 1
    assert pr_results[0]["is_passed"] is True
    assert pr_results[0]["test"] == "(skipped-no-pairs)"
    assert pr_results[0]["target"] == "(none)"


def test_save_mutation_report():
    with tempfile.TemporaryDirectory() as tmpdir:
        report_data = {"test": "data"}
        _save_mutation_report(tmpdir, "test_report.json", report_data)
        report_path = os.path.join(tmpdir, "logs", "test_report.json")
        assert os.path.exists(report_path)
