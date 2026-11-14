# Generated for Issue #1410 on 2026-11-14
# 冪等性を備えた自律治癒ライフサイクル・詳細取得日時カラム＆インデックス追加マイグレーション
from django.db import migrations, models


def _existing_columns(schema_editor, cursor, table_name: str) -> set[str] | None:
    existing_tables = {t.name for t in schema_editor.connection.introspection.get_table_list(cursor)}
    if table_name not in existing_tables:
        return None
    return {
        col.name
        for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
    }


def _ensure_single_column_index(schema_editor, cursor, table_name: str, col_name: str, idx_name: str) -> None:
    qn = schema_editor.quote_name
    constraints = schema_editor.connection.introspection.get_constraints(cursor, table_name)
    has_idx = any(
        info.get("index") and info.get("columns") == [col_name]
        for info in constraints.values()
    )
    if not has_idx:
        cursor.execute(f"CREATE INDEX {qn(idx_name)} ON {qn(table_name)} ({qn(col_name)});")


def apply_issue_1410_schema_forwards(apps, schema_editor):
    qn = schema_editor.quote_name
    vendor = schema_editor.connection.vendor
    dt_sql = "DATETIME(6) NULL" if vendor == "mysql" else "DATETIME NULL"
    with schema_editor.connection.cursor() as cursor:
        eval_cols = _existing_columns(schema_editor, cursor, "property_evaluation")
        if eval_cols is None:
            return
        for col_name, col_sql in (
            ("heal_status", "VARCHAR(30) NOT NULL DEFAULT 'healthy'"),
            ("failed_git_sha", "VARCHAR(40) NOT NULL DEFAULT ''"),
            ("recrawl_attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("last_recrawled_at", dt_sql),
            ("last_detail_fetched_at", dt_sql),
        ):
            if col_name not in eval_cols:
                cursor.execute(f"ALTER TABLE {qn('property_evaluation')} ADD COLUMN {qn(col_name)} {col_sql};")

        _ensure_single_column_index(schema_editor, cursor, "property_evaluation", "heal_status", "idx_prop_eval_heal_status")
        _ensure_single_column_index(schema_editor, cursor, "property_evaluation", "failed_git_sha", "idx_prop_eval_failed_git_sha")
        _ensure_single_column_index(schema_editor, cursor, "property_evaluation", "last_detail_fetched_at", "idx_prop_eval_last_detail_dt")


def apply_issue_1410_schema_reverse(apps, schema_editor):
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        eval_cols = _existing_columns(schema_editor, cursor, "property_evaluation")
        if eval_cols is None:
            return
        for col_name in (
            "heal_status",
            "failed_git_sha",
            "recrawl_attempts",
            "last_recrawled_at",
            "last_detail_fetched_at",
        ):
            if col_name in eval_cols:
                cursor.execute(f"ALTER TABLE {qn('property_evaluation')} DROP COLUMN {qn(col_name)};")


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ("package", "0072_add_p10_and_extended_hazard_fields"),
    ]

    operations = [  # noqa: RUF012
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="heal_status",
                    field=models.CharField(
                        choices=[
                            ("healthy", "正常"),
                            ("detected", "異常検知・修復待ち"),
                            ("heal_requested", "Auto-Heal指示発報済み"),
                            ("ready_for_recrawl", "パーサー修正デプロイ済み・再取得待ち"),
                            ("recrawled_pending_ml", "再取得完了・ML再推論待ち"),
                            ("source_data_invalid", "元サイト掲載情報不備（パーサー正常）"),
                        ],
                        db_index=True,
                        default="healthy",
                        max_length=30,
                        verbose_name="自律治癒ステータス",
                    ),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="failed_git_sha",
                    field=models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        max_length=40,
                        verbose_name="異常検知時Git SHA",
                    ),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="recrawl_attempts",
                    field=models.IntegerField(default=0, verbose_name="再クローリング試行回数"),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="last_recrawled_at",
                    field=models.DateTimeField(blank=True, null=True, verbose_name="最終再クローリング日時"),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="last_detail_fetched_at",
                    field=models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="詳細ページ最終取得日時",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    apply_issue_1410_schema_forwards,
                    reverse_code=apply_issue_1410_schema_reverse,
                ),
            ],
        ),
    ]
