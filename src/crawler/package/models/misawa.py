from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class MisawaCommon(PropertyBaseModel, TransportationMixin):
    # Railway/Station fields are in TransportationMixin.
    tochikenri = models.TextField(blank=True, default="") # 土地権利の種類 (landTenure)
    kenpeiStr = models.TextField(null=True, blank=True, default="")
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True, default="")
    youseki = models.IntegerField(null=True, blank=True)
    youtoChiiki = models.TextField(blank=True, default="") # 用途地域 (zoning)
    deliveryDate = models.TextField(blank=True, default="") # 引渡（入居予定日）
    facilities = models.TextField(blank=True, default="") # 物件設備
    neighborhood = models.TextField(blank=True, default="") # 周辺施設
    schoolDistrict = models.TextField(blank=True, default="") # 学区
    transactionType = models.TextField(blank=True, default="") # 取引態様
    biko = models.TextField(blank=True, default="") # 備考 制限事項
    updatedAt = models.DateField(null=True, blank=True)
    nextUpdateAt = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True

class MisawaMansion(MisawaCommon):
    senyuMensekiStr = models.TextField(default="")
    senyuMenseki = models.DecimalField(max_digits=7, decimal_places=2, default=0)  # Strict: null=False
    balconyMensekiStr = models.TextField(null=True, blank=True, default="")
    balconyMenseki = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, default=0)
    madori = models.TextField()  # Strict: null=False
    kaisu = models.TextField(blank=True, default="") # 所在階 (floor)
    kouzou = models.TextField(blank=True, default="") # 建物構造 (structure)
    chikunengetsuStr = models.TextField(blank=True, default="") # 完成時期 (completionDate)
    soukosu = models.IntegerField(null=True, blank=True) # 総戸数
    kanriKeitai = models.TextField(blank=True, default="") # 管理形態・方式
    kanriKaisya = models.TextField(blank=True, default="") # 管理会社
    kanrihi = models.IntegerField(null=True, blank=True) # 管理費
    syuzenTsumitate = models.IntegerField(null=True, blank=True) # 修繕積立金
    tyusyajo = models.TextField(blank=True, default="") # 駐車場状況/料金

    class Meta:
        db_table = "misawa_mansion"

class MisawaKodate(MisawaCommon):
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # Strict: null=False
    tatemonoMensekiStr = models.TextField(default="")
    tatemonoMenseki = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # Strict: null=False
    madori = models.TextField()
    kouzou = models.TextField(blank=True, default="") # structure
    chikunengetsuStr = models.TextField(blank=True, default="") # completionDate
    kakuninBango = models.TextField(blank=True, default="") # 建築確認番号
    setsudou = models.TextField(blank=True, default="") # 接道状況 (roadCondition)
    privateRoadFee = models.TextField(blank=True, default="") # 私道負担
    setback = models.TextField(blank=True, default="")
    urbanPlanning = models.TextField(blank=True, default="") # 都市計画
    tyusyajo = models.TextField(blank=True, default="") # 駐車場台数

    class Meta:
        db_table = "misawa_kodate"

class MisawaTochi(MisawaCommon):
    """土地専用モデル"""
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    chimoku = models.TextField(blank=True, default="") # landCategory
    setsudou = models.TextField(blank=True, default="") # roadCondition
    buildingCondition = models.TextField(blank=True, default="")
    urbanPlanning = models.TextField(blank=True, default="")
    currentStatus = models.TextField(blank=True, default="")

    class Meta:
        db_table = "misawa_tochi"


# ========== Investment Kodate & Apartment Models ==========


class MisawaInvestmentKodate(MisawaCommon):
    """投資用戸建専用モデル"""
    # Investment Info (Strict)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2)
    annualRent = models.IntegerField()
    monthlyRent = models.IntegerField(null=True, blank=True)
    currentStatus = models.TextField(null=True, blank=True)
    
    # Kodate Specific (Strict)
    tochiMensekiStr = models.TextField(null=True, blank=True)
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2)
    tatemonoMensekiStr = models.TextField(null=True, blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=8, decimal_places=2)
    kouzou = models.TextField(null=True, blank=True)
    chikunengetsuStr = models.TextField(null=True, blank=True)
    
    # Land Details
    kenpeiStr = models.TextField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True)
    setsudou = models.TextField(null=True, blank=True)
    chimoku = models.TextField(null=True, blank=True)
    youtoChiiki = models.TextField(null=True, blank=True)
    tochikenri = models.TextField(null=True, blank=True)

    # Other
    madori = models.TextField(null=True, blank=True)
    propertyType = models.TextField(default="Kodate")

    class Meta:
        db_table = "misawa_investment_kodate"


class MisawaInvestmentApartment(MisawaCommon):
    """アパート専用モデル"""
    # Investment Info (Strict)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2)
    annualRent = models.IntegerField()
    monthlyRent = models.IntegerField(null=True, blank=True)
    currentStatus = models.TextField(null=True, blank=True)
    
    # Apartment Specific (Strict)
    tochiMensekiStr = models.TextField(null=True, blank=True)
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2)
    tatemonoMensekiStr = models.TextField(null=True, blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=8, decimal_places=2)
    kouzou = models.TextField(null=True, blank=True)
    chikunengetsuStr = models.TextField(null=True, blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    
    # Land Details
    kenpeiStr = models.TextField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True)
    setsudou = models.TextField(null=True, blank=True)
    chimoku = models.TextField(null=True, blank=True)
    youtoChiiki = models.TextField(null=True, blank=True)
    tochikenri = models.TextField(null=True, blank=True)

    # Other
    propertyType = models.TextField(default="Apartment")

    class Meta:
        db_table = "misawa_investment_apartment"
