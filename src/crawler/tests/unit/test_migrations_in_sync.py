"""Issue #905: モデルとマイグレーションのDBスキーマ乖離検知テスト"""
from __future__ import annotations

from typing import Any

from django.apps import apps
from django.db import migrations, models
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.special import SeparateDatabaseAndState
from django.test import override_settings

_SCHEMA_ATTRS = (
    "null",
    "max_length",
    "max_digits",
    "decimal_places",
    "unique",
    "db_index",
    "db_column",
    "primary_key",
)


def _field_schema_signature(field: Any) -> tuple[Any, ...]:
    """DBカラム定義（DDL）に影響するフィールド属性シグネチャを返す。"""
    return (
        field.get_internal_type(),
        *(getattr(field, attr, None) for attr in _SCHEMA_ATTRS),
    )


def _apply_operations(
    ops: list[Any],
    schema_models: dict[str, dict[str, Any]],
) -> None:
    """マイグレーション操作列を走査し、モデル別のフィールド辞書を構築する。"""
    for op in ops:
        if isinstance(op, SeparateDatabaseAndState):
            _apply_operations(list(op.state_operations), schema_models)
        elif isinstance(op, migrations.CreateModel):
            schema_models[op.name.lower()] = dict(op.fields)
        elif isinstance(op, migrations.DeleteModel):
            schema_models.pop(op.name.lower(), None)
        elif isinstance(op, migrations.RenameModel):
            schema_models[op.new_name.lower()] = schema_models.pop(
                op.old_name.lower(), {}
            )
        elif isinstance(op, migrations.AddField):
            schema_models.setdefault(op.model_name.lower(), {})[op.name] = op.field
        elif isinstance(op, migrations.RemoveField):
            schema_models.get(op.model_name.lower(), {}).pop(op.name, None)
        elif isinstance(op, migrations.RenameField):
            model_fields = schema_models.get(op.model_name.lower(), {})
            if op.old_name in model_fields:
                model_fields[op.new_name] = model_fields.pop(op.old_name)
        elif isinstance(op, migrations.AlterField):
            schema_models.setdefault(op.model_name.lower(), {})[op.name] = op.field


def _build_migrated_schema(loader: MigrationLoader, app_label: str = "package") -> dict[str, dict[str, Any]]:
    """マイグレーション履歴から最終スキーマ状態（モデル名 -> フィールド辞書）を高速構築する。"""
    schema_models: dict[str, dict[str, Any]] = {}
    leaf_nodes = loader.graph.leaf_nodes(app_label)
    visited: set[tuple[str, str]] = set()
    for leaf in leaf_nodes:
        for node in loader.graph.forwards_plan(leaf):
            if node in visited or node[0] != app_label:
                continue
            visited.add(node)
            migration = loader.get_migration(*node)
            _apply_operations(list(migration.operations), schema_models)
    return schema_models


def _find_schema_diffs(
    migrated_models: dict[str, dict[str, Any]],
    app_models: list[Any],
) -> list[str]:
    """マイグレーション上のモデル定義と現在のDjangoモデル定義のDDL差分を検出する。"""
    diffs: list[str] = []
    expected_model_names: set[str] = set()

    for model in app_models:
        if model._meta.abstract or model._meta.proxy:
            continue
        model_key = model._meta.model_name.lower()
        expected_model_names.add(model_key)

        if model_key not in migrated_models:
            diffs.append(f"CreateModel missing: {model.__name__}")
            continue

        mig_fields = migrated_models[model_key]
        model_fields = {f.name: f for f in model._meta.local_fields}

        for fname, field in model_fields.items():
            if fname not in mig_fields:
                diffs.append(f"AddField missing: {model.__name__}.{fname}")
            elif _field_schema_signature(field) != _field_schema_signature(mig_fields[fname]):
                diffs.append(
                    f"AlterField schema mismatch: {model.__name__}.{fname} "
                    f"(model={_field_schema_signature(field)} vs migration={_field_schema_signature(mig_fields[fname])})"
                )

        for fname in mig_fields:
            if fname not in model_fields:
                diffs.append(f"RemoveField missing: {model.__name__}.{fname}")

    for mig_model_key in migrated_models:
        if mig_model_key not in expected_model_names:
            diffs.append(f"DeleteModel missing: {mig_model_key}")

    return diffs


@override_settings(MIGRATION_MODULES={})
def test_migrations_in_sync_with_models() -> None:
    """モデル定義とマイグレーションの間にDBスキーマ乖離やリーフ競合が無いこと。"""
    loader = MigrationLoader(None, ignore_no_migrations=True)
    conflicts = loader.detect_conflicts()
    assert not conflicts, f"マイグレーション競合が存在します: {conflicts}"

    migrated_models = _build_migrated_schema(loader, "package")
    app_models = list(apps.get_app_config("package").get_models())
    schema_diffs = _find_schema_diffs(migrated_models, app_models)

    assert not schema_diffs, (
        "未作成のDBスキーママイグレーションが検出されました:\n"
        + "\n".join(f"  - {desc}" for desc in schema_diffs)
    )


def test_schema_diff_detection_and_meta_ignore() -> None:
    """AddField/CreateModel/型変更は検知し、blankやdefaultのみの変更は除外すること。"""
    schema_models: dict[str, dict[str, Any]] = {}
    _apply_operations(
        [
            migrations.CreateModel(
                name="SampleModel",
                fields=[
                    ("id", models.AutoField(primary_key=True)),
                    ("status", models.TextField()),
                ],
            ),
            # blank/default のみの AlterField はスキーマシグネチャを変えない
            migrations.AlterField(
                model_name="samplemodel",
                name="status",
                field=models.TextField(blank=True, default=""),
            ),
        ],
        schema_models,
    )
    assert "samplemodel" in schema_models
    assert _field_schema_signature(schema_models["samplemodel"]["status"]) == _field_schema_signature(
        models.TextField()
    )
    assert _field_schema_signature(schema_models["samplemodel"]["status"]) != _field_schema_signature(
        models.IntegerField(null=True)
    )
