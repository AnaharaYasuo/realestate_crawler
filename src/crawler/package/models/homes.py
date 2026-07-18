# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

class HomesModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True)
    genkyo = models.TextField(blank=True)
    tochikenri = models.TextField(blank=True)
    biko = models.TextField(blank=True)

    class Meta(PropertyBaseModel.Meta):
        abstract = True

class HomesInvestmentApartment(HomesModel):
    # 投資用固有項目
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    annualRent = models.IntegerField(null=True, blank=True)
    monthlyRent = models.IntegerField(null=True, blank=True)
    currentStatus = models.TextField(blank=True)
    
    # 共通スペック
    kouzou = models.TextField(blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    soukosuStr = models.TextField(default="", blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    kaisuStr = models.TextField(default="", blank=True)
    
    # 面積
    tochiMensekiStr = models.TextField(default="", blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(default="", blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # 土地詳細
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(default="", blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(default="", blank=True)

    setsudou = models.TextField(default="", blank=True)
    chimoku = models.TextField(default="", blank=True)
    youtoChiiki = models.TextField(default="", blank=True)
    tochikenri = models.TextField(default="", blank=True)
    
    propertyType = models.TextField(default="Apartment")

    class Meta(HomesModel.Meta):
        db_table = "homes_investment_apartment"

class HomesMansion(HomesModel):
    madori = models.TextField(blank=True)
    senyuMensekiStr = models.TextField(blank=True)
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kaisuStr = models.TextField(default="", blank=True)
    chikunengetsuStr = models.TextField(blank=True)
    chikunengetsu = models.DateField(null=True, blank=True)
    balconyMensekiStr = models.TextField(blank=True)
    saikou = models.TextField(blank=True)
    soukosuStr = models.TextField(blank=True)
    soukosu = models.IntegerField(null=True, blank=True)
    kanriKeitai = models.TextField(blank=True)
    kanriKaisya = models.TextField(blank=True)
    kanrihiStr = models.TextField(blank=True)
    kanrihi = models.IntegerField(null=True, blank=True)
    syuzenTsumitateStr = models.TextField(blank=True)
    syuzenTsumitate = models.IntegerField(null=True, blank=True)
    tyusyajo = models.TextField(blank=True)
    kouzou = models.TextField(blank=True)

    class Meta(HomesModel.Meta):
        db_table = "homes_mansion"

class HomesKodate(HomesModel):
    tochiMensekiStr = models.TextField(blank=True)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    tatemonoMensekiStr = models.TextField(blank=True)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kaisuStr = models.TextField(default="", blank=True)
    kouzou = models.TextField(blank=True)
    tyusyajo = models.TextField(blank=True)
    chimoku = models.TextField(blank=True)
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    kenpeiStr = models.TextField(blank=True)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    yousekiStr = models.TextField(blank=True)
    youtoChiiki = models.TextField(blank=True)
    setsudou = models.TextField(blank=True)
    douroMuki = models.TextField(blank=True)

    class Meta(HomesModel.Meta):
        db_table = "homes_kodate"


class HomesTochi(HomesModel):
    # 土地面積
    tochiMensekiStr = models.TextField(blank=True, default="", verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="土地面積（数値）")
    
    # 用途・建容
    youtoChiiki = models.TextField(blank=True, default="", verbose_name="用途地域")
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="建ぺい率")
    kenpeiStr = models.TextField(blank=True, default="", verbose_name="建ぺい率（文字列）")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="容積率")
    yousekiStr = models.TextField(blank=True, default="", verbose_name="容積率（文字列）")
    
    # 土地評価用パラメータ
    maguchiStr = models.TextField(blank=True, default="", verbose_name="間口（文字列）")
    maguchi = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, verbose_name="間口（数値）")
    
    okuyukiStr = models.TextField(blank=True, default="", verbose_name="奥行（文字列）")
    okuyuki = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, verbose_name="奥行（数値）")
    
    roadWidthStr = models.TextField(blank=True, default="", verbose_name="前面道路幅員（文字列）")
    roadWidth = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, verbose_name="前面道路幅員（数値）")
    
    roadDirection = models.TextField(blank=True, default="", verbose_name="接道方位")
    roadType = models.TextField(blank=True, default="", verbose_name="道路区分")
    roadStructure = models.TextField(blank=True, default="", verbose_name="接道状況")
    
    chimoku = models.TextField(blank=True, default="", verbose_name="地目")
    setsudou = models.TextField(blank=True, default="", verbose_name="接道状況詳細")

    class Meta(HomesModel.Meta):
        db_table = "homes_tochi"

