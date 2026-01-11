from django.db import models

class NomuraInvestmentModel(models.Model):
    propertyName = models.TextField()
    pageUrl = models.CharField(max_length=500, db_index=True)
    inputDate = models.DateField()
    inputDateTime = models.DateTimeField()
    
    priceStr = models.TextField()
    price = models.IntegerField(null=True)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True) # 利回り
    
    address = models.TextField()
    traffic = models.TextField(null=True)
    
    structure = models.TextField(null=True)
    yearBuilt = models.TextField(null=True)
    
    landArea = models.TextField(null=True)
    buildingArea = models.TextField(null=True)
    
    currentStatus = models.TextField(null=True) # 現況
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.propertyName = ""
        self.pageUrl = ""
        self.inputDate = None
        self.inputDateTime = None
        self.priceStr = ""
        self.price = None
        self.grossYield = None
        self.address = ""
        self.traffic = ""
        self.structure = ""
        self.yearBuilt = ""
        self.landArea = ""
        self.buildingArea = ""
        self.currentStatus = ""

    class Meta:
        db_table = "nomura_investment"
        abstract = False

class NomuraMansion(models.Model):
    pageUrl = models.CharField(max_length=500, db_index=True)
    propertyName = models.TextField()
    priceStr = models.TextField()
    price = models.IntegerField()
    address = models.TextField()
    traffic = models.TextField()
    madori = models.TextField()
    senyuMensekiStr = models.TextField()
    senyuMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    balconyArea = models.TextField(null=True)
    facing = models.TextField(null=True)
    otherArea = models.TextField(null=True)
    structure = models.TextField(null=True)
    floorNumber = models.TextField(null=True)
    yearBuilt = models.TextField()
    totalUnits = models.TextField(null=True)
    landRights = models.TextField(null=True)
    zoning = models.TextField(null=True)
    managementCompany = models.TextField(null=True)
    managementForm = models.TextField(null=True)
    manager = models.TextField(null=True)
    managementFee = models.TextField(null=True)
    repairReserveFund = models.TextField(null=True)
    otherFees = models.TextField(null=True)
    parking = models.TextField(null=True)
    currentStatus = models.TextField(null=True)
    deliveryDate = models.TextField(null=True)
    transactionMode = models.TextField(null=True)
    remarks = models.TextField(null=True)
    updateDate = models.TextField(null=True)
    nextUpdateDate = models.TextField(null=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pageUrl = ""
        self.propertyName = ""
        self.priceStr = ""
        self.price = 0
        self.address = ""
        self.traffic = ""
        self.madori = ""
        self.senyuMensekiStr = ""
        self.senyuMenseki = 0
        self.balconyArea = ""
        self.facing = ""
        self.otherArea = ""
        self.structure = ""
        self.floorNumber = ""
        self.yearBuilt = ""
        self.totalUnits = ""
        self.landRights = ""
        self.zoning = ""
        self.managementCompany = ""
        self.managementForm = ""
        self.manager = ""
        self.managementFee = ""
        self.repairReserveFund = ""
        self.otherFees = ""
        self.parking = ""
        self.currentStatus = ""
        self.deliveryDate = ""
        self.transactionMode = ""
        self.remarks = ""
        self.updateDate = ""
        self.nextUpdateDate = ""

    class Meta:
        db_table = "nomura_mansion"

class NomuraKodate(models.Model):
    pageUrl = models.CharField(max_length=500, db_index=True)
    propertyName = models.TextField()
    priceStr = models.TextField()
    price = models.IntegerField()
    address = models.TextField()
    traffic = models.TextField()
    landArea = models.TextField()
    buildingArea = models.TextField()
    structure = models.TextField(null=True)
    yearBuilt = models.TextField(null=True)
    parking = models.TextField(null=True)
    landRights = models.TextField(null=True)
    landCategory = models.TextField(null=True) # 地目
    privateRoadBurden = models.TextField(null=True)
    setback = models.TextField(null=True)
    cityPlanning = models.TextField(null=True)
    zoning = models.TextField(null=True)
    buildingCoverageRatio = models.TextField(null=True) # 建ぺい率
    floorAreaRatio = models.TextField(null=True) # 容積率
    roadAccess = models.TextField(null=True)
    facilities = models.TextField(null=True)
    currentStatus = models.TextField(null=True)
    deliveryDate = models.TextField(null=True)
    transactionMode = models.TextField(null=True)
    remarks = models.TextField(null=True)
    updateDate = models.TextField(null=True)
    nextUpdateDate = models.TextField(null=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pageUrl = ""
        self.propertyName = ""
        self.priceStr = ""
        self.price = 0
        self.address = ""
        self.traffic = ""
        self.landArea = ""
        self.buildingArea = ""
        self.structure = ""
        self.yearBuilt = ""
        self.parking = ""
        self.landRights = ""
        self.landCategory = ""
        self.privateRoadBurden = ""
        self.setback = ""
        self.cityPlanning = ""
        self.zoning = ""
        self.buildingCoverageRatio = ""
        self.floorAreaRatio = ""
        self.roadAccess = ""
        self.facilities = ""
        self.currentStatus = ""
        self.deliveryDate = ""
        self.transactionMode = ""
        self.remarks = ""
        self.updateDate = ""
        self.nextUpdateDate = ""

    class Meta:
        db_table = "nomura_kodate"

class NomuraTochi(models.Model):
    pageUrl = models.CharField(max_length=500, db_index=True)
    propertyName = models.TextField()
    priceStr = models.TextField()
    price = models.IntegerField()
    address = models.TextField()
    traffic = models.TextField()
    landArea = models.TextField()
    landRights = models.TextField(null=True)
    landCategory = models.TextField(null=True)
    privateRoadBurden = models.TextField(null=True)
    setback = models.TextField(null=True)
    cityPlanning = models.TextField(null=True)
    zoning = models.TextField(null=True)
    buildingCoverageRatio = models.TextField(null=True)
    floorAreaRatio = models.TextField(null=True)
    roadAccess = models.TextField(null=True)
    facilities = models.TextField(null=True)
    currentStatus = models.TextField(null=True)
    deliveryDate = models.TextField(null=True)
    transactionMode = models.TextField(null=True)
    remarks = models.TextField(null=True)
    updateDate = models.TextField(null=True)
    nextUpdateDate = models.TextField(null=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pageUrl = ""
        self.propertyName = ""
        self.priceStr = ""
        self.price = 0
        self.address = ""
        self.traffic = ""
        self.landArea = ""
        self.landRights = ""
        self.landCategory = ""
        self.privateRoadBurden = ""
        self.setback = ""
        self.cityPlanning = ""
        self.zoning = ""
        self.buildingCoverageRatio = ""
        self.floorAreaRatio = ""
        self.roadAccess = ""
        self.facilities = ""
        self.currentStatus = ""
        self.deliveryDate = ""
        self.transactionMode = ""
        self.remarks = ""
        self.updateDate = ""
        self.nextUpdateDate = ""

    class Meta:
        db_table = "nomura_tochi"

