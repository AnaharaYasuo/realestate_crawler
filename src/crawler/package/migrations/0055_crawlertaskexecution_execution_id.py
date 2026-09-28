from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [  # noqa: RUF012
        ('package', '0054_crawlertaskexecution_results_json'),
    ]

    operations = [  # noqa: RUF012
        migrations.AddField(
            model_name='crawlertaskexecution',
            name='execution_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128),
        ),
    ]
