# Generated for Issue #1380 on 2026-11-12
# 冪等性を備えた P10 下限予測・不確実性指標・analyzed_at インデックス・拡張ハザードカラム追加マイグレーション
from django.db import migrations, models


def _existing_columns(schema_editor, cursor, table_name: str) -> set[str] | None:
    existing_tables = {t.name for t in schema_editor.connection.introspection.get_table_list(cursor)}
    if table_name not in existing_tables:
        return None
    return {
        col.name
        for col in schema_editor.connection.introspection.get_table_description(cursor, table_name)
    }


def apply_issue_1380_schema_forwards(apps, schema_editor):
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        eval_cols = _existing_columns(schema_editor, cursor, "property_evaluation")
        if eval_cols is not None:
            for col_name, col_sql in (
                ("first_stage_p10_price", "DECIMAL(12, 0) NULL"),
                ("prediction_uncertainty_ratio", "DOUBLE NULL"),
            ):
                if col_name not in eval_cols:
                    cursor.execute(f"ALTER TABLE {qn('property_evaluation')} ADD COLUMN {qn(col_name)} {col_sql};")

            constraints = schema_editor.connection.introspection.get_constraints(cursor, "property_evaluation")
            has_analyzed_idx = any(
                info.get("index") and info.get("columns") == ["analyzed_at"]
                for info in constraints.values()
            )
            if not has_analyzed_idx:
                cursor.execute(
                    f"CREATE INDEX {qn('idx_prop_eval_analyzed_at')} "
                    f"ON {qn('property_evaluation')} ({qn('analyzed_at')});"
                )

        hz_cols = _existing_columns(schema_editor, cursor, "hazard_map_potential")
        if hz_cols is not None:
            for col_name in ("tsunami_risk_level", "red_zone_landslide_flag", "liquefaction_risk_level"):
                if col_name not in hz_cols:
                    cursor.execute(
                        f"ALTER TABLE {qn('hazard_map_potential')} "
                        f"ADD COLUMN {qn(col_name)} INTEGER NOT NULL DEFAULT 0;"
                    )


def apply_issue_1380_schema_reverse(apps, schema_editor):
    qn = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        eval_cols = _existing_columns(schema_editor, cursor, "property_evaluation")
        if eval_cols is not None:
            for col_name in ("first_stage_p10_price", "prediction_uncertainty_ratio"):
                if col_name in eval_cols:
                    cursor.execute(f"ALTER TABLE {qn('property_evaluation')} DROP COLUMN {qn(col_name)};")

        hz_cols = _existing_columns(schema_editor, cursor, "hazard_map_potential")
        if hz_cols is not None:
            for col_name in ("tsunami_risk_level", "red_zone_landslide_flag", "liquefaction_risk_level"):
                if col_name in hz_cols:
                    cursor.execute(f"ALTER TABLE {qn('hazard_map_potential')} DROP COLUMN {qn(col_name)};")


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ("package", "0071_add_land_price_point_potential"),
    ]

    operations = [  # noqa: RUF012
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="first_stage_p10_price",
                    field=models.DecimalField(
                        blank=True, decimal_places=0, max_digits=12, null=True, verbose_name="一次予測下限P10価格"
                    ),
                ),
                migrations.AddField(
                    model_name="propertyevaluation",
                    name="prediction_uncertainty_ratio",
                    field=models.FloatField(blank=True, null=True, verbose_name="予測不確実性比率"),
                ),
                migrations.AlterField(
                    model_name="propertyevaluation",
                    name="analyzed_at",
                    field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="解析実行日時"),
                ),
                migrations.AddField(
                    model_name="hazardmappotential",
                    name="tsunami_risk_level",
                    field=models.IntegerField(default=0, verbose_name="津波浸水リスクレベル (0:無 - 3:高)"),
                ),
                migrations.AddField(
                    model_name="hazardmappotential",
                    name="red_zone_landslide_flag",
                    field=models.IntegerField(
                        default=0, verbose_name="土砂災害特別警戒区域(レッドゾーン)リスク (0/1)"
                    ),
                ),
                migrations.AddField(
                    model_name="hazardmappotential",
                    name="liquefaction_risk_level",
                    field=models.IntegerField(default=0, verbose_name="液状化リスクレベル (0:低 - 3:高)"),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    apply_issue_1380_schema_forwards,
                    reverse_code=apply_issue_1380_schema_reverse,
                ),
            ],
        ),
    ]
