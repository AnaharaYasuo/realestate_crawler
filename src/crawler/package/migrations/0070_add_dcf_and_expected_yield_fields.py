# Generated for Issue #1349 on 2026-11-11
# 冪等性を備えた期待利回り・DCF理論価格カラム追加マイグレーション（すでにカラムが存在する場合は安全にスキップ）
from django.db import migrations, models


def add_dcf_columns_if_not_exists(apps, schema_editor):
    PropertyEvaluation = apps.get_model("package", "PropertyEvaluation")
    table_name = PropertyEvaluation._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        table_list = schema_editor.connection.introspection.get_table_list(cursor)
        existing_tables = {t.name for t in table_list}
        if table_name not in existing_tables:
            return

        existing_cols = {
            col.name
            for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

        columns = [
            ("expected_gross_yield", "DECIMAL(5, 2)"),
            ("expected_net_yield", "DECIMAL(5, 2)"),
            ("estimated_annual_rent", "BIGINT"),
            ("dcf_theoretical_price", "BIGINT"),
        ]

        for col_name, col_type in columns:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type} NULL;")


def remove_dcf_columns_if_exists(apps, schema_editor):
    PropertyEvaluation = apps.get_model("package", "PropertyEvaluation")
    table_name = PropertyEvaluation._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        table_list = schema_editor.connection.introspection.get_table_list(cursor)
        existing_tables = {t.name for t in table_list}
        if table_name not in existing_tables:
            return

        existing_cols = {
            col.name
            for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

        for col_name in (
            "expected_gross_yield",
            "expected_net_yield",
            "estimated_annual_rent",
            "dcf_theoretical_price",
        ):
            if col_name in existing_cols:
                cursor.execute(f"ALTER TABLE `{table_name}` DROP COLUMN `{col_name}`;")


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ("package", "0069_add_rent_and_cap_rate_potentials"),
    ]

    operations = [  # noqa: RUF012
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="expected_gross_yield",
                    field=models.DecimalField(
                        blank=True, decimal_places=2, max_digits=5, null=True, verbose_name="期待表面利回り (%)"
                    ),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="expected_net_yield",
                    field=models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        verbose_name="期待実質利回り / NCF Cap Rate (%)",
                    ),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="estimated_annual_rent",
                    field=models.BigIntegerField(blank=True, null=True, verbose_name="推定適正年間賃料 (円/年)"),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="dcf_theoretical_price",
                    field=models.BigIntegerField(blank=True, null=True, verbose_name="10年DCF逆算理論価格 (万円)"),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_dcf_columns_if_not_exists, reverse_code=remove_dcf_columns_if_exists),
            ],
        ),
    ]
