from django.db import models


class ExternalDataSyncAudit(models.Model):
    """
    外部公的データセットの定期同期・洗い替え（TTL管理）監査モデル (Issue #1538).

    各公的データセット（総務省e-Stat、国土数値情報駅乗降客数、用途地域、ハザードマップ等）の
    最終全量同期日時、取得件数、実行ステータスをテーブル単位で永続化し、
    未登録時のみならず指定TTL（30日/90日等）経過時の自動定期再同期を管理する。
    """

    dataset_key = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name="データセット識別子",
    )
    dataset_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="データセット名称",
    )
    last_synced_at = models.DateTimeField(
        db_index=True,
        verbose_name="最終同期日時",
    )
    record_count = models.IntegerField(
        default=0,
        verbose_name="同期レコード件数",
    )
    status = models.CharField(
        max_length=32,
        default="SUCCESS",
        verbose_name="同期ステータス",
    )
    duration_seconds = models.IntegerField(
        default=0,
        verbose_name="所要時間(秒)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="初回登録日時",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="更新日時",
    )

    class Meta:
        db_table = "external_data_sync_audit"
        verbose_name = "外部データ同期監査レコード"
        verbose_name_plural = "外部データ同期監査レコード"

    def __str__(self) -> str:
        return f"[{self.dataset_key}] {self.status} at {self.last_synced_at} ({self.record_count} items)"
