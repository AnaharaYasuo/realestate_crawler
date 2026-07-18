# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class DaikyoModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True, default="")
    genkyo = models.TextField(blank=True, default="")
    saikouSaiteki = models.TextField(blank=True, default="")
    saikouSaitekiStr = models.TextField(blank=True, default="")
    biko = models.TextField(blank=True, default="")
    saikouMukiStr = models.TextField(blank=True, default="")
    tochikenri = models.TextField(blank=True, default="")
    torihiki = models.TextField(blank=True, default="")

    # 共通の住所分割フィールド
    address1 = models.TextField(blank=True, default="")
    address2 = models.TextField(blank=True, default="")
    address3 = models.TextField(blank=True, default="")
    addressKyoto = models.TextField(blank=True, default="")

    class Meta:
        abstract = True

class DaikyoMansion(DaikyoModel):
    madori = models.TextField(blank=True, default="")
    senyuMensekiStr = models.TextField(blank=True, default="")
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    saikouKadobeya = models.TextField(blank=True, default="")
    soukosuStr = models.TextField(blank=True, default="")
    soukosu = models.IntegerField(null=True, blank=True)
    kanrihiStr = models.TextField(blank=True, default="")
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitateStr = models.TextField(blank=True, default="")
    syuzenTsumitate = models.IntegerField(null=True, blank=True)
    saikou = models.TextField(blank=True, default="")
    saikouMuki = models.TextField(blank=True, default="")
    kadobeya = models.TextField(blank=True, default="")
    kanriKeitai = models.TextField(blank=True, default="")
    kanriKaisya = models.TextField(blank=True, default="")
    kaisuStr = models.TextField(blank=True, default="")
    floorType_kai = models.IntegerField(null=True, blank=True)
    floorType_chijo = models.IntegerField(null=True, blank=True)
    floorType_chika = models.IntegerField(null=True, blank=True)
    floorType_kouzou = models.TextField(blank=True, default="")
    balconyMensekiStr = models.TextField(blank=True, default="")
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kouzou = models.TextField(blank=True, default="")
    chikunengetsuStr = models.TextField(blank=True, default="")
    chikunengetsu = models.DateField(null=True, blank=True)

    class Meta(DaikyoModel.Meta):
        db_table = "daikyo_mansion"

class DaikyoKodate(DaikyoModel):
    tochiMensekiStr = models.TextField(blank=True, default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(blank=True, default="")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kaisuKouzou = models.TextField(blank=True, default="")
    kaisuStr = models.TextField(blank=True, default="")
    kaisu = models.IntegerField(null=True, blank=True)
    kouzou = models.TextField(blank=True, default="")
    madori = models.TextField(blank=True, default="")
    chikunengetsuStr = models.TextField(blank=True, default="")
    chikunengetsu = models.DateField(null=True, blank=True)
    kenpeiStr = models.TextField(blank=True, default="")
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True, default="")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    youtoChiiki = models.TextField(blank=True, default="")
    setsudou = models.TextField(blank=True, default="")

    class Meta(DaikyoModel.Meta):
        db_table = "daikyo_kodate"

class DaikyoTochi(DaikyoModel):
    tochiMensekiStr = models.TextField(blank=True, default="")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenchikuJoken = models.TextField(blank=True, default="")
    chimoku = models.TextField(blank=True, default="")
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True, default="")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True, default="")
    youtoChiiki = models.TextField(blank=True, default="")
    setsudou = models.TextField(blank=True, default="")

    class Meta(DaikyoModel.Meta):
        db_table = "daikyo_tochi"
