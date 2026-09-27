from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('package', '0054_crawlertaskexecution_results_json'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tokyutochi',
            name='chisei',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tokyutochi',
            name='boukaChiiki',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tokyutochi',
            name='saikenchiku',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tokyutochi',
            name='sonotaChiiki',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='tokyutochi',
            name='kokudoHou',
            field=models.TextField(blank=True),
        ),
    ]
