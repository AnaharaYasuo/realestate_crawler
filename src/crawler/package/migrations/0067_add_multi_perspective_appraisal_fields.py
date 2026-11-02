# Generated for Issue #1197 on 2026-11-02
# 冪等性を備えたカラム追加マイグレーション（すでにカラムが存在する場合は安全にスキップ）
from django.db import migrations, models


def add_columns_if_not_exists(apps, schema_editor):
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

        # エンジンに応じた型指定
        is_mysql = schema_editor.connection.vendor == "mysql"
        text_type = "LONGTEXT" if is_mysql else "TEXT"

        columns = [
            ("area_evaluation", text_type),
            ("station_evaluation", text_type),
            ("hazard_evaluation", text_type),
            ("property_spec_evaluation", text_type),
            ("mansion_market_evaluation", text_type),
        ]

        for col_name, col_type in columns:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type} NULL;")


def remove_columns_if_exists(apps, schema_editor):
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
            "area_evaluation",
            "station_evaluation",
            "hazard_evaluation",
            "property_spec_evaluation",
            "mansion_market_evaluation",
        ]

        for col_name in columns:
            if col_name in existing_cols:
                cursor.execute(f"ALTER TABLE `{table_name}` DROP COLUMN `{col_name}`;")


class Migration(migrations.Migration):

    dependencies = [
        ('package', '0066_add_evaluation_qualitative_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='propertyevaluation',
                    name='area_evaluation',
                    field=models.TextField(blank=True, default='', verbose_name='地域の需給評価'),
                ),
                migrations.AddField(
                    model_name='propertyevaluation',
                    name='station_evaluation',
                    field=models.TextField(blank=True, default='', verbose_name='駅力・交通アクセス評価'),
                ),
                migrations.AddField(
                    model_name='propertyevaluation',
                    name='hazard_evaluation',
                    field=models.TextField(blank=True, default='', verbose_name='防災・地盤・ハザード評価'),
                ),
                migrations.AddField(
                    model_name='propertyevaluation',
                    name='property_spec_evaluation',
                    field=models.TextField(blank=True, default='', verbose_name='物件スペック・価格歪み分析'),
                ),
                migrations.AddField(
                    model_name='propertyevaluation',
                    name='mansion_market_evaluation',
                    field=models.TextField(blank=True, default='', verbose_name='マンションレビュー過去取引事例・相場分析'),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_columns_if_not_exists, reverse_code=remove_columns_if_exists),
            ],
        ),
    ]
