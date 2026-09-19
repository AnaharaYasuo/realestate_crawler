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
