# Generated for Issue #1137
# ruff: noqa: RUF012

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('package', '0064_reguideinvestment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sumifuinvestmentapartment',
            name='chikunengetsuStr',
            field=models.TextField(blank=True, default=''),
        ),
    ]
