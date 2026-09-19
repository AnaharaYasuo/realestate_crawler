# -*- coding: utf-8 -*-
from django.db import models
from .base import PropertyBaseModel, TransportationMixin

# Verbose name constants to satisfy SonarCloud S1192
LABEL_GROSS_YIELD = "表面利回り"
LABEL_ANNUAL_RENT = "満室時年収（年間賃料）"
LABEL_MONTHLY_RENT = "満室時月収（月額賃料）"
LABEL_CURRENT_STATUS = "入居状況"
LABEL_KOUZOU = "建物構造"
LABEL_CHIKUNENGETSU_STR = "築年月（文字列）"
LABEL_CHIKUNENGETSU = "築年月"
LABEL_SOUKOSU_STR = "総戸数（文字列）"
LABEL_SOUKOSU = "総戸数"
LABEL_KAISU_STR = "階数（文字列）"
LABEL_TOCHI_MENSEKI_STR = "土地面積（文字列）"
LABEL_TOCHI_MENSEKI = "土地面積"
LABEL_TATEMONO_MENSEKI_STR = "建物面積（文字列）"
LABEL_TATEMONO_MENSEKI = "建物面積"
LABEL_KENPEI = "建ぺい率"
LABEL_KENPEI_STR = "建ぺい率（文字列）"
LABEL_YOUSEKI = "容積率"
LABEL_YOUSEKI_STR = "容積率（文字列）"
LABEL_SETSUDOU = "接道状況"
LABEL_CHIMOKU = "地目"
LABEL_YOUTO_CHIIKI = "用途地域"
LABEL_MADORI = "間取り"
LABEL_PROPERTY_TYPE = "物件種別"


class KenbiyaModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True, verbose_name="引渡")
    genkyo = models.TextField(blank=True, verbose_name="現況")
    tochikenri = models.TextField(blank=True, verbose_name="土地権利")
    biko = models.TextField(blank=True, verbose_name="備考")

    class Meta(PropertyBaseModel.Meta):
        abstract = True


class KenbiyaInvestmentApartment(KenbiyaModel):
    # 投資用固有項目
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=LABEL_GROSS_YIELD)
    annualRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_ANNUAL_RENT)
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_MONTHLY_RENT)
    currentStatus = models.TextField(blank=True, verbose_name=LABEL_CURRENT_STATUS)

    # 共通スペック
    kouzou = models.TextField(blank=True, verbose_name=LABEL_KOUZOU)
    chikunengetsuStr = models.TextField(blank=True, verbose_name=LABEL_CHIKUNENGETSU_STR)
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name=LABEL_CHIKUNENGETSU)
    soukosuStr = models.TextField(default="", blank=True, verbose_name=LABEL_SOUKOSU_STR)
    soukosu = models.IntegerField(null=True, blank=True, verbose_name=LABEL_SOUKOSU)
    kaisuStr = models.TextField(default="", blank=True, verbose_name=LABEL_KAISU_STR)

    # 面積
    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TOCHI_MENSEKI_STR)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TOCHI_MENSEKI)
    tatemonoMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TATEMONO_MENSEKI_STR)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TATEMONO_MENSEKI)

    # 土地詳細
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_KENPEI)
    kenpeiStr = models.TextField(default="", blank=True, verbose_name=LABEL_KENPEI_STR)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_YOUSEKI)
    yousekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_YOUSEKI_STR)

    setsudou = models.TextField(default="", blank=True, verbose_name=LABEL_SETSUDOU)
    chimoku = models.TextField(default="", blank=True, verbose_name=LABEL_CHIMOKU)
    youtoChiiki = models.TextField(default="", blank=True, verbose_name=LABEL_YOUTO_CHIIKI)
    madori = models.TextField(default="", blank=True, verbose_name=LABEL_MADORI)

    propertyType = models.TextField(default="Apartment", verbose_name=LABEL_PROPERTY_TYPE)

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_investment_apartment"
        verbose_name = "健美家一棟投資アパート"
        verbose_name_plural = "健美家一棟投資アパート一覧"


class KenbiyaInvestmentBuilding(KenbiyaModel):
    # 投資用一棟マンション・ビル
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=LABEL_GROSS_YIELD)
    annualRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_ANNUAL_RENT)
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_MONTHLY_RENT)
    currentStatus = models.TextField(blank=True, verbose_name=LABEL_CURRENT_STATUS)

    kouzou = models.TextField(blank=True, verbose_name=LABEL_KOUZOU)
    chikunengetsuStr = models.TextField(blank=True, verbose_name=LABEL_CHIKUNENGETSU_STR)
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name=LABEL_CHIKUNENGETSU)
    soukosuStr = models.TextField(default="", blank=True, verbose_name=LABEL_SOUKOSU_STR)
    soukosu = models.IntegerField(null=True, blank=True, verbose_name=LABEL_SOUKOSU)
    kaisuStr = models.TextField(default="", blank=True, verbose_name=LABEL_KAISU_STR)

    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TOCHI_MENSEKI_STR)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TOCHI_MENSEKI)
    tatemonoMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TATEMONO_MENSEKI_STR)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TATEMONO_MENSEKI)

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_KENPEI)
    kenpeiStr = models.TextField(default="", blank=True, verbose_name=LABEL_KENPEI_STR)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_YOUSEKI)
    yousekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_YOUSEKI_STR)

    setsudou = models.TextField(default="", blank=True, verbose_name=LABEL_SETSUDOU)
    chimoku = models.TextField(default="", blank=True, verbose_name=LABEL_CHIMOKU)
    youtoChiiki = models.TextField(default="", blank=True, verbose_name=LABEL_YOUTO_CHIIKI)
    madori = models.TextField(default="", blank=True, verbose_name=LABEL_MADORI)

    propertyType = models.TextField(default="Building", verbose_name=LABEL_PROPERTY_TYPE)

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_investment_building"
        verbose_name = "健美家一棟投資マンション・ビル"
        verbose_name_plural = "健美家一棟投資マンション・ビル一覧"


