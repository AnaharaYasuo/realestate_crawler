# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin


class KenbiyaModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True, verbose_name="引渡")
    genkyo = models.TextField(blank=True, verbose_name="現況")
    tochikenri = models.TextField(blank=True, verbose_name="土地権利")
    biko = models.TextField(blank=True, verbose_name="備考")

    class Meta(PropertyBaseModel.Meta):
        abstract = True


class KenbiyaInvestmentApartment(KenbiyaModel):
    # 投資用固有項目
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="表面利回り")
    annualRent = models.IntegerField(null=True, blank=True, verbose_name="満室時年収（年間賃料）")
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name="満室時月収（月額賃料）")
    currentStatus = models.TextField(blank=True, verbose_name="入居状況")

    # 共通スペック
    kouzou = models.TextField(blank=True, verbose_name="建物構造")
    chikunengetsuStr = models.TextField(blank=True, verbose_name="築年月（文字列）")
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name="築年月")
    soukosuStr = models.TextField(default="", blank=True, verbose_name="総戸数（文字列）")
    soukosu = models.IntegerField(null=True, blank=True, verbose_name="総戸数")
    kaisuStr = models.TextField(default="", blank=True, verbose_name="階数（文字列）")

    # 面積
    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="土地面積")
    tatemonoMensekiStr = models.TextField(default="", blank=True, verbose_name="建物面積（文字列）")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="建物面積")

    # 土地詳細
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="建ぺい率")
    kenpeiStr = models.TextField(default="", blank=True, verbose_name="建ぺい率（文字列）")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="容積率")
    yousekiStr = models.TextField(default="", blank=True, verbose_name="容積率（文字列）")

    setsudou = models.TextField(default="", blank=True, verbose_name="接道状況")
    chimoku = models.TextField(default="", blank=True, verbose_name="地目")
    youtoChiiki = models.TextField(default="", blank=True, verbose_name="用途地域")
    madori = models.TextField(default="", blank=True, verbose_name="間取り")

    propertyType = models.TextField(default="Apartment", verbose_name="物件種別")

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_investment_apartment"
        verbose_name = "健美家一棟投資アパート"
        verbose_name_plural = "健美家一棟投資アパート一覧"


class KenbiyaInvestmentBuilding(KenbiyaModel):
    # 投資用一棟マンション・ビル
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="表面利回り")
    annualRent = models.IntegerField(null=True, blank=True, verbose_name="満室時年収（年間賃料）")
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name="満室時月収（月額賃料）")
    currentStatus = models.TextField(blank=True, verbose_name="入居状況")

    kouzou = models.TextField(blank=True, verbose_name="建物構造")
    chikunengetsuStr = models.TextField(blank=True, verbose_name="築年月（文字列）")
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name="築年月")
    soukosuStr = models.TextField(default="", blank=True, verbose_name="総戸数（文字列）")
    soukosu = models.IntegerField(null=True, blank=True, verbose_name="総戸数")
    kaisuStr = models.TextField(default="", blank=True, verbose_name="階数（文字列）")

    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="土地面積")
    tatemonoMensekiStr = models.TextField(default="", blank=True, verbose_name="建物面積（文字列）")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="建物面積")

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="建ぺい率")
    kenpeiStr = models.TextField(default="", blank=True, verbose_name="建ぺい率（文字列）")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="容積率")
    yousekiStr = models.TextField(default="", blank=True, verbose_name="容積率（文字列）")

    setsudou = models.TextField(default="", blank=True, verbose_name="接道状況")
    chimoku = models.TextField(default="", blank=True, verbose_name="地目")
    youtoChiiki = models.TextField(default="", blank=True, verbose_name="用途地域")
    madori = models.TextField(default="", blank=True, verbose_name="間取り")

    propertyType = models.TextField(default="Building", verbose_name="物件種別")

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_investment_building"
        verbose_name = "健美家一棟投資マンション・ビル"
        verbose_name_plural = "健美家一棟投資マンション・ビル一覧"


