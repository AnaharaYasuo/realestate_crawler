# -*- coding: utf-8 -*-
"""
建物マスタ (BuildingMaster) モデル
同一マンション・アパートの共用部・構造・分譲主・施工会社・管理体制スペックを永続化・集約する。
"""
from django.db import models


class BuildingMaster(models.Model):
    """
    建物マスタ
    マンション等の棟単位スペックを保持し、同一棟の全住戸へスペックを自動伝搬させる。
    """
    normalized_name = models.CharField(max_length=255, db_index=True, verbose_name="正規化建物名")
    raw_name = models.TextField(verbose_name="原本建物名")
    normalized_address = models.CharField(max_length=255, db_index=True, verbose_name="正規化住所(町丁目)")
    raw_address = models.TextField(verbose_name="原本所在地")

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="緯度")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="経度")

    developer_brand = models.CharField(max_length=150, blank=True, default="", verbose_name="旧分譲主・ブランド名")
    developer_tier = models.CharField(max_length=30, default="unknown", verbose_name="デベロッパー格付け")
    contractor_name = models.CharField(max_length=150, blank=True, default="", verbose_name="施工会社")
    contractor_tier = models.CharField(max_length=30, default="unknown", verbose_name="ゼネコン格付け")

    structure_type = models.CharField(max_length=50, blank=True, default="", verbose_name="建物構造")
    earthquake_resistance = models.CharField(max_length=30, blank=True, default="", verbose_name="耐震性能")

    total_units = models.IntegerField(null=True, blank=True, verbose_name="総戸数")
    total_floors = models.IntegerField(null=True, blank=True, verbose_name="地上総階数")
    built_year = models.IntegerField(null=True, blank=True, verbose_name="建築年")
    built_month = models.IntegerField(null=True, blank=True, verbose_name="建築月")

    elevator_available = models.BooleanField(null=True, blank=True, verbose_name="エレベーター有無")
    elevator_count = models.IntegerField(null=True, blank=True, verbose_name="エレベーター基数")
    hallway_type = models.CharField(max_length=20, blank=True, default="", verbose_name="共用廊下(内廊下/外廊下)")
    garbage_disposal_24h = models.BooleanField(null=True, blank=True, verbose_name="24時間ゴミ出し可否")

    management_company = models.CharField(max_length=150, blank=True, default="", verbose_name="管理会社名")
    management_type = models.CharField(max_length=50, blank=True, default="", verbose_name="管理形態")
    manager_working_style = models.CharField(max_length=50, blank=True, default="", verbose_name="管理員勤務形態")
    repair_reserve_score = models.FloatField(null=True, blank=True, verbose_name="修繕積立金・管理組合健全性スコア")

    shared_facilities_json = models.TextField(blank=True, default="", verbose_name="共用施設リストJSON")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        db_table = "building_master"
        unique_together = ("normalized_name", "normalized_address")
        verbose_name = "建物マスタ"
        verbose_name_plural = "建物マスタ"

    def __str__(self):
        return f"{self.normalized_name} ({self.normalized_address})"
