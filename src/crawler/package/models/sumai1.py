# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class Sumai1Model(PropertyBaseModel, TransportationMixin):
    address1 = models.TextField(default="", blank=True)
    address2 = models.TextField(default="", blank=True)
    address3 = models.TextField(default="", blank=True)
    addressKyoto = models.TextField(default="", blank=True)

    hikiwatashi = models.TextField(blank=True)
    genkyo = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    torihiki = models.TextField(blank=True)
    biko = models.TextField(blank=True)

    class Meta(PropertyBaseModel.Meta):
        abstract = True

class Sumai1Mansion(Sumai1Model):
    madori = models.TextField(blank=True)
    senyuMensekiStr = models.TextField(blank=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    kaisuStr = models.TextField(default="", blank=True)

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
    kouzou = models.TextField(blank=True)
    sonotaHiyouStr = models.TextField(blank=True)
    bunjoKaisya = models.TextField(blank=True)
    sekouKaisya = models.TextField(blank=True)

    floorType_kai = models.IntegerField(null=True)
    floorType_chijo = models.IntegerField(null=True)
    floorType_chika = models.IntegerField(null=True)
    floorType_kouzou = models.TextField(blank=True)
    kyutaishin = models.IntegerField(null=True)
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    senyouNiwaMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    roofBarukoniMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kanrihi_p_heibei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    syuzenTsumitate_p_heibei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    class Meta(Sumai1Model.Meta):
        db_table = "sumai1_mansion"

class Sumai1Tochi(Sumai1Model):
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

    setsudou = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)
    douroHaba = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=10, decimal_places=3, null=True)

    maguchiStr = models.TextField(default="", blank=True)
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    okuyukiStr = models.TextField(default="", blank=True)
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadWidthStr = models.TextField(default="", blank=True)
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadDirection = models.TextField(default="", blank=True)
    roadType = models.TextField(default="", blank=True)
    roadStructure = models.TextField(default="", blank=True)

    class Meta(Sumai1Model.Meta):
        db_table = "sumai1_tochi"

class Sumai1Investment(Sumai1Model):
    # 投資用共通
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    annualRent = models.IntegerField(null=True)
    monthlyRent = models.IntegerField(null=True)
    currentStatus = models.TextField(blank=True)
    propertyType = models.TextField(blank=True) # "Apartment", "Mansion", "Building", "Tochi"

    # 建物スペック
    kouzou = models.TextField(blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    chikunengetsu = models.DateField(null=True)
    soukosuStr = models.TextField(blank=True)
    soukosu = models.IntegerField(null=True)
    kaisuStr = models.TextField(default="", blank=True)

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

    class Meta(Sumai1Model.Meta):
        db_table = "sumai1_investment"


class Sumai1Kodate(Sumai1Model):
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)
    tatemonoMensekiStr = models.TextField(blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True)

    kaisuKouzou = models.TextField(blank=True)
    kaisu = models.TextField(blank=True)
    kaisuStr = models.TextField(default="", blank=True)
    kouzou = models.TextField(blank=True)

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
    douroHaba = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    douroKubun = models.TextField(blank=True)
    setsumen = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    sonotaHiyouStr = models.TextField(blank=True)

    class Meta(Sumai1Model.Meta):
        db_table = "sumai1_kodate"
