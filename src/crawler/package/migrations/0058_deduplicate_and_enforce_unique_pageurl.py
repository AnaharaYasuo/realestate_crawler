# ruff: noqa: RUF012
# Generated for Issue #660: deduplicate and enforce unique pageUrl
from django.db import DatabaseError, OperationalError, migrations, models


def deduplicate_all_properties(apps, schema_editor):
    """各テーブルの重複pageUrlを削除し最新idのみ残す"""
    from django.db import connection
    app_config = apps.get_app_config('package')
    with connection.cursor() as cursor:
        for model in app_config.get_models():
            if not model._meta.managed:
                continue
            table = model._meta.db_table
            field_names = [f.name for f in model._meta.fields]
            if 'pageUrl' not in field_names:
                continue
            sql_del = (
                f"DELETE FROM {table} "
                f"WHERE id NOT IN ("
                f"    SELECT max_id FROM ("
                f"        SELECT MAX(id) AS max_id FROM {table} GROUP BY pageUrl"
                f"    ) AS keep_rows"
                f")"
            )
            try:
                cursor.execute(sql_del)
            except (OperationalError, DatabaseError):
                pass


MODELS = [
    'afrkodate', 'afrmansion', 'afrtochi', 'athomeinvestmentapartment',
    'athomekodate', 'athomemansion', 'athometochi', 'daikyokodate',
    'daikyomansion', 'daikyotochi', 'daiwakodate', 'daiwamansion',
    'daiwatochi', 'heimkodate', 'heimmansion', 'heimtochi',
    'homesinvestmentapartment', 'homeskodate', 'homesmansion',
    'homestochi', 'keikyukodate', 'keikyumansion', 'keikyutochi',
    'keiokodate', 'keiomansion', 'keiotochi', 'keiseikodate',
    'keiseimansion', 'keiseitochi', 'kenbiyainvestmentapartment',
    'kenbiyainvestmentbuilding', 'kenbiyakodate', 'kenbiyamansion',
    'kenbiyatochi', 'misawainvestmentapartment', 'misawainvestmentkodate',
    'misawakodate', 'misawamansion', 'misawatochi',
    'mitsuiinvestmentapartment', 'mitsuiinvestmentkodate', 'mitsuikodate',
    'mitsuimansion', 'mitsuitochi', 'mizuhoinvestment', 'mizuhokodate',
    'mizuhomansion', 'mizuhotochi', 'nomurainvestmentapartment',
    'nomurainvestmentkodate', 'nomurakodate', 'nomuramansion',
    'nomuratochi', 'odakyuinvestment', 'odakyukodate', 'odakyumansion',
    'odakyutochi', 'reariekodate', 'reariemansion', 'rearietochi',
    'seibukodate', 'seibumansion', 'seibutochi', 'sekisuikodate',
    'sekisuimansion', 'sekisuitochi', 'smtrcinvestment', 'smtrckodate',
    'smtrcmansion', 'smtrctochi', 'sotetsukodate', 'sotetsumansion',
    'sotetsutochi', 'sumai1investment', 'sumai1kodate', 'sumai1mansion',
    'sumai1tochi', 'sumifuinvestmentapartment', 'sumifuinvestmentkodate',
    'sumifukodate', 'sumifumansion', 'sumifutochi', 'sumirininvestment',
    'sumirinkodate', 'sumirinmansion', 'sumirintochi',
    'tokyuinvestmentapartment', 'tokyuinvestmentkodate', 'tokyukodate',
    'tokyumansion', 'tokyutochi', 'totatekodate', 'totatemansion',
    'totatetochi',
]


class Migration(migrations.Migration):

    dependencies = [
        ('package', '0057_alter_afrkodate_busstation1_and_more'),
    ]

    operations = [
        migrations.RunPython(deduplicate_all_properties, reverse_code=migrations.RunPython.noop),
    ] + [
        migrations.AlterField(
            model_name=m_name,
            name='pageUrl',
            field=models.CharField(db_index=True, max_length=500, unique=True, verbose_name='URL'),
        )
        for m_name in MODELS
    ]
