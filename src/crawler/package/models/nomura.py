from django.db import models
from .base import PropertyBaseModel, TransportationMixin


class NomuraModel(PropertyBaseModel, TransportationMixin):
    pass
    # address and traffic are in PropertyBaseModel
    # But wait, NomuraModel had traffic not in Mixin? PropertyBaseModel has traffic.
    # So traffic is covered.
    
    currentStatus = models.TextField()
    hikiwatashi = models.TextField()
    torihiki = models.TextField()
    biko = models.TextField(blank=True)
    address1 = models.TextField(null=True, blank=True)
    address2 = models.TextField(null=True, blank=True)
    address3 = models.TextField(null=True, blank=True)
    addressKyoto = models.TextField(null=True, blank=True)
    updateDate = models.TextField()
    nextUpdateDate = models.TextField()
    kaisuStr = models.TextField(null=True)

    class Meta:
        abstract = True

class NomuraMansion(NomuraModel):
    madori = models.TextField()
    senyuMensekiStr = models.TextField(default="")
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, default=0) # Strict
    balconyMensekiStr = models.TextField()
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    saikou = models.TextField()
    otherArea = models.TextField(blank=True)
    kouzou = models.TextField()
    kaisu = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    soukosuStr = models.TextField()
    soukosu = models.IntegerField(null=True)
    tochikenri = models.TextField()
    youtoChiiki = models.TextField()
    kanriKaisya = models.TextField()
    kanriKeitai = models.TextField()
    manager = models.TextField()
    kanrihiStr = models.TextField()
    kanrihi = models.IntegerField(null=True)
    syuzenTsumitateStr = models.TextField()
    syuzenTsumitate = models.IntegerField(null=True)
    otherFees = models.TextField(blank=True)
    tyusyajo = models.TextField(blank=True)

    class Meta:
        db_table = "nomura_mansion"

class NomuraKodate(NomuraModel):
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, default=0)
    tatemonoMensekiStr = models.TextField(default="")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, default=0)
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    tyusyajo = models.TextField(blank=True)
    tochikenri = models.TextField()
    chimoku = models.TextField() # 地目
    privateRoadBurden = models.TextField(blank=True)
    setback = models.TextField(blank=True)
    cityPlanning = models.TextField()
    youtoChiiki = models.TextField()
    kenpeiStr = models.TextField(default="") # 建ぺい率
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(default="") # 容積率
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField()
    facilities = models.TextField(blank=True)

    class Meta:
        db_table = "nomura_kodate"

class NomuraTochi(NomuraModel):
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, default=0)
    tochikenri = models.TextField()
    chimoku = models.TextField()
    privateRoadBurden = models.TextField(blank=True)
    setback = models.TextField(blank=True)
    cityPlanning = models.TextField()
    youtoChiiki = models.TextField()
    kenpeiStr = models.TextField(default="")
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(default="")
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField()
    facilities = models.TextField(blank=True)

    class Meta:
        db_table = "nomura_tochi"


# ========== Investment Kodate & Apartment Models ==========

class NomuraInvestmentKodate(NomuraModel):
    """戸建て賃貸専用モデル"""
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField() # Strict (Override base to strict if needed, validation handles it)
    
    # Kodate Specific (Strict)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    
    # Land Details
    kenpeiStr = models.TextField(null=True, blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(null=True, blank=True)
    chimoku = models.TextField(null=True, blank=True)
    youtoChiiki = models.TextField(null=True, blank=True)
    tochikenri = models.TextField(null=True, blank=True)

    propertyType = models.TextField()  # "Kodate"

    class Meta:
        db_table = "nomura_investment_kodate"


class NomuraInvestmentApartment(NomuraModel):
    """アパート専用モデル"""
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField() # Strict
    
    # Apartment Specific (Strict)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2)  # Strict
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    soukosu = models.IntegerField(null=True)
    
    # Land Details
    kenpeiStr = models.TextField(null=True, blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(null=True, blank=True)
    chimoku = models.TextField(null=True, blank=True)
    youtoChiiki = models.TextField(null=True, blank=True)
    tochikenri = models.TextField(null=True, blank=True)

    propertyType = models.TextField()  # "Apartment"

    class Meta:
        db_table = "nomura_investment_apartment"

