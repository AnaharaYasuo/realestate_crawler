# -*- coding: utf-8 -*-
"""Unit tests for pre_pr_check file categorization and optimization (Issue #579)."""
from scripts.ops.pre_pr_check import (
    FileCategory,
    classify_changed_files,
    format_terse_error,
)


def test_classify_docs_only():
    files = ["README.md", "docs/requirements/spec.md", "docs/basic_design/design.md"]
    cat = classify_changed_files(files)
    assert isinstance(cat, FileCategory)
    assert cat.is_docs_only is True
    assert cat.has_python is False
    assert cat.has_terraform is False
    assert cat.has_workflow is False


def test_classify_terraform_only():
    files = ["terraform/main.tf", "terraform/variables.tf"]
    cat = classify_changed_files(files)
    assert cat.is_tf_only is True
    assert cat.has_terraform is True
    assert cat.has_python is False
    assert cat.is_docs_only is False


def test_classify_python_and_docs():
    files = ["src/crawler/package/parser/mitsui.py", "docs/spec.md"]
    cat = classify_changed_files(files)
    assert cat.has_python is True
    assert cat.has_docs is True
    assert cat.is_docs_only is False
    assert cat.is_tf_only is False


def test_classify_empty():
    cat = classify_changed_files([])
    assert cat.is_empty is True
    assert cat.is_docs_only is False
    assert cat.changed_count == 0


def test_classify_requirements_txt():
    cat = classify_changed_files(["requirements.txt"])
    assert cat.is_docs_only is False
    assert cat.has_python is True


def test_classify_workflow_file():
    files = [".github/workflows/test.yml"]
    cat = classify_changed_files(files)
    assert cat.has_workflow is True
    assert cat.has_python is False

    # Non-workflow YAML should not be marked as workflow
    non_wf = classify_changed_files(["Taskfile.yml", "docker-compose.yaml"])
    assert non_wf.has_workflow is False
    assert non_wf.has_unclassified is True


def test_format_terse_error():
    first = "File '/app/test.py', line 45, in <module>"
    last = "ValueError: invalid value provided for test case"
    long_error = f"Traceback (most recent call last):\n  {first}\n    some_func()\n{last}"
    compressed = format_terse_error(long_error)
    assert compressed == f"{first} -> {last}"

    boundary_error = "ValueError: " + "x" * 300
    assert format_terse_error(boundary_error) == boundary_error[:237] + "..."
