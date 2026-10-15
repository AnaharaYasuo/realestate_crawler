from django.db import models

from .base import PropertyBaseModel, TransportationMixin

# Verbose name constants to satisfy SonarCloud S1192
LABEL_GROSS_YIELD = "表面利回り"
LABEL_ANNUAL_RENT = "満室時年収（年間賃料）"
LABEL_MONTHLY_RENT = "満室時月収（月額賃料）"
LABEL_CURRENT_STATUS = "現況"
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


class ReguideModel(PropertyBaseModel, TransportationMixin):
    hikiwatashi = models.TextField(blank=True, default="", verbose_name="引渡")
    genkyo = models.TextField(blank=True, default="", verbose_name="現況")
    tochikenri = models.TextField(blank=True, default="", verbose_name="土地権利")
    biko = models.TextField(blank=True, default="", verbose_name="備考")

    class Meta(PropertyBaseModel.Meta):
        abstract = True


class ReguideInvestment(ReguideModel):
    # 投資用固有指標
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=LABEL_GROSS_YIELD)
    annualRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_ANNUAL_RENT)
    monthlyRent = models.IntegerField(null=True, blank=True, verbose_name=LABEL_MONTHLY_RENT)
    currentStatus = models.TextField(blank=True, default="", verbose_name=LABEL_CURRENT_STATUS)

    # 建物スペック
    kouzou = models.TextField(blank=True, default="", verbose_name=LABEL_KOUZOU)
    chikunengetsuStr = models.TextField(blank=True, default="", verbose_name=LABEL_CHIKUNENGETSU_STR)
    chikunengetsu = models.DateField(null=True, blank=True, verbose_name=LABEL_CHIKUNENGETSU)
    soukosuStr = models.TextField(blank=True, default="", verbose_name=LABEL_SOUKOSU_STR)
    soukosu = models.IntegerField(null=True, blank=True, verbose_name=LABEL_SOUKOSU)
    kaisuStr = models.TextField(blank=True, default="", verbose_name=LABEL_KAISU_STR)

    # 面積
    tochiMensekiStr = models.TextField(blank=True, default="", verbose_name=LABEL_TOCHI_MENSEKI_STR)
    tochiMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_TOCHI_MENSEKI)
    tatemonoMensekiStr = models.TextField(blank=True, default="", verbose_name=LABEL_TATEMONO_MENSEKI_STR)
    tatemonoMenseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_TATEMONO_MENSEKI)

    # 土地詳細
    kenpei = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_KENPEI)
    kenpeiStr = models.TextField(blank=True, default="", verbose_name=LABEL_KENPEI_STR)
    youseki = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, verbose_name=LABEL_YOUSEKI)
    yousekiStr = models.TextField(blank=True, default="", verbose_name=LABEL_YOUSEKI_STR)

    setsudou = models.TextField(blank=True, default="", verbose_name=LABEL_SETSUDOU)
    chimoku = models.TextField(blank=True, default="", verbose_name=LABEL_CHIMOKU)
    youtoChiiki = models.TextField(blank=True, default="", verbose_name=LABEL_YOUTO_CHIIKI)
    madori = models.TextField(blank=True, default="", verbose_name=LABEL_MADORI)

    propertyType = models.TextField(blank=True, default="Investment", verbose_name=LABEL_PROPERTY_TYPE)

    class Meta(ReguideModel.Meta):
        app_label = "package"
        db_table = "reguide_investment"
        verbose_name = "リガイド収益物件"
        verbose_name_plural = "リガイド収益物件一覧"
