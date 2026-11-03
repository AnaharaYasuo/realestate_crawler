# -*- coding: utf-8 -*-
# Generated for Issue #1210 on 2026-11-03
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('package', '0067_add_multi_perspective_appraisal_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='MunicipalFuturePotential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefecture', models.CharField(db_index=True, max_length=100, verbose_name='都道府県')),
                ('city', models.CharField(db_index=True, max_length=100, verbose_name='市区町村')),
                ('target_year', models.IntegerField(db_index=True, verbose_name='推計対象年 (2025, 2030, 2035, 2040, 2045, 2050)')),
                ('projected_population', models.IntegerField(verbose_name='推計総人口 (人)')),
                ('pop_change_rate_from_2020', models.DecimalField(decimal_places=2, max_digits=6, verbose_name='2020年比増減率 (%)')),
                ('working_age_ratio', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='生産年齢人口比率 15-64歳 (%)')),
                ('elderly_ratio', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='老年人口比率 65歳以上 (%)')),
                ('projected_households', models.IntegerField(blank=True, null=True, verbose_name='推計一般世帯数')),
                ('single_household_ratio', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='単身世帯比率 (%)')),
            ],
            options={
                'verbose_name': '自治体将来推計人口マスタ',
                'verbose_name_plural': '自治体将来推計人口マスタ',
                'db_table': 'municipal_future_potential',
                'unique_together': {('prefecture', 'city', 'target_year')},
            },
        ),
        migrations.CreateModel(
            name='MunicipalYearlyPotential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefecture', models.CharField(db_index=True, max_length=100, verbose_name='都道府県')),
                ('city', models.CharField(db_index=True, max_length=100, verbose_name='市区町村')),
                ('year', models.IntegerField(db_index=True, verbose_name='実績年')),
                ('total_population', models.IntegerField(blank=True, null=True, verbose_name='総人口 (人)')),
                ('population_growth_rate', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='人口前年比増減率 (%)')),
                ('average_income', models.IntegerField(verbose_name='納税義務者1人あたり課税対象所得 (千円)')),
                ('income_growth_rate', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='所得前年比変動率 (%)')),
                ('income_3y_cagr', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True, verbose_name='過去3年所得CAGR (%)')),
                ('population_density', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True, verbose_name='人口密度 (人/㎢)')),
            ],
            options={
                'verbose_name': '自治体年次推移統計マスタ',
                'verbose_name_plural': '自治体年次推移統計マスタ',
                'db_table': 'municipal_yearly_potential',
                'unique_together': {('prefecture', 'city', 'year')},
            },
        ),
        migrations.CreateModel(
            name='StationYearlyPotential',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('station_name', models.CharField(db_index=True, max_length=100, verbose_name='駅名 (正規化名)')),
                ('railway_line', models.CharField(blank=True, default='', max_length=100, verbose_name='路線名')),
                ('year', models.IntegerField(db_index=True, verbose_name='実績年')),
                ('passenger_volume', models.IntegerField(verbose_name='1日平均乗降客数 (人/日)')),
                ('volume_yoy_growth', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='前年比増減率 (%)')),
                ('volume_3y_cagr', models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='過去3年CAGR (%)')),
            ],
            options={
                'verbose_name': '駅年次推移統計マスタ',
                'verbose_name_plural': '駅年次推移統計マスタ',
                'db_table': 'station_yearly_potential',
                'unique_together': {('station_name', 'railway_line', 'year')},
            },
        ),
        migrations.CreateModel(
            name='UrbanInductionZoneMaster',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefecture', models.CharField(db_index=True, max_length=100, verbose_name='都道府県')),
                ('city', models.CharField(db_index=True, max_length=100, verbose_name='市区町村')),
                ('town_name', models.CharField(blank=True, db_index=True, default='', max_length=100, verbose_name='大字・町丁目名')),
                ('is_urban_induction_zone', models.BooleanField(default=False, verbose_name='都市機能誘導区域内フラグ')),
                ('is_residential_induction_zone', models.BooleanField(default=False, verbose_name='居住誘導区域内フラグ')),
                ('plan_status', models.CharField(blank=True, default='作成公表済', max_length=50, verbose_name='計画作成状況')),
            ],
            options={
                'verbose_name': '立地適正化計画区域マスタ',
                'verbose_name_plural': '立地適正化計画区域マスタ',
                'db_table': 'urban_induction_zone_master',
                'unique_together': {('prefecture', 'city', 'town_name')},
            },
        ),
    ]
