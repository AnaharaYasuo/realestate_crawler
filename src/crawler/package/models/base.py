"""
Base model classes for property data.

This module provides abstract base classes that can be used as templates
for creating new company-specific models. These classes implement common
field patterns like Universal Fields, Transportation Fields, and property
type-specific fields.
"""

from django.db import models
from decimal import Decimal


class PropertyBaseModel(models.Model):
    """
    Abstract base class for all property models.
    
    Implements Universal Fields (8 fields) that are common to all properties
    regardless of company or property type.
    """
    class Meta:
        abstract = True
    
    # Universal Fields (8 fields)
    propertyName = models.TextField(verbose_name="物件名")
    pageUrl = models.CharField(max_length=500, db_index=True, verbose_name="URL")
    inputDate = models.DateField(auto_now_add=True, verbose_name="登録日")
    inputDateTime = models.DateTimeField(auto_now_add=True, verbose_name="登録日時")
    priceStr = models.TextField(verbose_name="価格（文字列）")
    price = models.IntegerField(verbose_name="価格（数値）")
    address = models.TextField(verbose_name="住所")
    traffic = models.TextField(blank=True, null=True, verbose_name="交通")


class TransportationMixin(models.Model):
    """
    Mixin for transportation fields.
    
    Implements Transportation Fields Pattern: 5 routes × 8 fields = 40 fields.
    Each route has: transfer, railway, station, walk minutes (str/int),
    bus station, bus walk minutes (str/int).
    """
    class Meta:
        abstract = True
    
    # Route 1
    transfer1 = models.TextField(blank=True, null=True, verbose_name="乗り換え1")
    railway1 = models.TextField(blank=True, null=True, verbose_name="沿線1")
    station1 = models.TextField(blank=True, null=True, verbose_name="駅1")
    railwayWalkMinute1Str = models.TextField(blank=True, null=True, verbose_name="徒歩分数1（文字列）")
    railwayWalkMinute1 = models.IntegerField(blank=True, null=True, verbose_name="徒歩分数1（数値）")
    busStation1 = models.TextField(blank=True, null=True, verbose_name="バス停1")
    busWalkMinute1Str = models.TextField(blank=True, null=True, verbose_name="バス徒歩分数1（文字列）")
    busWalkMinute1 = models.IntegerField(blank=True, null=True, verbose_name="バス徒歩分数1（数値）")
    
    # Route 2
    transfer2 = models.TextField(blank=True, null=True, verbose_name="乗り換え2")
    railway2 = models.TextField(blank=True, null=True, verbose_name="沿線2")
    station2 = models.TextField(blank=True, null=True, verbose_name="駅2")
    railwayWalkMinute2Str = models.TextField(blank=True, null=True, verbose_name="徒歩分数2（文字列）")
    railwayWalkMinute2 = models.IntegerField(blank=True, null=True, verbose_name="徒歩分数2（数値）")
    busStation2 = models.TextField(blank=True, null=True, verbose_name="バス停2")
    busWalkMinute2Str = models.TextField(blank=True, null=True, verbose_name="バス徒歩分数2（文字列）")
    busWalkMinute2 = models.IntegerField(blank=True, null=True, verbose_name="バス徒歩分数2（数値）")
    
    # Route 3
    transfer3 = models.TextField(blank=True, null=True, verbose_name="乗り換え3")
    railway3 = models.TextField(blank=True, null=True, verbose_name="沿線3")
    station3 = models.TextField(blank=True, null=True, verbose_name="駅3")
    railwayWalkMinute3Str = models.TextField(blank=True, null=True, verbose_name="徒歩分数3（文字列）")
    railwayWalkMinute3 = models.IntegerField(blank=True, null=True, verbose_name="徒歩分数3（数値）")
    busStation3 = models.TextField(blank=True, null=True, verbose_name="バス停3")
    busWalkMinute3Str = models.TextField(blank=True, null=True, verbose_name="バス徒歩分数3（文字列）")
    busWalkMinute3 = models.IntegerField(blank=True, null=True, verbose_name="バス徒歩分数3（数値）")
    
    # Route 4
    transfer4 = models.TextField(blank=True, null=True, verbose_name="乗り換え4")
    railway4 = models.TextField(blank=True, null=True, verbose_name="沿線4")
    station4 = models.TextField(blank=True, null=True, verbose_name="駅4")
    railwayWalkMinute4Str = models.TextField(blank=True, null=True, verbose_name="徒歩分数4（文字列）")
    railwayWalkMinute4 = models.IntegerField(blank=True, null=True, verbose_name="徒歩分数4（数値）")
    busStation4 = models.TextField(blank=True, null=True, verbose_name="バス停4")
    busWalkMinute4Str = models.TextField(blank=True, null=True, verbose_name="バス徒歩分数4（文字列）")
    busWalkMinute4 = models.IntegerField(blank=True, null=True, verbose_name="バス徒歩分数4（数値）")
    
    # Route 5
    transfer5 = models.TextField(blank=True, null=True, verbose_name="乗り換え5")
    railway5 = models.TextField(blank=True, null=True, verbose_name="沿線5")
    station5 = models.TextField(blank=True, null=True, verbose_name="駅5")
    railwayWalkMinute5Str = models.TextField(blank=True, null=True, verbose_name="徒歩分数5（文字列）")
    railwayWalkMinute5 = models.IntegerField(blank=True, null=True, verbose_name="徒歩分数5（数値）")
    busStation5 = models.TextField(blank=True, null=True, verbose_name="バス停5")
    busWalkMinute5Str = models.TextField(blank=True, null=True, verbose_name="バス徒歩分数5（文字列）")
    busWalkMinute5 = models.IntegerField(blank=True, null=True, verbose_name="バス徒歩分数5（数値）")
    
    # Metadata
    railwayCount = models.IntegerField(blank=True, null=True, verbose_name="沿線数")
    busUse1 = models.IntegerField(blank=True, null=True, verbose_name="バス利用フラグ1")
    busUse2 = models.IntegerField(blank=True, null=True, verbose_name="バス利用フラグ2")
    busUse3 = models.IntegerField(blank=True, null=True, verbose_name="バス利用フラグ3")
    busUse4 = models.IntegerField(blank=True, null=True, verbose_name="バス利用フラグ4")
    busUse5 = models.IntegerField(blank=True, null=True, verbose_name="バス利用フラグ5")


