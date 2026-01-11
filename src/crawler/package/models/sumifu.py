from django.db import models

# Create your models here.

class SumifuModel(models.Model):
    propertyName = models.TextField()
    pageUrl = models.TextField()
    inputDate = models.DateField()
    inputDateTime = models.DateTimeField()    
    priceStr = models.TextField()
    price = models.IntegerField()
    address = models.TextField()
    transfer1 = models.TextField()
    railway1 = models.TextField()
    station1 = models.TextField()
    railwayWalkMinute1Str = models.TextField()
    railwayWalkMinute1 = models.IntegerField()
    busStation1 = models.TextField()
    busWalkMinute1Str = models.TextField()
    busWalkMinute1 = models.IntegerField()
    
    transfer2 = models.TextField()
    railway2 = models.TextField()
    station2 = models.TextField()
    railwayWalkMinute2Str = models.TextField()
    railwayWalkMinute2 = models.IntegerField()
    busStation2 = models.TextField()
    busWalkMinute2Str = models.TextField()
    busWalkMinute2 = models.IntegerField()
    
    transfer3 = models.TextField()
    railway3 = models.TextField()
    station3 = models.TextField()
    railwayWalkMinute3Str = models.TextField()
    railwayWalkMinute3 = models.IntegerField()
    busStation3 = models.TextField()
    busWalkMinute3Str = models.TextField()
    busWalkMinute3 = models.IntegerField()
    
    transfer4 = models.TextField()
    railway4 = models.TextField()
    station4 = models.TextField()
    railwayWalkMinute4Str = models.TextField()
    railwayWalkMinute4 = models.IntegerField()
    busStation4 = models.TextField()
    busWalkMinute4Str = models.TextField()
    busWalkMinute4 = models.IntegerField()

    transfer5 = models.TextField()
    railway5 = models.TextField()
    station5 = models.TextField()
    railwayWalkMinute5Str = models.TextField()
    railwayWalkMinute5 = models.IntegerField()
    busStation5 = models.TextField()
    busWalkMinute5Str = models.TextField()
    busWalkMinute5 = models.IntegerField()
    hikiwatashi = models.TextField()
    genkyo = models.TextField()
    tochikenri = models.TextField()
    torihiki  = models.TextField()
    biko  = models.TextField()

    address1 = models.TextField()
    address2 = models.TextField()
    address3 = models.TextField()
    addressKyoto = models.TextField()
    railwayCount = models.IntegerField()
    busUse1 = models.IntegerField()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.propertyName = ""        
        self.pageUrl = ""
        self.inputDate = None
        self.inputDateTime = None
        self.priceStr = ""
        self.price = 0
        self.address = ""
    
        self.transfer1 = ""
        self.railway1 = ""
        self.station1 = ""
        self.railwayWalkMinute1Str = ""
        self.railwayWalkMinute1 = 0
        self.busStation1 = ""
        self.busWalkMinute1Str = ""
        self.busWalkMinute1Str = ""
        self.busWalkMinute1 = 0

        self.transfer2 = ""
        self.railway2 = ""
        self.station2 = ""
        self.railwayWalkMinute2Str = ""
        self.railwayWalkMinute2 = 0
        self.busStation2 = ""
        self.busWalkMinute2Str = ""
        self.busWalkMinute2 = 0

        self.transfer3 = ""
        self.railway3 = ""
        self.station3 = ""
        self.railwayWalkMinute3Str = ""
        self.railwayWalkMinute3 = 0
        self.busStation3 = ""
        self.busWalkMinute3Str = ""
        self.busWalkMinute3 = 0

        self.transfer4 = ""
        self.railway4 = ""
        self.station4 = ""
        self.railwayWalkMinute4Str = ""
        self.railwayWalkMinute4 = 0
        self.busStation4 = ""
        self.busWalkMinute4Str = ""
        self.busWalkMinute4 = 0
    
        self.transfer5 = ""
        self.railway5 = ""
        self.station5 = ""
        self.railwayWalkMinute5Str = ""
        self.railwayWalkMinute5 = 0
        self.busStation5 = ""
        self.busWalkMinute5Str = ""
        self.busWalkMinute5 = 0

        self.hikiwatashi = ""
        self.genkyo = ""
        self.tochikenri = ""
        self.torihiki  = ""
        self.biko  = ""
    #追加項目
        self.address1 = ""
        self.address2 = ""
        self.address3 = ""
        self.addressKyoto = ""
        self.railwayCount = 0
        self.busUse1 = 0
    class Meta:
        abstract = True
        
