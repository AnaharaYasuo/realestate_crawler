#!/usr/bin/env python3
"""PR size guardrail and DoD drift detector (Chapter 12.4-12.5)."""
import re


def evaluate_pr_dod(
    changed_files: list[str],
    total_changed_lines: int,
    pr_body: str,
    max_lines: int = 800,
) -> list[str]:
    """Check PR size limits and detect discrepancies between DoD checkboxes and diff."""
    warnings: list[str] = []
    if total_changed_lines > max_lines:
        warnings.append(f"oversized_pr:{total_changed_lines}>{max_lines}")

    test_checked = bool(re.search(r"-\s*\[x\]\s*.*テスト", pr_body, re.IGNORECASE))
    has_test_file = any("test_" in f or "/tests/" in f.replace("\\", "/") for f in changed_files)
    if test_checked and not has_test_file:
        warnings.append("dod_drift:test_checkbox_checked_without_test_file_changes")

    return warnings
