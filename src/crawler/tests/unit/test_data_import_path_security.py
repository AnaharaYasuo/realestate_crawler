"""Regression tests for the canonical path guards added to data-import tools."""

import importlib
from pathlib import Path

import pytest


SAFE_PATH_MODULES = (
    "scripts.data_import.import_mlit_land_prices",
    "scripts.data_import.import_mlit_stations",
    "scripts.data_import.sync_estat_municipalities",
    "scripts.data_import.sync_mlit_land_prices",
)


@pytest.fixture(params=SAFE_PATH_MODULES)
def guarded_module(request):
    """Load each data-import module that exposes the same path-security contract."""
    return importlib.import_module(request.param)


def test_safe_path_accepts_and_canonicalizes_working_tree_child(
    guarded_module, monkeypatch, tmp_path
):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    monkeypatch.setattr(guarded_module.os, "getcwd", lambda: str(allowed_root))

    candidate = allowed_root / "nested" / ".." / "prices.csv"

    assert guarded_module.safe_path(str(candidate)) == str(
        allowed_root / "prices.csv"
    )


def test_safe_path_accepts_module_source_tree_when_cwd_is_elsewhere(
    guarded_module, monkeypatch, tmp_path
):
    unrelated_cwd = tmp_path / "working"
    unrelated_cwd.mkdir()
    monkeypatch.setattr(guarded_module.os, "getcwd", lambda: str(unrelated_cwd))

    module_path = Path(guarded_module.__file__).resolve()

    assert guarded_module.safe_path(str(module_path)) == str(module_path)


def test_safe_path_rejects_parent_traversal_outside_allowed_trees(
    guarded_module, monkeypatch, tmp_path
):
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    monkeypatch.setattr(guarded_module.os, "getcwd", lambda: str(allowed_root))

    escaped_path = allowed_root / ".." / "outside" / "payload.csv"

    with pytest.raises(ValueError, match="outside the allowed directory"):
        guarded_module.safe_path(str(escaped_path))


def test_safe_path_rejects_symlink_escape(guarded_module, monkeypatch, tmp_path):
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()
    (allowed_root / "escape").symlink_to(outside_root, target_is_directory=True)
    monkeypatch.setattr(guarded_module.os, "getcwd", lambda: str(allowed_root))

    with pytest.raises(ValueError, match="outside the allowed directory"):
        guarded_module.safe_path(str(allowed_root / "escape" / "payload.csv"))
