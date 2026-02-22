from django.db import models
from .base import PropertyBaseModel, TransportationMixin

# Create your models here.

class SumifuModel(PropertyBaseModel, TransportationMixin):
    # Sumifu Specific Fields
    hikiwatashi = models.TextField()
    genkyo = models.TextField()
    tochikenri = models.TextField()
    torihiki  = models.TextField()
    biko  = models.TextField(blank=True)

    address1 = models.TextField(null=True, blank=True)
    address2 = models.TextField(null=True, blank=True)
    address3 = models.TextField(null=True, blank=True)
    addressKyoto = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True
        
class SumifuInvestmentKodate(SumifuModel):
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField() # Strict
    
    # Location
    
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Strict
    tatemonoMensekiStr = models.TextField(default="")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Strict
    
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    
    kenpeiStr = models.TextField(null=True, blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(null=True, blank=True)
    chimoku = models.TextField(null=True, blank=True)
    youtoChiiki = models.TextField(null=True, blank=True)
    tochikenri = models.TextField()
    
    # Extra fields for flexibility if needed, but keeping main ones strict
    propertyType = models.TextField() # To store "Kodate" explicitly
    
    # Inherits:
    # propertyName, pageUrl, inputDate, inputDateTime, priceStr, price, address, etc.

    class Meta:
        db_table = "sumifu_investment_kodate"

class SumifuInvestmentApartment(SumifuModel):
    # Investment Info (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField() # Strict
    
    # Location
    
    tochiMensekiStr = models.TextField(default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Strict
    tatemonoMensekiStr = models.TextField(default="")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, default=0) # Strict
    
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    soukosuStr = models.TextField(null=True, blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    kaisu = models.IntegerField(null=True, blank=True)
    kaisuStr = models.TextField(null=True, blank=True)
    
    # Land Details
    kenpeiStr = models.TextField(null=True, blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    yousekiStr = models.TextField(null=True, blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    setsudou = models.TextField(null=True, blank=True)
    chimoku = models.TextField(null=True, blank=True)
    youtoChiiki = models.TextField(null=True, blank=True)
    tochikenri = models.TextField()

    propertyType = models.TextField() # To store "Apartment" explicitly

    class Meta:
        db_table = "sumifu_investment_apartment"

class SumifuMansion(SumifuModel):
    madori = models.TextField()
    senyuMensekiStr = models.TextField()
    senyuMenseki = models.DecimalField(max_digits=8, decimal_places=3) # Strict
    # kaisu = models.TextField() # Removed, defined as IntegerField below
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)

    balconyMensekiStr = models.TextField()
    saikouKadobeya = models.TextField()
    saikou = models.TextField()
    kadobeya = models.TextField()
    soukosuStr = models.TextField()
    soukosu = models.IntegerField(null=True)
    kanriKeitaiKaisya = models.TextField()
    kanriKeitai = models.TextField()
    kanriKaisya = models.TextField()
    kanrihiStr = models.TextField()
    kanrihi = models.IntegerField(null=True)
    syuzenTsumitateStr = models.TextField()
    syuzenTsumitate = models.IntegerField(null=True)
    tyusyajo = models.TextField(blank=True)
    #追加項目
    kaisuKouzou = models.TextField(null=True, blank=True) # Added for combined structure/floor label
    kaisu = models.IntegerField(null=True, blank=True) # Floor number (e.g. 5)
    kaisuStr = models.TextField(null=True, blank=True) # Building height or raw string (e.g. 地上15階建)
    
    kouzou  = models.TextField()
    sonotaHiyouStr  = models.TextField(blank=True)
    bunjoKaisya  = models.TextField(blank=True)
    sekouKaisya  = models.TextField(blank=True)

    floorType_kai = models.IntegerField(null=True, blank=True)
    floorType_chijo = models.IntegerField(null=True, blank=True)
    floorType_chika = models.IntegerField(null=True, blank=True)
    floorType_kouzou = models.TextField(null=True)
    kyutaishin = models.IntegerField(null=True, blank=True)

    balconyMenseki = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    senyouNiwaMenseki = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    roofBarukoniMenseki = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    kanrihi_p_heibei = models.DecimalField(max_digits=7,decimal_places=3, null=True, blank=True)
    syuzenTsumitate_p_heibei = models.DecimalField(max_digits=7,decimal_places=3, null=True, blank=True)

    class Meta:
        db_table = "sumifu_mansion"
        abstract = False

class SumifuTochi(SumifuModel):
    tochiMensekiStr = models.TextField()
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3) # Strict
    chimokuChisei = models.TextField()
    chimoku = models.TextField() 
    chisei = models.TextField()
    setsudou = models.TextField(blank=True)
    douro = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)
    douroHaba = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    kenpeiYousekiStr = models.TextField()
    kenpeiStr = models.TextField(blank=True)
    yousekiStr = models.TextField(blank=True)
    kenpei = models.IntegerField(null=True, blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    chiikiChiku = models.TextField(blank=True)
    kuiki = models.TextField()
    youtoChiiki = models.TextField()
    boukaChiiki = models.TextField()
    saikenchiku = models.TextField()
    sonotaChiiki = models.TextField()
    kenchikuJoken = models.TextField()
    kokudoHou = models.TextField()

    class Meta:
        db_table = "sumifu_tochi"
        abstract = False    

class SumifuKodate(SumifuModel):
    tochiMensekiStr = models.TextField()
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3) # Strict
    tatemonoMensekiStr = models.TextField()
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3) # Strict
    madori = models.TextField() # Strict
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField(null=True)
    kaisuKouzou  = models.TextField()
    kaisu  = models.TextField(blank=True)
    kouzou  = models.TextField(blank=True)
    chimokuChisei = models.TextField()
    chimoku = models.TextField()
    chisei = models.TextField()
    setsudou = models.TextField(blank=True)
    douro = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)
    douroHaba = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=6,decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True)
    yousekiStr = models.TextField(blank=True)
    kenpeiYousekiStr = models.TextField()
    kenpei = models.IntegerField(null=True, blank=True)
    youseki = models.IntegerField(null=True, blank=True)
    chiikiChiku = models.TextField()

    kuiki = models.TextField()
    youtoChiiki = models.TextField()
    boukaChiiki = models.TextField()
    saikenchiku = models.TextField()
    sonotaChiiki = models.TextField()
    tyusyajo = models.TextField(blank=True)
    kokudoHou = models.TextField()
    kaisuStr = models.TextField(null=True, blank=True)
    kaisu = models.IntegerField(null=True, blank=True) # Total stories (e.g. 2)

    class Meta:
        db_table = "sumifu_kodate"
        abstract = False
