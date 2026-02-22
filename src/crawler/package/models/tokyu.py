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
    # inputDate/Time/Price strictness handled by Base (or overridden if needed stricter)
    # Actually Base has null=True for flexibility in migration, but schema says Strict.
    # We will assume Base definitions are flexible, but logic enforces validation.
    # However, to match schema strictness we should change Base to null=False?
    # Existing TokyuMansion had some null=False (implicit) for inputDate.
    # Let's keep them generally simple.
    
    madori = models.TextField()
    senyuMensekiStr = models.TextField()
    senyuMenseki = models.DecimalField(max_digits=8, decimal_places=3)
    kaisu = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    
    kanrihiStr = models.TextField()
    kanrihi = models.IntegerField(null=True)
    syuzenTsumitateStr = models.TextField()
    syuzenTsumitate = models.IntegerField(null=True)
    sonotaHiyouStr = models.TextField(blank=True)
    balconyMensekiStr = models.TextField()
    balconyMenseki = models.DecimalField(max_digits=8,decimal_places=3, null=True)
    saikou = models.TextField()
    kaisuStr = models.TextField()
    tatemonoKaisu  = models.TextField()
    kouzou  = models.TextField()
    soukosu  = models.TextField()
    bunjoKaisya  = models.TextField(blank=True)
    sekouKaisya  = models.TextField(blank=True)
    kanriKaisya  = models.TextField(blank=True)
    kanriKeitai  = models.TextField()
    
    tyusyajo  = models.TextField(blank=True)
    saikou = models.TextField(verbose_name="向き", default="")
    soukosu = models.IntegerField(verbose_name="総戸数", null=True, blank=True)
    bikeokiba  = models.TextField(blank=True)
    isSoldout = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "tokyu_mansion"


class TokyuTochi(TokyuModel):
    tochiMensekiStr = models.TextField()
    tochiMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    chimokuChisei = models.TextField()
    chimoku = models.TextField()
    chisei = models.TextField()
    setsudou = models.TextField()
    douro = models.TextField()
    douroMuki = models.TextField()
    douroHaba = models.DecimalField(max_digits=6,decimal_places=3, null=True)
    douroKubun = models.TextField()
    setsumen = models.DecimalField(max_digits=6,decimal_places=3, null=True)
    tochiMensekiStr = models.TextField(verbose_name="土地面積", default="")
    kenpei = models.IntegerField(verbose_name="建ぺい率", default=0)
    youseki = models.IntegerField(verbose_name="容積率", default=0)
    kenpeiStr = models.TextField(verbose_name="建ぺい率（文字列）", default="")
    yousekiStr = models.TextField(verbose_name="容積率（文字列）", default="")
    kenpeiYousekiStr = models.TextField(verbose_name="建ぺい率・容積率", default="")
    chiikiChiku = models.TextField()
    kuiki = models.TextField()
    youtoChiiki = models.TextField()
    boukaChiiki = models.TextField()
    saikenchiku = models.TextField()
    sonotaChiiki = models.TextField()
    kenchikuJoken = models.TextField()
    kokudoHou = models.TextField()
    
    sonotaHiyouStr  = models.TextField(blank=True)
    bunjoKaisya  = models.TextField(blank=True)
    sekouKaisya  = models.TextField(blank=True)

    class Meta:
        db_table = "tokyu_tochi"


class TokyuKodate(TokyuModel):
    madori = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    
    tochiMensekiStr = models.TextField()
    tochiMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    shidoMensekiStr = models.TextField()
    shidoMenseki = models.DecimalField(max_digits=8,decimal_places=3, null=True)
    kenpeiYousekiStr = models.TextField(default='')
    tatemonoMensekiStr = models.TextField()
    tatemonoMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    kouzou  = models.TextField()
    saikou = models.TextField(verbose_name="向き", default="")
    kaisuStr = models.TextField(verbose_name="階数（地上）", null=True, blank=True)

    setsumen  = models.TextField()
    douroHaba  = models.TextField()
    youtoChiiki = models.TextField()
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="建ぺい率（数値）", default=0)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="容積率（数値）", default=0)
    kenpeiStr = models.TextField(verbose_name="建ぺい率（文字列）", default="")
    yousekiStr = models.TextField(verbose_name="容積率（文字列）", default="")
    kenpeiYousekiStr = models.TextField(verbose_name="建ぺい率・容積率", default="")
    tyusyajo  = models.TextField(blank=True)
    setsudou = models.TextField()
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
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # 土地面積
    tatemonoMensekiStr = models.TextField(default="")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # 建物面積/専有面積
    kouzou = models.TextField() 
    kaisuStr = models.TextField(null=True, blank=True) 
    chikunengetsuStr = models.TextField() 
    
    # Detailed Specs removed: soukosu, floorPlan, balconyArea, kanrihi, syuzenTsumitate
    # These are condominium-specific fields not applicable to one-building properties 
    
    # Land Specific Details
    kenpeiStr = models.TextField(null=True, blank=True, default="")
    kenpei = models.IntegerField(null=True, blank=True) 
    yousekiStr = models.TextField(null=True, blank=True, default="")
    youseki = models.IntegerField(null=True, blank=True) 
    youtoChiiki = models.TextField(null=True, blank=True) 
    startRoad = models.TextField(null=True, blank=True) 
    tochikenri = models.TextField(null=True, blank=True) 

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
    kaisuStr = models.TextField(null=True, blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    soukosuStr = models.TextField(null=True, default="", blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    
    # Costs (Strict for Apartment)
    # kanrihi/syuzenTsumitate removed per user request (not applicable for Tokyu Apartments)
    
    # Land Details
    kenpeiStr = models.TextField(null=True, blank=True, default="")
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True, default="")
    youseki = models.IntegerField(null=True, blank=True)
    youtoChiiki = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    setsudou = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    
    propertyType = models.TextField()  # "Apartment"

    class Meta:
        db_table = "tokyu_investment_apartment"

        