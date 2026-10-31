from django.db import models

from .base import PropertyBaseModel, TransportationMixin


class NomuraModel(PropertyBaseModel, TransportationMixin):
    currentStatus = models.TextField(default="", blank=True)
    hikiwatashi = models.TextField(default="", blank=True)
    torihiki = models.TextField(default="", blank=True)
    biko = models.TextField(blank=True)
    address1 = models.TextField(default="", blank=True)
    address2 = models.TextField(default="", blank=True)
    address3 = models.TextField(default="", blank=True)
    addressKyoto = models.TextField(default="", blank=True)
    updateDate = models.TextField(default="", blank=True)
    nextUpdateDate = models.TextField(default="", blank=True)
    kaisuStr = models.TextField(default="", blank=True)

    class Meta:
        abstract = True

class NomuraMansion(NomuraModel):
    madori = models.TextField(default="", blank=True)
    senyuMensekiStr = models.TextField(default="", blank=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, default=0) # Strict
    balconyMensekiStr = models.TextField(default="", blank=True)
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    saikou = models.TextField(default="", blank=True)
    otherArea = models.TextField(blank=True)
    kouzou = models.TextField(default="", blank=True)
    kaisu = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(default="", blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    soukosuStr = models.TextField(default="", blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    tochikenri = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    kanriKaisya = models.TextField(default="", blank=True)
    kanriKeitai = models.TextField(default="", blank=True)
    manager = models.TextField(default="", blank=True)
    kanrihiStr = models.TextField(default="", blank=True)
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitateStr = models.TextField(default="", blank=True)
    syuzenTsumitate = models.IntegerField(null=True, blank=True)
    otherFees = models.TextField(blank=True)
    tyusyajo = models.TextField(blank=True)

    class Meta:
        db_table = "nomura_mansion"

class NomuraKodate(NomuraModel):
    madori = models.TextField(blank=True, default="")
    tochiMensekiStr = models.TextField(default="", blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    tatemonoMensekiStr = models.TextField(default="", blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    kouzou = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(default="", blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    tyusyajo = models.TextField(blank=True)
    tochikenri = models.TextField(default="", blank=True)
    chimoku = models.TextField(default="", blank=True) # 地目
    privateRoadBurden = models.TextField(blank=True)
    setback = models.TextField(blank=True)
    cityPlanning = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    kenpeiStr = models.TextField(default="", blank=True) # 建ぺい率
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(default="", blank=True) # 容積率
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(default="", blank=True)
    facilities = models.TextField(blank=True)

    class Meta:
        db_table = "nomura_kodate"

class NomuraTochi(NomuraModel):
    tochiMensekiStr = models.TextField(default="", blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    tochikenri = models.TextField(default="", blank=True)
    chimoku = models.TextField(default="", blank=True)
    privateRoadBurden = models.TextField(blank=True)
    setback = models.TextField(blank=True)
    cityPlanning = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    kenpeiStr = models.TextField(default="", blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(default="", blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(default="", blank=True)
    facilities = models.TextField(blank=True)

    # 統一土地評価フィールド
    maguchiStr = models.TextField(default="", blank=True)
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    okuyukiStr = models.TextField(default="", blank=True)
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadWidthStr = models.TextField(default="", blank=True)
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadDirection = models.TextField(default="", blank=True)
    roadType = models.TextField(default="", blank=True)
    roadStructure = models.TextField(default="", blank=True)

    class Meta:
        db_table = "nomura_tochi"


# ========== Investment Kodate & Apartment Models ==========

class NomuraInvestmentKodate(NomuraModel):
    """戸建て賃貸専用モデル"""
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField(blank=True, default="")
    
    # Kodate Specific (Strict)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    kouzou = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(default="", blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    madori = models.TextField(blank=True, default="")
    
    # Land Details
    kenpeiStr = models.TextField(default="", blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(default="", blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(default="", blank=True)
    chimoku = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    tochikenri = models.TextField(default="", blank=True)

    propertyType = models.TextField()  # "Kodate"

    class Meta:
        db_table = "nomura_investment_kodate"


class NomuraInvestmentApartment(NomuraModel):
    """アパート専用モデル"""
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField(blank=True, default="")
    
    # Apartment Specific (Strict)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    kouzou = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(default="", blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    
    # Land Details
    kenpeiStr = models.TextField(default="", blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(default="", blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(default="", blank=True)
    chimoku = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    tochikenri = models.TextField(default="", blank=True)

    propertyType = models.TextField()  # "Apartment"

    class Meta:
        db_table = "nomura_investment_apartment"
