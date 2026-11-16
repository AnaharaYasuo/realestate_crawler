# Generated for Issue #1500 on 2026-11-15
# SmtrcInvestment に kaisu (階数・数値) カラムを追加するマイグレーション
from django.db import migrations, models


def _existing_columns(schema_editor, cursor, table_name: str) -> set[str] | None:
    existing_tables = {t.name for t in schema_editor.connection.introspection.get_table_list(cursor)}
    if table_name not in existing_tables:
        return None
    return {
        col.name
        for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
    }


def add_kaisu_column_forwards(apps, schema_editor):
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cols = _existing_columns(schema_editor, cursor, "smtrc_investment")
        if cols is not None and "kaisu" not in cols:
            cursor.execute(f"ALTER TABLE {qn('smtrc_investment')} ADD COLUMN {qn('kaisu')} INTEGER NULL;")


def add_kaisu_column_reverse(apps, schema_editor):
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        cols = _existing_columns(schema_editor, cursor, "smtrc_investment")
        if cols is not None and "kaisu" in cols:
            cursor.execute(f"ALTER TABLE {qn('smtrc_investment')} DROP COLUMN {qn('kaisu')};")


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("package", "0073_add_self_healing_lifecycle_fields"),
    ]

    operations = [
        migrations.RunPython(
            add_kaisu_column_forwards,
            reverse_code=add_kaisu_column_reverse,
        ),
    ]
