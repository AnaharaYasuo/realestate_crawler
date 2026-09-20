# -*- coding: utf-8 -*-
"""Security boundary tests for local files consumed by data-import scripts."""

from pathlib import Path

import pytest

from scripts.data_import import import_mlit_land_prices
from scripts.data_import import import_mlit_stations
from scripts.data_import import sync_estat_municipalities
from scripts.data_import import sync_mlit_land_prices


PATH_MODULES = [
    import_mlit_land_prices,
    import_mlit_stations,
    sync_estat_municipalities,
    sync_mlit_land_prices,
]


@pytest.mark.parametrize("module", PATH_MODULES, ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_safe_path_accepts_descendants_of_current_working_directory(module, tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    candidate = work_dir / "nested" / "input.csv"
    candidate.parent.mkdir(parents=True)
    monkeypatch.chdir(work_dir)

    assert module.safe_path(str(candidate)) == str(candidate.resolve())


@pytest.mark.parametrize("module", PATH_MODULES, ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_safe_path_accepts_repository_files_when_cwd_is_elsewhere(module, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repository_file = Path(module.__file__).resolve()

    assert module.safe_path(str(repository_file)) == str(repository_file)


@pytest.mark.parametrize("module", PATH_MODULES, ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_safe_path_rejects_parent_and_prefix_collision_paths(module, tmp_path, monkeypatch):
    work_dir = tmp_path / "allowed"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)
    outside_paths = [
        tmp_path / "outside.csv",
        tmp_path / "allowed-sibling" / "outside.csv",
    ]

    for outside_path in outside_paths:
        with pytest.raises(ValueError, match="outside the allowed directory"):
            module.safe_path(str(outside_path))


@pytest.mark.parametrize("module", PATH_MODULES, ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_safe_path_rejects_symlink_escape(module, tmp_path, monkeypatch):
    work_dir = tmp_path / "allowed"
    work_dir.mkdir()
    outside_file = tmp_path / "outside.csv"
    outside_file.write_text("sensitive", encoding="utf-8")
    symlink = work_dir / "input.csv"
    symlink.symlink_to(outside_file)
    monkeypatch.chdir(work_dir)

    with pytest.raises(ValueError, match="outside the allowed directory"):
        module.safe_path(str(symlink))


def test_csv_import_entrypoints_reject_existing_outside_files(tmp_path, monkeypatch):
    work_dir = tmp_path / "allowed"
    work_dir.mkdir()
    outside_file = tmp_path / "outside.csv"
    outside_file.write_text("header\nvalue\n", encoding="utf-8")
    monkeypatch.chdir(work_dir)
    monkeypatch.delenv("ESTAT_APP_ID", raising=False)

    with pytest.raises(ValueError, match="outside the allowed directory"):
        import_mlit_land_prices.import_land_prices(str(outside_file))
    with pytest.raises(ValueError, match="outside the allowed directory"):
        import_mlit_stations.import_mlit_stations(str(outside_file))
    with pytest.raises(ValueError, match="outside the allowed directory"):
        sync_estat_municipalities.sync_municipalities(str(outside_file))


def test_json_sync_rejects_existing_outside_file_without_opening_it(tmp_path, monkeypatch, caplog):
    work_dir = tmp_path / "allowed"
    work_dir.mkdir()
    outside_file = tmp_path / "outside.json"
    outside_file.write_text('{"data": []}', encoding="utf-8")
    monkeypatch.chdir(work_dir)

    assert sync_mlit_land_prices.sync_land_prices_from_mlit(json_path=str(outside_file)) is False
    assert "outside the allowed directory" in caplog.text
