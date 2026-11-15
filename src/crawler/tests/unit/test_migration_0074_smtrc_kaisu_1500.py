"""Unit tests for migration 0074: add kaisu field to smtrc_investment (Issue #1500)"""

import importlib
from pathlib import Path
from unittest.mock import MagicMock
from package.models.smtrc import SmtrcInvestment

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_smtrc_investment_model_has_kaisu_field():
    """Verify SmtrcInvestment model field declaration for kaisu"""
    field_names = [f.name for f in SmtrcInvestment._meta.fields]
    assert "kaisu" in field_names
    assert "kaisuStr" in field_names


def test_migration_0074_file_and_structure():
    """Verify migration 0074 file exists and dependencies are consistent"""
    mig_path = REPO_ROOT / "src" / "crawler" / "package" / "migrations" / "0074_add_smtrc_investment_kaisu.py"
    assert mig_path.exists(), f"Migration file missing: {mig_path}"

    migration_mod = importlib.import_module("package.migrations.0074_add_smtrc_investment_kaisu")
    assert hasattr(migration_mod, "add_kaisu_column_forwards")
    assert hasattr(migration_mod, "add_kaisu_column_reverse")
    assert hasattr(migration_mod, "Migration")
    assert migration_mod.Migration.dependencies == [("package", "0073_add_self_healing_lifecycle_fields")]


def test_migration_0074_forwards_logic():
    """Verify forwards logic inspects columns and issues alter table when missing"""
    migration_mod = importlib.import_module("package.migrations.0074_add_smtrc_investment_kaisu")
    add_kaisu_column_forwards = migration_mod.add_kaisu_column_forwards

    mock_schema_editor = MagicMock()
    mock_cursor = MagicMock()
    mock_schema_editor.connection.cursor.return_value.__enter__.return_value = mock_cursor
    mock_schema_editor.quote_name = lambda s: f"`{s}`"

    # Mock introspection
    mock_col1 = MagicMock()
    mock_col1.name = "id"
    mock_schema_editor.connection.introspection.get_table_description.return_value = [mock_col1]
    mock_table = MagicMock()
    mock_table.name = "smtrc_investment"
    mock_schema_editor.connection.introspection.get_table_list.return_value = [mock_table]

    add_kaisu_column_forwards(None, mock_schema_editor)

    mock_cursor.execute.assert_called_once_with("ALTER TABLE `smtrc_investment` ADD COLUMN `kaisu` INTEGER NULL;")
