from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("package", "0075_alter_afrkodate_property_type_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tokyukodate",
            name="setsumen",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True),
        ),
    ]