class MansionBaseModel(PropertyBaseModel, TransportationMixin):
    """
    Abstract base class for mansion (condominium) properties.
    
    Includes common fields for mansion properties using Dual Storage Pattern.
    """
    class Meta:
        abstract = True
    
    # Dual Storage Pattern fields
    senyuMensekiStr = models.TextField(blank=True, null=True, verbose_name="専有面積（文字列）")
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="専有面積（数値）")
    
    chikunengetsuStr = models.TextField(blank=True, null=True, verbose_name="築年月（文字列）")
    chikunengetsu = models.DateField(blank=True, null=True, verbose_name="築年月（日付）")
    
    kanrihiStr = models.TextField(blank=True, null=True, verbose_name="管理費（文字列）")
    kanrihi = models.IntegerField(blank=True, null=True, verbose_name="管理費（数値）")
    
    syuzenTsumitateStr = models.TextField(blank=True, null=True, verbose_name="修繕積立金（文字列）")
    syuzenTsumitate = models.IntegerField(blank=True, null=True, verbose_name="修繕積立金（数値）")
    
    # Mansion-specific fields
    madori = models.TextField(blank=True, null=True, verbose_name="間取り")
    balconyMensekiStr = models.TextField(blank=True, null=True, verbose_name="バルコニー面積（文字列）")
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="バルコニー面積（数値）")
    kaisu = models.TextField(blank=True, null=True, verbose_name="所在階")


class KodateBaseModel(PropertyBaseModel, TransportationMixin):
    """
    Abstract base class for kodate (detached house) properties.
    
    Includes common fields for kodate properties using Dual Storage Pattern.
    """
    class Meta:
        abstract = True
    
    # Dual Storage Pattern fields
    tochiMensekiStr = models.TextField(blank=True, null=True, verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="土地面積（数値）")
    
    tatemonoMensekiStr = models.TextField(blank=True, null=True, verbose_name="建物面積（文字列）")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="建物面積（数値）")
    
    chikunengetsuStr = models.TextField(blank=True, null=True, verbose_name="築年月（文字列）")
    chikunengetsu = models.DateField(blank=True, null=True, verbose_name="築年月（日付）")
    
    # Kodate-specific fields
    madori = models.TextField(blank=True, null=True, verbose_name="間取り")
    kouzou = models.TextField(blank=True, null=True, verbose_name="構造")


class TochiBaseModel(PropertyBaseModel, TransportationMixin):
    """
    Abstract base class for tochi (land) properties.
    
    Includes common fields for tochi properties using Dual Storage Pattern.
    """
    class Meta:
        abstract = True
    
    # Dual Storage Pattern fields
    tochiMensekiStr = models.TextField(blank=True, null=True, verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name="土地面積（数値）")
    
    # Tochi-specific fields
    youtoChiiki = models.TextField(blank=True, null=True, verbose_name="用途地域")
    kenpei = models.TextField(blank=True, null=True, verbose_name="建ぺい率")
    youseki = models.TextField(blank=True, null=True, verbose_name="容積率")
