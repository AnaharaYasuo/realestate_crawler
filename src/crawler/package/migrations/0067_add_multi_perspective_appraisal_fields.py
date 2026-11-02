# Generated for Issue #1197 on 2026-11-02
# 冪等性を備えたカラム追加マイグレーション（すでにカラムが存在する場合は安全にスキップ）

from django.db import migrations, models


def add_columns_if_not_exists(apps, schema_editor):
    table_name = "package_propertyevaluation"
    columns = [
        ("area_evaluation", "LONGTEXT DEFAULT ''"),
        ("station_evaluation", "LONGTEXT DEFAULT ''"),
        ("hazard_evaluation", "LONGTEXT DEFAULT ''"),
        ("property_spec_evaluation", "LONGTEXT DEFAULT ''"),
        ("mansion_market_evaluation", "LONGTEXT DEFAULT ''"),
    ]
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """,
            [table_name],
        )
        existing_cols = {row[0] for row in cursor.fetchall()}

        for col_name, col_def in columns:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_def};")


def remove_columns_if_exists(apps, schema_editor):
    table_name = "package_propertyevaluation"
    columns = [
        "area_evaluation",
        "station_evaluation",
        "hazard_evaluation",
        "property_spec_evaluation",
        "mansion_market_evaluation",
    ]
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """,
            [table_name],
        )
        existing_cols = {row[0] for row in cursor.fetchall()}

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
                    field=models.TextField(blank=True, default='', verbose_name='地域・需給評価'),
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
