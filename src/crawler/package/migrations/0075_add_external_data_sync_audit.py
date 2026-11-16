# Generated for Issue #1538 on 2026-11-16
# Add ExternalDataSyncAudit model for table-level external dataset periodic TTL sync management
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("package", "0074_add_smtrc_investment_kaisu"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalDataSyncAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dataset_key", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="データセット識別子")),
                ("dataset_name", models.CharField(blank=True, default="", max_length=128, verbose_name="データセット名称")),
                ("last_synced_at", models.DateTimeField(db_index=True, verbose_name="最終同期日時")),
                ("record_count", models.IntegerField(default=0, verbose_name="同期レコード件数")),
                ("status", models.CharField(default="SUCCESS", max_length=32, verbose_name="同期ステータス")),
                ("duration_seconds", models.IntegerField(default=0, verbose_name="所要時間(秒)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="初回登録日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
            ],
            options={
                "db_table": "external_data_sync_audit",
                "verbose_name": "外部データ同期監査レコード",
                "verbose_name_plural": "外部データ同期監査レコード",
            },
        ),
    ]
