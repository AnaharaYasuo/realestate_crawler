# Generated for Issue #1360 on 2026-11-11
# 冪等性を備えた地点別公示・基準地価マスタ（land_price_point_potential）作成マイグレーション
from django.db import migrations, models


def create_land_price_point_table_if_not_exists(apps, schema_editor):
    model = apps.get_model("package", "LandPricePointPotential")
    table_name = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_tables = {t.name for t in schema_editor.connection.introspection.get_table_list(cursor)}
    if table_name not in existing_tables:
        schema_editor.create_model(model)


def drop_land_price_point_table_if_exists(apps, schema_editor):
    model = apps.get_model("package", "LandPricePointPotential")
    table_name = model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        existing_tables = {t.name for t in schema_editor.connection.introspection.get_table_list(cursor)}
    if table_name in existing_tables:
        schema_editor.delete_model(model)


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ("package", "0070_add_dcf_and_expected_yield_fields"),
    ]

    operations = [  # noqa: RUF012
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="LandPricePointPotential",
                    fields=[
                        ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("point_code", models.CharField(db_index=True, max_length=100, unique=True, verbose_name="地点識別コード")),
                        ("survey_type", models.CharField(db_index=True, default="L01", max_length=10, verbose_name="調査区分 (L01/L02)")),
                        ("prefecture", models.CharField(db_index=True, max_length=100, verbose_name="都道府県")),
                        ("city", models.CharField(db_index=True, max_length=100, verbose_name="市区町村")),
                        ("chome_key", models.CharField(blank=True, db_index=True, default="", max_length=150, verbose_name="正規化町丁目キー")),
                        ("latitude", models.FloatField(verbose_name="緯度")),
                        ("longitude", models.FloatField(verbose_name="経度")),
                        ("land_price", models.IntegerField(verbose_name="地点地価（円/㎡）")),
                        ("growth_rate", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name="対前年変動率（％）")),
                        (
                            "land_use",
                            models.CharField(
                                choices=[("residential", "住宅地"), ("commercial", "商業地")],
                                db_index=True,
                                default="residential",
                                max_length=50,
                                verbose_name="用途区分",
                            ),
                        ),
                        ("zone_name", models.CharField(blank=True, default="", max_length=100, verbose_name="用途地域")),
                        ("road_width", models.FloatField(blank=True, null=True, verbose_name="前面道路幅員（m）")),
                        ("station_name", models.CharField(blank=True, db_index=True, default="", max_length=100, verbose_name="最寄駅名")),
                        ("station_distance_m", models.IntegerField(blank=True, null=True, verbose_name="最寄駅距離（m）")),
                        ("has_gas", models.BooleanField(default=True, verbose_name="ガス供給有無")),
                        ("has_water", models.BooleanField(default=True, verbose_name="上水道有無")),
                        ("has_sewer", models.BooleanField(default=True, verbose_name="下水道有無")),
                        ("updated_at", models.DateTimeField(auto_now=True, verbose_name="最終同期日時")),
                    ],
                    options={
                        "verbose_name": "地点別公示・基準地価マスタ",
                        "verbose_name_plural": "地点別公示・基準地価マスタ",
                        "db_table": "land_price_point_potential",
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    create_land_price_point_table_if_not_exists,
                    reverse_code=drop_land_price_point_table_if_exists,
                ),
            ],
        ),
    ]
