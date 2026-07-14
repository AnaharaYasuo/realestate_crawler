# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class MizuhoModel(PropertyBaseModel, TransportationMixin):
    address1 = models.TextField(null=True, blank=True)
    address2 = models.TextField(null=True, blank=True)
    address3 = models.TextField(null=True, blank=True)
    addressKyoto = models.TextField(null=True, blank=True)

    hikiwatashi = models.TextField(blank=True)
    genkyo = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    torihiki = models.TextField(blank=True)
    biko = models.TextField(blank=True)

    class Meta(PropertyBaseModel.Meta):
        abstract = True

class MizuhoMansion(MizuhoModel):
    madori = models.TextField(blank=True)
    senyuMensekiStr = models.TextField(blank=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kaisuStr = models.TextField(null=True, blank=True)

    chikunengetsuStr = models.TextField(blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)

    saikouKadobeya = models.TextField(blank=True)
    saikou = models.TextField(blank=True)
    saikouMuki = models.TextField(blank=True)
    saikouMukiStr = models.TextField(blank=True)
    kadobeya = models.TextField(blank=True)
    soukosuStr = models.TextField(blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    kanrihiStr = models.TextField(blank=True)
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitateStr = models.TextField(blank=True)
    syuzenTsumitate = models.IntegerField(null=True, blank=True)
    kanriKeitai = models.TextField(blank=True)
    kanriKaisya = models.TextField(blank=True)
    kouzou = models.TextField(blank=True)

    balconyMensekiStr = models.TextField(blank=True)
    saikouSaitekiStr = models.TextField(blank=True)

    floorType_kai = models.IntegerField(null=True, blank=True)
    floorType_chijo = models.IntegerField(null=True, blank=True)
    floorType_chika = models.IntegerField(null=True, blank=True)
    floorType_kouzou = models.TextField(blank=True)
    saikouSaiteki = models.TextField(blank=True)
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    senyouNiwaMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    roofBarukoniMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kanrihi_p_heibei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    syuzenTsumitate_p_heibei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    class Meta(MizuhoModel.Meta):
        db_table = "mizuho_mansion"

class MizuhoTochi(MizuhoModel):
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenchikuJoken = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True)

    youtoChiiki = models.TextField(blank=True)
    kuiki = models.TextField(blank=True)
    kokudoHou = models.TextField(blank=True)

    setsudou = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)
    douroHaba = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    maguchiStr = models.TextField(null=True, blank=True)
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    okuyukiStr = models.TextField(null=True, blank=True)
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadWidthStr = models.TextField(null=True, blank=True)
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadDirection = models.TextField(null=True, blank=True)
    roadType = models.TextField(null=True, blank=True)
    roadStructure = models.TextField(null=True, blank=True)

    class Meta(MizuhoModel.Meta):
        db_table = "mizuho_tochi"

class MizuhoInvestment(MizuhoModel):
    # 投資用共通
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    annualRent = models.IntegerField(null=True, blank=True)
    monthlyRent = models.IntegerField(null=True, blank=True)
    currentStatus = models.TextField(blank=True)
    propertyType = models.TextField(blank=True) # "Apartment", "Mansion", "Building", "Tochi"

    # 建物スペック
    kouzou = models.TextField(blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    soukosuStr = models.TextField(blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    kaisuStr = models.TextField(null=True, blank=True)

    # 面積
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    # 土地スペック
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True)
    setsudou = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    youtoChiiki = models.TextField(blank=True)

    class Meta(MizuhoModel.Meta):
        db_table = "mizuho_investment"


class MizuhoKodate(MizuhoModel):
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    kaisuKouzou = models.TextField(blank=True)
    kaisuStr = models.TextField(blank=True)
    kaisu = models.IntegerField(null=True, blank=True)
    kouzou = models.TextField(blank=True)
    madori = models.TextField(blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True)

    youtoChiiki = models.TextField(blank=True)
    kuiki = models.TextField(blank=True)
    kokudoHou = models.TextField(blank=True)

    setsudou = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)
    douroHaba = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    maguchiStr = models.TextField(null=True, blank=True)
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    okuyukiStr = models.TextField(null=True, blank=True)
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadWidthStr = models.TextField(null=True, blank=True)
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadDirection = models.TextField(null=True, blank=True)
    roadType = models.TextField(null=True, blank=True)
    roadStructure = models.TextField(null=True, blank=True)

    class Meta(MizuhoModel.Meta):
        db_table = "mizuho_kodate"
