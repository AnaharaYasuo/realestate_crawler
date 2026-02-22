# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

# Create your models here.



class MitsuiModel(PropertyBaseModel, TransportationMixin):
    address1 = models.TextField(null=True, blank=True)
    address2 = models.TextField(null=True, blank=True)
    address3 = models.TextField(null=True, blank=True)
    addressKyoto = models.TextField(null=True, blank=True)

    hikiwatashi = models.TextField(blank=True)
    genkyo = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    torihiki  = models.TextField(blank=True)
    biko  = models.TextField(blank=True)

    class Meta:
        abstract = True

class MitsuiMansion(MitsuiModel):
    # unique_id = models.CharField(max_length=100, null=True)
    madori = models.TextField(blank=True)
    senyuMensekiStr = models.TextField(blank=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kaisuStr = models.TextField(null=True, blank=True)

    chikunengetsuStr = models.TextField(blank=True)
    chikunengetsu = models.DateField(null=True)

    balconyMensekiStr = models.TextField(blank=True)
    saikouKadobeya = models.TextField(blank=True)
    saikou = models.TextField(blank=True)
    kadobeya = models.TextField(blank=True)
    soukosuStr = models.TextField(blank=True)
    soukosu = models.IntegerField(null=True)
    kanriKeitaiKaisya = models.TextField(blank=True)
    kanriKeitai = models.TextField(blank=True)
    kanriKaisya = models.TextField(blank=True)
    kanrihiStr = models.TextField(blank=True)
    kanrihi = models.IntegerField(null=True)
    syuzenTsumitateStr = models.TextField(blank=True)
    syuzenTsumitate = models.IntegerField(null=True)
    tyusyajo = models.TextField(blank=True)
    #追加項目
    kouzou  = models.TextField(blank=True)
    sonotaHiyouStr  = models.TextField(blank=True)
    bunjoKaisya  = models.TextField(blank=True)
    sekouKaisya  = models.TextField(blank=True)

    floorType_kai = models.IntegerField(null=True)
    floorType_chijo = models.IntegerField(null=True)
    floorType_chika = models.IntegerField(null=True)
    floorType_kouzou = models.TextField(blank=True)
    kyutaishin = models.IntegerField(null=True)
    balconyMenseki = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)
    senyouNiwaMenseki = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)
    roofBarukoniMenseki = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)
    kanrihi_p_heibei = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)
    syuzenTsumitate_p_heibei = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)

    class Meta:
        db_table = "mitsui_mansion"

        
class MitsuiTochi(MitsuiModel):
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kenchikuJoken = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kenpeiStr = models.TextField(blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    yousekiStr = models.TextField(blank=True)

    youtoChiiki = models.TextField(blank=True)
    kuiki = models.TextField(blank=True)
    kokudoHou = models.TextField(blank=True)
    
    sonotaHiyouStr = models.TextField(blank=True)

    setsudou = models.TextField()
    douroMuki = models.TextField()
    douroHaba = models.DecimalField(max_digits=10,decimal_places=3, null=True)
    douroKubun = models.TextField()
    setsumen = models.DecimalField(max_digits=10,decimal_places=3, null=True)

    class Meta:
        db_table = "mitsui_tochi"

        
class MitsuiKodate(MitsuiModel):
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    tatemonoMensekiStr = models.TextField(blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    
    kaisuKouzou  = models.TextField(blank=True)
    kaisu  = models.TextField(blank=True)
    kaisuStr = models.TextField(null=True, blank=True)
    kouzou  = models.TextField(blank=True)

    tyusyajo = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kenpeiStr = models.TextField(blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    yousekiStr = models.TextField(blank=True)

    youtoChiiki = models.TextField(blank=True)
    kuiki = models.TextField(blank=True)

    setsudou = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)
    douroHaba = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=10,decimal_places=3, null=True, blank=True)
    sonotaHiyouStr = models.TextField(blank=True)

    class Meta:
        db_table = "mitsui_kodate"


class MitsuiInvestmentKodate(MitsuiModel):
    # Transportation (Strict - at least railway1)
    
    # Investment specific (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField() # Strict
    
    # Common specs
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField()
    
    # Areas (Strict for Kodate)
    tochiMensekiStr = models.TextField(null=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2) # Strict
    tatemonoMensekiStr = models.TextField(null=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2) # Strict
    
    # Land Details
    setsudou = models.TextField(null=True)
    chimoku = models.TextField(null=True)
    youtoChiiki = models.TextField(null=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kenpeiStr = models.TextField(null=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    yousekiStr = models.TextField(null=True)
    kaisuStr = models.TextField(null=True)
    
    propertyType = models.TextField() # "Kodate"

    class Meta:
        db_table = "mitsui_investment_kodate"
        
class MitsuiInvestmentApartment(MitsuiModel):
    # Transportation
    
    # Investment specific (Mandatory)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2) # Strict
    annualRent = models.IntegerField() # Strict
    monthlyRent = models.IntegerField() # Strict
    currentStatus = models.TextField() # Strict
    
    # Common specs
    kouzou = models.TextField()
    chikunengetsuStr = models.TextField() # Strict
    soukosuStr = models.TextField(null=True)
    soukosu = models.IntegerField(null=True)
    kaisuStr = models.TextField(null=True)
    
    # Areas (Optional for Apartment - mansion properties don't display these fields)
    tochiMensekiStr = models.TextField(null=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    tatemonoMensekiStr = models.TextField(null=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    # Land Details
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kenpeiStr = models.TextField(null=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    yousekiStr = models.TextField(null=True)

    setsudou = models.TextField(null=True)
    chimoku = models.TextField(null=True)
    youtoChiiki = models.TextField(null=True)
    tochikenri = models.TextField(null=True)
    
    # Management
    kanrihi = models.IntegerField(null=True)
    syuzenTsumitate = models.IntegerField(null=True)

    propertyType = models.TextField() # "Apartment"

    class Meta:
        db_table = "mitsui_investment_apartment"

        