class KenbiyaMansion(KenbiyaModel):
    # 区分マンション
    madori = models.TextField(blank=True, verbose_name=LABEL_MADORI)
    senyuMensekiStr = models.TextField(blank=True, verbose_name="専有面積（文字列）")
    senyuMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="専有面積")
    balconyMensekiStr = models.TextField(blank=True, verbose_name="バルコニー面積（文字列）")
    balconyMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name="バルコニー面積")

    kouzou = models.TextField(blank=True, verbose_name=LABEL_KOUZOU)
    chikunengetsuStr = models.TextField(blank=True, verbose_name=LABEL_CHIKUNENGETSU_STR)
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name=LABEL_CHIKUNENGETSU)

    floorStr = models.TextField(blank=True, verbose_name="所在階（文字列）")
    floor = models.IntegerField(null=True, blank=True, verbose_name="所在階")
    totalFloorStr = models.TextField(blank=True, verbose_name="総階数（文字列）")
    totalFloor = models.IntegerField(null=True, blank=True, verbose_name="総階数")
    soukosuStr = models.TextField(blank=True, verbose_name=LABEL_SOUKOSU_STR)
    soukosu = models.IntegerField(null=True, blank=True, verbose_name=LABEL_SOUKOSU)

    direction = models.TextField(blank=True, verbose_name="主要採光面")
    kanrihi = models.IntegerField(null=True, blank=True, verbose_name="管理費")
    shuzenTsumitate = models.IntegerField(null=True, blank=True, verbose_name="修繕積立金")

    # 投資固有指標
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=LABEL_GROSS_YIELD)
    annualRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_ANNUAL_RENT)
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_MONTHLY_RENT)
    currentStatus = models.TextField(blank=True, verbose_name=LABEL_CURRENT_STATUS)

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_KENPEI)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_YOUSEKI)
    youtoChiiki = models.TextField(default="", blank=True, verbose_name=LABEL_YOUTO_CHIIKI)

    propertyType = models.TextField(default="Mansion", verbose_name=LABEL_PROPERTY_TYPE)

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_mansion"
        verbose_name = "健美家区分マンション"
        verbose_name_plural = "健美家区分マンション一覧"


class KenbiyaKodate(KenbiyaModel):
    # 戸建賃貸
    madori = models.TextField(blank=True, verbose_name=LABEL_MADORI)
    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TOCHI_MENSEKI_STR)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TOCHI_MENSEKI)
    tatemonoMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TATEMONO_MENSEKI_STR)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TATEMONO_MENSEKI)

    kouzou = models.TextField(blank=True, verbose_name=LABEL_KOUZOU)
    chikunengetsuStr = models.TextField(blank=True, verbose_name=LABEL_CHIKUNENGETSU_STR)
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name=LABEL_CHIKUNENGETSU)
    kaisuStr = models.TextField(default="", blank=True, verbose_name=LABEL_KAISU_STR)

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_KENPEI)
    kenpeiStr = models.TextField(default="", blank=True, verbose_name=LABEL_KENPEI_STR)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_YOUSEKI)
    yousekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_YOUSEKI_STR)

    setsudou = models.TextField(default="", blank=True, verbose_name=LABEL_SETSUDOU)
    chimoku = models.TextField(default="", blank=True, verbose_name=LABEL_CHIMOKU)
    youtoChiiki = models.TextField(default="", blank=True, verbose_name=LABEL_YOUTO_CHIIKI)

    # 投資固有指標
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=LABEL_GROSS_YIELD)
    annualRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_ANNUAL_RENT)
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_MONTHLY_RENT)
    currentStatus = models.TextField(blank=True, verbose_name=LABEL_CURRENT_STATUS)

    propertyType = models.TextField(default="Kodate", verbose_name=LABEL_PROPERTY_TYPE)

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_kodate"
        verbose_name = "健美家戸建賃貸"
        verbose_name_plural = "健美家戸建賃貸一覧"


class KenbiyaTochi(KenbiyaModel):
    # 投資用土地・事業用土地
    tochiMensekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_TOCHI_MENSEKI_STR)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=LABEL_TOCHI_MENSEKI)

    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_KENPEI)
    kenpeiStr = models.TextField(default="", blank=True, verbose_name=LABEL_KENPEI_STR)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_YOUSEKI)
    yousekiStr = models.TextField(default="", blank=True, verbose_name=LABEL_YOUSEKI_STR)

    setsudou = models.TextField(default="", blank=True, verbose_name=LABEL_SETSUDOU)
    chimoku = models.TextField(default="", blank=True, verbose_name=LABEL_CHIMOKU)
    youtoChiiki = models.TextField(default="", blank=True, verbose_name=LABEL_YOUTO_CHIIKI)

    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=LABEL_GROSS_YIELD)
    annualRent = models.IntegerField(null=True, blank=True, verbose_name="年間賃料")

    propertyType = models.TextField(default="Tochi", verbose_name=LABEL_PROPERTY_TYPE)

    class Meta(KenbiyaModel.Meta):
        db_table = "kenbiya_tochi"
        verbose_name = "健美家投資用土地"
        verbose_name_plural = "健美家投資用土地一覧"