class KenbiyaMansion(KenbiyaModel):
    # 区分マンション
    madori = models.TextField(blank=True, verbose_name="間取り")
    senyuMensekiStr = models.TextField(blank=True, verbose_name="専有面積（文字列）")
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="専有面積")
    balconyMensekiStr = models.TextField(blank=True, verbose_name="バルコニー面積（文字列）")
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="バルコニー面積")

    kouzou = models.TextField(blank=True, verbose_name="建物構造")
    chikunengetsuStr = models.TextField(blank=True, verbose_name="築年月（文字列）")
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name="築年月")

    floorStr = models.TextField(blank=True, verbose_name="所在階（文字列）")
    floor = models.IntegerField(null=True, blank=True, verbose_name="所在階")
    totalFloorStr = models.TextField(blank=True, verbose_name="総階数（文字列）")
    totalFloor = models.IntegerField(null=True, blank=True, verbose_name="総階数")
    soukosuStr = models.TextField(blank=True, verbose_name="総戸数（文字列）")
    soukosu = models.IntegerField(null=True, blank=True, verbose_name="総戸数")

    direction = models.TextField(blank=True, verbose_name="主要採光面")
    kanrihi = models.IntegerField(null=True, blank=True, verbose_name="管理費")
    shuzenTsumitate = models.IntegerField(null=True, blank=True, verbose_name="修繕積立金")

    # 投資固有指標
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="表面利回り")
    annualRent = models.IntegerField(null=True, blank=True, verbose_name="満室時年収（年間賃料）")
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name="満室時月収（月額賃料）")
    currentStatus = models.TextField(blank=True, verbose_name="入居状況")

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="建ぺい率")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="容積率")
    youtoChiiki = models.TextField(default="", blank=True, verbose_name="用途地域")

    propertyType = models.TextField(default="Mansion", verbose_name="物件種別")

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_mansion"
        verbose_name = "健美家区分マンション"
        verbose_name_plural = "健美家区分マンション一覧"


class KenbiyaKodate(KenbiyaModel):
    # 戸建賃貸
    madori = models.TextField(blank=True, verbose_name="間取り")
    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="土地面積")
    tatemonoMensekiStr = models.TextField(default="", blank=True, verbose_name="建物面積（文字列）")
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="建物面積")

    kouzou = models.TextField(blank=True, verbose_name="建物構造")
    chikunengetsuStr = models.TextField(blank=True, verbose_name="築年月（文字列）")
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name="築年月")
    kaisuStr = models.TextField(default="", blank=True, verbose_name="階数（文字列）")

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="建ぺい率")
    kenpeiStr = models.TextField(default="", blank=True, verbose_name="建ぺい率（文字列）")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="容積率")
    yousekiStr = models.TextField(default="", blank=True, verbose_name="容積率（文字列）")

    setsudou = models.TextField(default="", blank=True, verbose_name="接道状況")
    chimoku = models.TextField(default="", blank=True, verbose_name="地目")
    youtoChiiki = models.TextField(default="", blank=True, verbose_name="用途地域")

    # 投資固有指標
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="表面利回り")
    annualRent = models.IntegerField(null=True, blank=True, verbose_name="満室時年収（年間賃料）")
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name="満室時月収（月額賃料）")
    currentStatus = models.TextField(blank=True, verbose_name="入居状況")

    propertyType = models.TextField(default="Kodate", verbose_name="物件種別")

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_kodate"
        verbose_name = "健美家戸建賃貸"
        verbose_name_plural = "健美家戸建賃貸一覧"


class KenbiyaTochi(KenbiyaModel):
    # 投資用土地・事業用土地
    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name="土地面積（文字列）")
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="土地面積")

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="建ぺい率")
    kenpeiStr = models.TextField(default="", blank=True, verbose_name="建ぺい率（文字列）")
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="容積率")
    yousekiStr = models.TextField(default="", blank=True, verbose_name="容積率（文字列）")

    setsudou = models.TextField(default="", blank=True, verbose_name="接道状況")
    chimoku = models.TextField(default="", blank=True, verbose_name="地目")
    youtoChiiki = models.TextField(default="", blank=True, verbose_name="用途地域")

    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="表面利回り")
    annualRent = models.IntegerField(null=True, blank=True, verbose_name="年間賃料")

    propertyType = models.TextField(default="Tochi", verbose_name="物件種別")

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_tochi"
        verbose_name = "健美家投資用土地"
        verbose_name_plural = "健美家投資用土地一覧"