class SumifuInvestment(models.Model):
    # Basic Info
    propertyName = models.TextField()
    pageUrl = models.TextField(unique=True)
    inputDate = models.DateField()
    inputDateTime = models.DateTimeField()
    updatedAt = models.DateField(null=True)
    nextUpdateAt = models.DateField(null=True)
    
    # Investment Info
    priceStr = models.TextField()
    price = models.IntegerField(null=True)
    grossYield = models.DecimalField(max_digits=5, decimal_places=2, null=True) # 想定利回り
    annualRent = models.IntegerField(null=True) # 年間想定賃料等
    monthlyRent = models.IntegerField(null=True) # 月額賃料等
    currentStatus = models.TextField(null=True) # 現在の賃貸状況 (満室/賃貸中/空室 etc)
    
    # Property Type & Location
    propertyType = models.TextField() # マンション（区分）, マンション（一棟） etc
    address = models.TextField()
    traffic = models.TextField(null=True) # 交通
    
    # Building / Land Details
    landArea = models.DecimalField(max_digits=10, decimal_places=2, null=True) # 土地面積
    buildingArea = models.DecimalField(max_digits=10, decimal_places=2, null=True) # 建物面積/専有面積
    structure = models.TextField(null=True) # 構造/階数
    yearBuilt = models.TextField(null=True) # 築年月
    
    # Detailed Specs (Nullable as they depend on type)
    totalUnits = models.IntegerField(null=True) # 総戸数
    floorPlan = models.TextField(null=True) # 間取り
    balconyArea = models.DecimalField(max_digits=6, decimal_places=2, null=True) # バルコニー面積
    managementFee = models.IntegerField(null=True) # 管理費
    repairReserve = models.IntegerField(null=True) # 修繕積立金
    
    # Land Specific
    kenpei = models.IntegerField(null=True) # 建ぺい率
    youseki = models.IntegerField(null=True) # 容積率
    zoning = models.TextField(null=True) # 用途地域
    landRights = models.TextField(null=True) # 土地権利

    class Meta:
        db_table = "sumifu_investment"

