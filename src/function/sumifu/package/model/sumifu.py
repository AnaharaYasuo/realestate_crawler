from django.db import models

# Create your models here.


class SumifuMansion(models.Model):
    # unique_id = models.CharField(max_length=100, null=True)
    propertyName = models.TextField()
    pageUrl = models.TextField()
    inputDate = models.DateField()
    inputDateTime = models.DateTimeField()
    priceStr = models.TextField()
    price = models.IntegerField()
    madori = models.TextField()
    senyuMensekiStr = models.TextField()
    senyuMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    floorType = models.TextField()  
    chikunengetsuStr = models.TextField()
    chikunengetsu = models.DateField()
    address = models.TextField()

    transfer1 = models.TextField()
    railway1 = models.TextField()
    station1 = models.TextField()
    railwayWalkMinute1Str = models.TextField()
    railwayWalkMinute1 = models.IntegerField()
    busStation1 = models.TextField()
    busWalkMinute1Str = models.TextField()
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
    hikiwatashi = models.TextField()
    genkyo = models.TextField()
    tyusyajo = models.TextField()
    tochikenri = models.TextField()
    #追加項目
    kaisu  = models.TextField()
    kouzou  = models.TextField()
    address1 = models.TextField()
    address2 = models.TextField()
    address3 = models.TextField()
    addressKyoto = models.TextField()
    sonotaHiyouStr  = models.TextField()
    bunjoKaisya  = models.TextField()
    sekouKaisya  = models.TextField()
    torihiki  = models.TextField()
    biko  = models.TextField()

    floorType_kai = models.IntegerField()
    floorType_chijo = models.IntegerField()
    floorType_chika = models.IntegerField()
    floorType_kouzou = models.TextField()
    kyutaishin = models.IntegerField()
    railwayCount = models.IntegerField()
    busUse1 = models.IntegerField()
    barukoniMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    senyouNiwaMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    roofBarukoniMenseki = models.DecimalField(max_digits=6,decimal_places=3)
    kanrihi_p_heibei = models.DecimalField(max_digits=7,decimal_places=3)
    syuzenTsumitate_p_heibei = models.DecimalField(max_digits=7,decimal_places=3)

            
    def __init__(self, *args, **kwargs):
        super(SumifuMansion, self).__init__(*args, **kwargs)
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
        managed = False
        