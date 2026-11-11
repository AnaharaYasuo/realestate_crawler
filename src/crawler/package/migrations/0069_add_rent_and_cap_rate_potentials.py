# Generated for Issue #1354 on 2026-11-11
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ('package', '0068_comprehensive_future_and_historical_potentials'),
    ]

    operations = [  # noqa: RUF012
        migrations.CreateModel(
            name='RentMarketPotential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefecture', models.CharField(db_index=True, max_length=100, verbose_name='都道府県')),
                ('city', models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='市区町村')),
                ('station_name', models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='駅名 (正規化名)')),
                ('town_name', models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='町丁目・メッシュ名')),
                ('building_type', models.CharField(db_index=True, default='all', max_length=30, verbose_name='建物種別 (mansion/apartment/kodate/all)')),
                ('layout_type', models.CharField(default='all', max_length=30, verbose_name='間取り区分')),
                ('age_band', models.CharField(default='all', max_length=30, verbose_name='築年帯')),
                ('monthly_rent_yen', models.IntegerField(verbose_name='月額家賃相場 (円)')),
                ('standard_area_sqm', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='換算基準専有面積 (㎡)')),
                ('rent_per_sqm', models.IntegerField(verbose_name='月額賃料単価 (円/㎡)')),
                ('sample_count', models.IntegerField(blank=True, null=True, verbose_name='集計サンプル件数')),
                ('source', models.CharField(db_index=True, max_length=50, verbose_name='データソース識別子')),
                ('gcs_raw_key', models.CharField(blank=True, default='', max_length=500, verbose_name='GCS原本保存パス')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最終同期日時')),
            ],
            options={
                'verbose_name': '地域・駅別家賃相場マスタ',
                'verbose_name_plural': '地域・駅別家賃相場マスタ',
                'db_table': 'rent_market_potential',
                'unique_together': {(
                    'prefecture', 'city', 'station_name', 'town_name',
                    'building_type', 'layout_type', 'age_band', 'source',
                )},
            },
        ),
        migrations.CreateModel(
            name='CapRateBenchmarkPotential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefecture', models.CharField(db_index=True, max_length=100, verbose_name='都道府県')),
                ('city', models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='市区町村')),
                ('station_name', models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='駅名 (正規化名)')),
                ('asset_type', models.CharField(db_index=True, default='all', max_length=40, verbose_name='アセット区分')),
                ('expected_gross_yield', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='期待・実勢表面利回り (%)')),
                ('expected_net_cap_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='期待実質利回り / NCF Cap Rate (%)')),
                ('standard_opex_ratio', models.DecimalField(decimal_places=2, default=20.0, max_digits=5, verbose_name='標準運営経費率 OPEX率 (%)')),
                ('rental_vacancy_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='賃貸用住宅空室率 (%)')),
                ('total_vacancy_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='住宅全般空室率 (%)')),
                ('jgb_spread_bps', models.IntegerField(blank=True, null=True, verbose_name='10年国債利回りスプレッド (bps)')),
                ('demand_supply_score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='検索需要/掲載供給バランス指数')),
                ('sample_count', models.IntegerField(blank=True, null=True, verbose_name='集計サンプル件数')),
                ('survey_period', models.CharField(blank=True, default='', max_length=20, verbose_name='調査対象時点')),
                ('source', models.CharField(db_index=True, max_length=50, verbose_name='データソース識別子')),
                ('gcs_raw_key', models.CharField(blank=True, default='', max_length=500, verbose_name='GCS原本保存パス')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最終同期日時')),
            ],
            options={
                'verbose_name': '地域・アセット別キャップレートマスタ',
                'verbose_name_plural': '地域・アセット別キャップレートマスタ',
                'db_table': 'cap_rate_benchmark_potential',
                'unique_together': {('prefecture', 'city', 'station_name', 'asset_type', 'source')},
            },
        ),
    ]
