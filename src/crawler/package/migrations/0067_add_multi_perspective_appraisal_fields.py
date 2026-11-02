# Generated for Issue #1197 on 2026-11-02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('package', '0066_add_evaluation_qualitative_fields'),
    ]

    operations = [
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
    ]