class SumifuMansion(SumifuModel):
    madori = models.TextField()
    senyuMensekiStr = models.TextField()
    senyuMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    floorType = models.TextField()  
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField()

    barukoniMensekiStr = models.TextField()
    saikouKadobeya = models.TextField()
    saikou = models.TextField()
    kadobeya = models.TextField()
    soukosuStr = models.TextField()
    soukosu = models.IntegerField()
    kanriKeitaiKaisya = models.TextField()
    kanriKeitai = models.TextField()
    kanriKaisya = models.TextField()
    kanrihiStr = models.TextField()
    kanrihi = models.IntegerField()
    syuzenTsumitateStr = models.TextField()
    syuzenTsumitate = models.IntegerField()
    tyusyajo = models.TextField()
    #追加項目
    kaisu  = models.TextField()
    kouzou  = models.TextField()
    sonotaHiyouStr  = models.TextField()
    bunjoKaisya  = models.TextField()
    sekouKaisya  = models.TextField()

    floorType_kai = models.IntegerField()
    floorType_chijo = models.IntegerField()
    floorType_chika = models.IntegerField()
    floorType_kouzou = models.TextField()
    kyutaishin = models.IntegerField()

    barukoniMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    senyouNiwaMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    roofBarukoniMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    kanrihi_p_heibei = models.DecimalField(max_digits=7,decimal_places=3)
    syuzenTsumitate_p_heibei = models.DecimalField(max_digits=7,decimal_places=3)
            
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.propertyName = ""        
        self.pageUrl = ""
        self.inputDate = None
        self.inputDateTime = None
        self.priceStr = ""
        self.price = 0
        self.madori = ""
        self.senyuMensekiStr = ""
        self.senyuMenseki = 0
        self.floorType = ""  
        self.chikunengetsuStr = ""
        self.chikunengetsu = None
        self.address = ""
    
        self.transfer1 = ""
        self.railway1 = ""
        self.station1 = ""
        self.railwayWalkMinute1Str = ""
        self.railwayWalkMinute1 = 0
        self.busStation1 = ""
        self.busWalkMinute1Str = ""
        self.busWalkMinute1Str = ""
        self.busWalkMinute1 = 0

        self.transfer2 = ""
        self.railway2 = ""
        self.station2 = ""
        self.railwayWalkMinute2Str = ""
        self.railwayWalkMinute2 = 0
        self.busStation2 = ""
        self.busWalkMinute2Str = ""
        self.busWalkMinute2 = 0

        self.transfer3 = ""
        self.railway3 = ""
        self.station3 = ""
        self.railwayWalkMinute3Str = ""
        self.railwayWalkMinute3 = 0
        self.busStation3 = ""
        self.busWalkMinute3Str = ""
        self.busWalkMinute3 = 0

        self.transfer4 = ""
        self.railway4 = ""
        self.station4 = ""
        self.railwayWalkMinute4Str = ""
        self.railwayWalkMinute4 = 0
        self.busStation4 = ""
        self.busWalkMinute4Str = ""
        self.busWalkMinute4 = 0
    
        self.transfer5 = ""
        self.railway5 = ""
        self.station5 = ""
        self.railwayWalkMinute5Str = ""
        self.railwayWalkMinute5 = 0
        self.busStation5 = ""
        self.busWalkMinute5Str = ""
        self.busWalkMinute5 = 0
    
        self.barukoniMensekiStr = ""
        self.saikouKadobeya = ""
        self.saikou = ""
        self.kadobeya = ""
        self.soukosuStr = ""
        self.soukosu = 0
        self.kanriKeitaiKaisya = ""
        self.kanriKeitai = ""
        self.kanriKaisya = ""
        self.kanrihiStr = ""
        self.kanrihi = 0
        self.syuzenTsumitateStr = ""
        self.syuzenTsumitate = 0
        self.hikiwatashi = ""
        self.genkyo = ""
        self.tyusyajo = ""
        self.tochikenri = ""
    #追加項目
        self.kaisu  = ""
        self.kouzou  = ""
        self.address1 = ""
        self.address2 = ""
        self.address3 = ""
        self.addressKyoto = ""
        self.sonotaHiyouStr  = ""
        self.bunjoKaisya  = ""
        self.sekouKaisya  = ""
        self.torihiki  = ""
        self.biko  = ""
        
        self.floorType_kai = 0
        self.floorType_chijo = 0
        self.floorType_chika = 0
        self.floorType_kouzou = ""
        self.kyutaishin = 0
        self.railwayCount = 0
        self.busUse1 = 0
        self.barukoniMenseki = 0
        self.senyouNiwaMenseki = 0
        self.roofBarukoniMenseki = 0
        self.kanrihi_p_heibei = 0
        self.syuzenTsumitate_p_heibei = 0

    class Meta:
        db_table = "sumifu_mansion"

        abstract = False

