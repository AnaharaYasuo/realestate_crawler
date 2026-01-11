from django.db import models

class MisawaCommon(models.Model):
    propertyName = models.TextField()
    pageUrl = models.TextField()
    inputDate = models.DateField()
    inputDateTime = models.DateTimeField()
    priceStr = models.TextField()
    price = models.IntegerField()
    address = models.TextField()
    railway1 = models.TextField()
    station1 = models.TextField()
    walkMinute1 = models.IntegerField(null=True)
    landTenure = models.TextField() # 土地権利の種類
    kenpei = models.IntegerField(null=True)
    youseki = models.IntegerField(null=True)
    zoning = models.TextField() # 用途地域
    deliveryDate = models.TextField() # 引渡（入居予定日）
    facilities = models.TextField() # 物件設備
    neighborhood = models.TextField() # 周辺施設
    schoolDistrict = models.TextField() # 学区
    transactionType = models.TextField() # 取引態様
    remarks = models.TextField() # 備考 制限事項
    updatedAt = models.DateField(null=True)
    nextUpdateAt = models.DateField(null=True)

    class Meta:
        abstract = True

class MisawaMansion(MisawaCommon):
    senyuMenseki = models.DecimalField(max_digits=7, decimal_places=2, null=True)
    balconyMenseki = models.DecimalField(max_digits=7, decimal_places=2, null=True)
    madori = models.TextField(null=True) # Added field
    floor = models.TextField() # 所在階
    structure = models.TextField() # 建物構造
    completionDate = models.TextField() # 完成時期
    totalUnits = models.IntegerField(null=True) # 総戸数
    managementType = models.TextField() # 管理形態・方式
    managementCompany = models.TextField() # 管理会社
    managementFee = models.IntegerField(null=True) # 管理費
    repairReserve = models.IntegerField(null=True) # 修繕積立金
    parkingStatus = models.TextField() # 駐車場状況/料金

    class Meta:
        db_table = "misawa_mansion"

class MisawaKodate(MisawaCommon):
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    tatemonoMenseki = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    madori = models.TextField()
    structure = models.TextField()
    completionDate = models.TextField()
    confirmationNumber = models.TextField() # 建築確認番号
    roadCondition = models.TextField() # 接道状況
    privateRoadFee = models.TextField() # 私道負担
    setback = models.TextField()
    urbanPlanning = models.TextField() # 都市計画
    parkingCount = models.TextField() # 駐車場台数

    class Meta:
        db_table = "misawa_kodate"

class MisawaTochi(MisawaCommon):
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    landCategory = models.TextField() # 地目
    roadCondition = models.TextField()
    buildingCondition = models.TextField() # 建築条件
    urbanPlanning = models.TextField()
    currentStatus = models.TextField() # 建物現況

    class Meta:
        db_table = "misawa_tochi"

class MisawaInvestment(MisawaCommon):
    tochiMenseki = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    tatemonoMenseki = models.DecimalField(max_digits=8, decimal_places=2, null=True)
    structure = models.TextField()
    completionDate = models.TextField()
    yield_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True) # 利回り
    annualIncome = models.IntegerField(null=True) # 年間収入
    madori = models.TextField()
    totalUnits = models.IntegerField(null=True)
    roadCondition = models.TextField()
    managementFee = models.IntegerField(null=True) # 区分の場合

    class Meta:
        db_table = "misawa_investment"
