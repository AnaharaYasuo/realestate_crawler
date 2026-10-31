from django.db import models

from .base import PropertyBaseModel, TransportationMixin

# Create your models here.



class TokyuModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True)
    genkyo = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    torihiki  = models.TextField(blank=True)
    biko  = models.TextField(blank=True)
    
    # Common Address fields (auxiliary/derived)
    address1 = models.TextField(blank=True)
    address2 = models.TextField(blank=True)
    address3 = models.TextField(blank=True)
    addressKyoto = models.TextField(blank=True)

    class Meta:
        abstract = True

class TokyuMansion(TokyuModel):
    madori = models.TextField(default="", blank=True)
    senyuMensekiStr = models.TextField(default="", blank=True)
    senyuMenseki = models.DecimalField(max_digits=8, decimal_places=3)
    kaisu = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(default="", blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    
    kanrihiStr = models.TextField(default="", blank=True)
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitateStr = models.TextField(default="", blank=True)
    syuzenTsumitate = models.IntegerField(null=True, blank=True)
    sonotaHiyouStr = models.TextField(blank=True)
    balconyMensekiStr = models.TextField(default="", blank=True)
    balconyMenseki = models.DecimalField(max_digits=8,decimal_places=3, null=True, blank=True)
    kaisuStr = models.TextField(default="", blank=True)
    tatemonoKaisu  = models.TextField(default="", blank=True)
    kouzou  = models.TextField(default="", blank=True)
    bunjoKaisya  = models.TextField(blank=True)
    sekouKaisya  = models.TextField(blank=True)
    kanriKaisya  = models.TextField(blank=True)
    kanriKeitai  = models.TextField(default="", blank=True)
    
    tyusyajo  = models.TextField(blank=True)
    saikou = models.TextField(verbose_name="向き", default="", blank=True)
    soukosu = models.IntegerField(verbose_name="総戸数", null=True, blank=True)
    bikeokiba  = models.TextField(blank=True)
    isSoldout = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "tokyu_mansion"


class TokyuTochi(TokyuModel):
    tochiMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    chimokuChisei = models.TextField(default="", blank=True)
    chimoku = models.TextField(default="")
    chisei = models.TextField(blank=True)
    setsudou = models.TextField(default="", blank=True)
    douro = models.TextField(default="", blank=True)
    douroMuki = models.TextField(default="", blank=True)
    douroHaba = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(default="", blank=True)
    setsumen = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    tochiMensekiStr = models.TextField(verbose_name="土地面積", default="", blank=True)
    kenpei = models.IntegerField(verbose_name="建ぺい率", default=0)
    youseki = models.IntegerField(verbose_name="容積率", default=0)
    kenpeiStr = models.TextField(verbose_name="建ぺい率（文字列）", default="", blank=True)
    yousekiStr = models.TextField(verbose_name="容積率（文字列）", default="", blank=True)
    kenpeiYousekiStr = models.TextField(verbose_name="建ぺい率・容積率", default="", blank=True)
    chiikiChiku = models.TextField(default="", blank=True)
    kuiki = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    boukaChiiki = models.TextField(blank=True)
    saikenchiku = models.TextField(blank=True)
    sonotaChiiki = models.TextField(blank=True)
    kenchikuJoken = models.TextField(default="", blank=True)
    kokudoHou = models.TextField(blank=True)
    
    sonotaHiyouStr  = models.TextField(blank=True)
    bunjoKaisya  = models.TextField(blank=True)
    sekouKaisya  = models.TextField(blank=True)

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
        db_table = "tokyu_tochi"


class TokyuKodate(TokyuModel):
    madori = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(default="", blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    
    tochiMensekiStr = models.TextField(default="", blank=True)
    tochiMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    shidoMensekiStr = models.TextField(default="", blank=True)
    shidoMenseki = models.DecimalField(max_digits=8,decimal_places=3, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(default="", blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    kouzou  = models.TextField(default="", blank=True)
    saikou = models.TextField(verbose_name="向き", default="", blank=True)
    kaisuStr = models.TextField(verbose_name="階数（地上）", default="", blank=True)

    setsumen  = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    douroHaba  = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="建ぺい率（数値）", default=0)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="容積率（数値）", default=0)
    kenpeiStr = models.TextField(verbose_name="建ぺい率（文字列）", default="", blank=True)
    yousekiStr = models.TextField(verbose_name="容積率（文字列）", default="", blank=True)
    kenpeiYousekiStr = models.TextField(verbose_name="建ぺい率・容積率", default="", blank=True)
    tyusyajo  = models.TextField(blank=True)
    setsudou = models.TextField(default="", blank=True)
    isSoldout = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "tokyu_kodate"


class TokyuInvestmentKodate(TokyuModel):
    # Investment Info
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # 表面利回り
    annualRent = models.IntegerField() # 満室時想定年収
    currentStatus = models.TextField() # 現況 (賃貸中 etc)
    
    # Property Type & Location
    propertyType = models.TextField() 
    
    # Building / Land Details
    tochiMensekiStr = models.TextField(default="", blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # 土地面積
    tatemonoMensekiStr = models.TextField(default="", blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # 建物面積/専有面積
    kouzou = models.TextField(default="", blank=True) 
    kaisuStr = models.TextField(default="", blank=True) 
    chikunengetsuStr = models.TextField(default="", blank=True) 
    
    # Land Specific Details
    kenpeiStr = models.TextField(blank=True, default="")
    kenpei = models.IntegerField(null=True, blank=True) 
    yousekiStr = models.TextField(blank=True, default="")
    youseki = models.IntegerField(null=True, blank=True) 
    youtoChiiki = models.TextField(default="", blank=True) 
    startRoad = models.TextField(default="", blank=True) 
    tochikenri = models.TextField(default="", blank=True) 

    class Meta:
        db_table = "tokyu_investment_kodate"


class TokyuInvestmentApartment(TokyuModel):
    """アパート専用モデル"""
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # Strict -> Relaxed
    annualRent = models.IntegerField(null=True, blank=True) # Strict -> Relaxed
    monthlyRent = models.IntegerField(null=True, blank=True) # Strict -> Relaxed
    currentStatus = models.TextField(blank=True) # Strict -> Relaxed
    
    # Location
    
    # Apartment Specific (Strict)
    tochiMensekiStr = models.TextField(default="", blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)  # Strict -> Relaxed
    tatemonoMensekiStr = models.TextField(default="", blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)  # Strict -> Relaxed
    kouzou = models.TextField(blank=True)
    kaisuStr = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    soukosuStr = models.TextField(default="", blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    
    # Land Details
    kenpeiStr = models.TextField(blank=True, default="")
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(blank=True, default="")
    youseki = models.IntegerField(null=True, blank=True)
    youtoChiiki = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    setsudou = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    
    propertyType = models.TextField()  # "Apartment"

    class Meta:
        db_table = "tokyu_investment_apartment"