class SumifuTochi(SumifuModel):
    tochiMensekiStr = models.TextField()
    tochiMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    chimokuChisei = models.TextField()
    chimoku = models.TextField()
    chisei = models.TextField()
    setsudou = models.TextField()
    douro = models.TextField()
    douroMuki = models.TextField()
    douroHaba = models.DecimalField(max_digits=6,decimal_places=3)
    douroKubun = models.TextField()
    setsumen = models.DecimalField(max_digits=6,decimal_places=3)
    kenpeiYousekiStr = models.TextField()
    kenpei = models.IntegerField()
    youseki = models.IntegerField()
    chiikiChiku = models.TextField()
    kuiki = models.TextField()
    youtoChiiki = models.TextField()
    boukaChiiki = models.TextField()
    saikenchiku = models.TextField()
    sonotaChiiki = models.TextField()
    kenchikuJoken = models.TextField()
    kokudoHou = models.TextField()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tochiMensekiStr = ""
        self.tochiMenseki = 0
        self.chimokuChisei = ""
        self.chimoku = ""
        self.chisei = ""
        self.setsudou = ""
        self.douro = ""
        self.douroMuki = ""
        self.douroHaba = 0
        self.douroKubun = ""
        self.setsumen = 0

        self.kenpeiStr = ""
        self.kenpei = 0
        self.yousekiStr = ""
        self.youseki = 0
        self.chiikiChiku = ""
        self.kuiki = ""
        self.youtoChiiki = ""
        self.boukaChiiki = ""
        self.saikenchiku = ""
        self.sonotaChiiki = ""
        self.kenchikuJoken = ""
        self.kokudoHou = ""

    class Meta:
        db_table = "sumifu_tochi"

        abstract = False    

class SumifuKodate(SumifuModel):
    tochiMensekiStr = models.TextField()
    tochiMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    tatemonoMensekiStr = models.TextField()
    tatemonoMenseki = models.DecimalField(max_digits=8,decimal_places=3)
    madori = models.TextField()
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField()
    kaisuKouzou  = models.TextField()
    kaisu  = models.TextField()
    kouzou  = models.TextField()
    chimokuChisei = models.TextField()
    chimoku = models.TextField()
    chisei = models.TextField()
    setsudou = models.TextField()
    douro = models.TextField()
    douroMuki = models.TextField()
    douroHaba = models.DecimalField(max_digits=6,decimal_places=3)
    douroKubun = models.TextField()
    setsumen = models.DecimalField(max_digits=6,decimal_places=3)
    kenpeiYousekiStr = models.TextField()
    kenpei = models.IntegerField()
    youseki = models.IntegerField()
    chiikiChiku = models.TextField()

    kuiki = models.TextField()
    youtoChiiki = models.TextField()
    boukaChiiki = models.TextField()
    saikenchiku = models.TextField()
    sonotaChiiki = models.TextField()
    tyusyajo = models.TextField()
    kokudoHou = models.TextField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tochiMensekiStr = ""
        self.tochiMenseki = 0
        self.tatemonoMensekiStr = ""
        self.tatemonoMenseki = 0
        self.madori = ""
        self.chikunengetsuStr = ""
        self.chikunengetsu = None
        self.kaisuKouzou  = ""
        self.kaisu  = ""
        self.kouzou  = ""
        self.tyusyajo = ""
        self.chimokuChisei = ""
        self.chimoku = ""
        self.chisei = ""
        self.setsudou = ""
        self.douro = ""
        self.douroMuki = ""
        self.douroHaba = 0
        self.douroKubun = ""
        self.setsumen = 0

        self.kenpeiYousekiStr = ""
        self.kenpei = 0
        self.youseki = 0
        self.chiikiChiku = ""
        self.kuiki = ""
        self.youtoChiiki = ""
        self.boukaChiiki = ""
        self.saikenchiku = ""
        self.sonotaChiiki = ""
        self.tyusyajo = ""
        self.kokudoHou = ""


    class Meta:
        db_table = "sumifu_kodate"

        abstract = False
