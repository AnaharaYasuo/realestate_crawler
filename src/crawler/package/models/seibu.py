# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class SeibuModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True, null=True)
    genkyo = models.TextField(blank=True, null=True)
    saikouSaiteki = models.TextField(blank=True, null=True)
    saikouSaitekiStr = models.TextField(blank=True, null=True)
    biko = models.TextField(blank=True, null=True)
    saikouMukiStr = models.TextField(blank=True, null=True)
    tochikenri = models.TextField(blank=True, null=True)
    torihiki = models.TextField(blank=True, null=True)

    # 共通の住所分割フィールド
    address1 = models.TextField(blank=True, null=True)
    address2 = models.TextField(blank=True, null=True)
    address3 = models.TextField(blank=True, null=True)
    addressKyoto = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

class SeibuMansion(SeibuModel):
    madori = models.TextField(blank=True, null=True)
    senyuMensekiStr = models.TextField(blank=True, null=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    saikouKadobeya = models.TextField(blank=True, null=True)
    soukosuStr = models.TextField(blank=True, null=True)
    soukosu = models.IntegerField(null=True, blank=True)
    kanrihiStr = models.TextField(blank=True, null=True)
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitateStr = models.TextField(blank=True, null=True)
    syuzenTsumitate = models.IntegerField(null=True, blank=True)
    saikou = models.TextField(blank=True, null=True)
    saikouMuki = models.TextField(blank=True, null=True)
    kadobeya = models.TextField(blank=True, null=True)
    kanriKeitai = models.TextField(blank=True, null=True)
    kanriKaisya = models.TextField(blank=True, null=True)
    kaisuStr = models.TextField(blank=True, null=True)
    floorType_kai = models.IntegerField(null=True, blank=True)
    floorType_chijo = models.IntegerField(null=True, blank=True)
    floorType_chika = models.IntegerField(null=True, blank=True)
    floorType_kouzou = models.TextField(blank=True, null=True)
    balconyMensekiStr = models.TextField(blank=True, null=True)
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kouzou = models.TextField(blank=True, null=True)
    chikunengetsuStr = models.TextField(blank=True, null=True)
    chikunengetsu = models.DateField(null=True, blank=True)

    class Meta(SeibuModel.Meta):
        db_table = "seibu_mansion"

class SeibuKodate(SeibuModel):
    tochiMensekiStr = models.TextField(blank=True, null=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(blank=True, null=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kaisuKouzou = models.TextField(blank=True, null=True)
    kaisuStr = models.TextField(blank=True, null=True)
    kaisu = models.IntegerField(null=True, blank=True)
    kouzou = models.TextField(blank=True, null=True)
    madori = models.TextField(blank=True, null=True)
    chikunengetsuStr = models.TextField(blank=True, null=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    kenpeiStr = models.TextField(blank=True, null=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True, null=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    youtoChiiki = models.TextField(blank=True, null=True)
    setsudou = models.TextField(blank=True, null=True)

    class Meta(SeibuModel.Meta):
        db_table = "seibu_kodate"

class SeibuTochi(SeibuModel):
    tochiMensekiStr = models.TextField(blank=True, null=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenchikuJoken = models.TextField(blank=True, null=True)
    chimoku = models.TextField(blank=True, null=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True, null=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True, null=True)
    youtoChiiki = models.TextField(blank=True, null=True)
    setsudou = models.TextField(blank=True, null=True)

    class Meta(SeibuModel.Meta):
        db_table = "seibu_tochi"
