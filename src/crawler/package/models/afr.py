# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class AfrModel(PropertyBaseModel, TransportationMixin):
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

class AfrMansion(AfrModel):
    madori = models.TextField(blank=True)
    senyuMensekiStr = models.TextField(blank=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kaisuStr = models.TextField(default="", blank=True)

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

    class Meta(AfrModel.Meta):
        db_table = "afr_mansion"

class AfrTochi(AfrModel):
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

    maguchiStr = models.TextField(default="", blank=True)
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    okuyukiStr = models.TextField(default="", blank=True)
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadWidthStr = models.TextField(default="", blank=True)
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadDirection = models.TextField(default="", blank=True)
    roadType = models.TextField(default="", blank=True)
    roadStructure = models.TextField(default="", blank=True)

    class Meta(AfrModel.Meta):
        db_table = "afr_tochi"

class AfrKodate(AfrModel):
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

    maguchiStr = models.TextField(default="", blank=True)
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    okuyukiStr = models.TextField(default="", blank=True)
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadWidthStr = models.TextField(default="", blank=True)
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    roadDirection = models.TextField(default="", blank=True)
    roadType = models.TextField(default="", blank=True)
    roadStructure = models.TextField(default="", blank=True)

    class Meta(AfrModel.Meta):
        db_table = "afr_kodate"
