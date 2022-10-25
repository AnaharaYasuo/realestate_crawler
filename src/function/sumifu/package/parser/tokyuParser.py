# -*- coding: utf-8 -*-
import sys

from bs4 import BeautifulSoup
from package.model.tokyu import TokyuMansion
import importlib
importlib.reload(sys)
from decimal import Decimal
import datetime
import traceback
from concurrent.futures._base import TimeoutError
from package.parser.baseParser import LoadPropertyPageException, \
    ReadPropertyNameException, ParserBase
from bs4.element import NavigableString, Tag
import logging

class TokyuParser(ParserBase):
    BASE_URL='https://www.livable.co.jp'
    def __init__(self, params):
        ""
        
    def getCharset(self):
        return "utf-8"

    def createEntity(self):
        pass

    def getRootXpath(self):
        return u''

    def getRootDestUrl(self,linkUrl):
        return self.BASE_URL +  linkUrl

    async def parseRootPage(self, response):
        async for destUrl in self._parsePageCore(response, self.getRootXpath, self.getRootDestUrl):
            yield destUrl

    def getAreaXpath(self):
        return u''

    def getAreaDestUrl(self,linkUrl):
        return  self.BASE_URL + linkUrl

    async def parseAreaPage(self, response):        
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield destUrl

    def getPropertyListXpath(self):
        return u''

    def getPropertyListDestUrl(self,linkUrl):
        return self.BASE_URL+linkUrl

    async def parsePropertyListPage(self, response):
        
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    async def getPropertyListNextPageUrl(self, response):

        def getNextPageXpath():
            return u'(//div[@class="m-page-navigation__inner"])[1]/a[@class="m-page-navigation__next iconfont-livable-arrow_right"]/@href'

        def getDestUrl(linkUrl):
            return self.BASE_URL + linkUrl

        def _parsePageCore(self, response, getXpath , getDestUrl):
            destUrl = response.xpath(getXpath())
            return self.BASE_URL + destUrl

        logging.info("getPropertyListNextPageUrl")
        linkUrlList = response.xpath(getNextPageXpath())
        if (len(linkUrlList) > 0):
            linkUrl = linkUrlList[0]
            return getDestUrl(linkUrl)
        return ""

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            item.propertyName = response.find("h1", class_="o-detail-header__headline o-detail-header__headline--match").contents[0]
        except Exception:
            raise ReadPropertyNameException()
        item.railwayCount = 0
        for i, tr in enumerate(response.find_all("div", class_="m-status-table__wrapper")[1].find_all("dl")):
            for j, th in enumerate(tr.find_all("dt")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("dd")[j].contents[0]
                    tdValue = tdValue.strip()
                    # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
                except:
                    tdValue = ""
                    logging.warn("error. tdValue is empty. thTitle is " + thTitle)

                if thTitle == u"価格":
                    tdValue = tr.find("dd").find("p").find("span").text
                    item.priceStr = tdValue            
                    priceWork = item.priceStr.replace(',', '')
                    oku = 0
                    man = 0
                    if (u"億" in item.priceStr):
                        priceArr = priceWork.split(u"億")
                        oku = int(priceArr[0]) * 10000
                        if len(priceArr) > 1 and len(priceArr[1]) != 0:
                            man = Decimal(priceArr[1].replace(u'万', '').replace(u'円', '').replace(u"（消費税込）", ""))
                            man = int(round(man))
                    else:
                        man = Decimal(priceWork.replace(u'万', '').replace(u'円', '').replace(u"（消費税込）", ""))
                        man = int(round(man))
                    price = oku + man
                    item.price = price

                if thTitle == u"所在地":
                    item.address1 = tr.find("dd").find_all("a")[0].text  # 新規項目
                    item.address2 = tr.find("dd").find_all("a")[1].text
                    item.address3 = tr.find("dd").find_all("a")[2].text
                    item.addressKyoto = ""  # 不要
                    item.address = item.address1 + item.address2 + item.address3

                if thTitle == u"交通":
                    item.transfer1 = ""
                    item.railway1 = ""
                    item.station1 = ""
                    item.railwayWalkMinute1Str = ""
                    item.railwayWalkMinute1 = 0
                    item.busStation1 = ""
                    item.busWalkMinute1Str = ""
                    item.busWalkMinute1 = 0
            
                    item.transfer2 = ""
                    item.railway2 = ""
                    item.station2 = ""
                    item.railwayWalkMinute2Str = ""
                    item.railwayWalkMinute2 = 0
                    item.busStation2 = ""
                    item.busWalkMinute2Str = ""
                    item.busWalkMinute2 = 0
            
                    item.transfer3 = ""
                    item.railway3 = ""
                    item.station3 = ""
                    item.railwayWalkMinute3Str = ""
                    item.railwayWalkMinute3 = 0
                    item.busStation3 = ""
                    item.busWalkMinute3Str = ""
                    item.busWalkMinute3 = 0
            
                    item.transfer4 = ""
                    item.railway4 = ""
                    item.station4 = ""
                    item.railwayWalkMinute4Str = ""
                    item.railwayWalkMinute4 = 0
                    item.busStation4 = ""
                    item.busWalkMinute4Str = ""
                    item.busWalkMinute4 = 0
            
                    item.transfer5 = ""
                    item.railway5 = ""
                    item.station5 = ""
                    item.railwayWalkMinute5Str = ""
                    item.railwayWalkMinute5 = 0
                    item.busStation5 = ""
                    item.busWalkMinute5Str = ""
                    item.busWalkMinute5 = 0
            
                    for j, element in enumerate(tr.find("dd").find_all("span")):   
                        value = element.contents[0]
                        if(type(element.contents[0]) == NavigableString):
                            value = str(element.contents[0])
                        if(type(element.contents[0]) == Tag):
                            value = str(element.contents[0].string)
                            
                        if (j % 3 == 0):
                            item.railwayCount += 1
                            railway = value
                            transfer = value
                        elif (j % 3 == 1):
                            station = value.replace(u"「", "").replace(u"」駅", "")
                            transfer = transfer + value
                        elif (j % 3 == 2):
                            transfer = transfer + value
                            if (value.find(u"バス") > -1):  # 中央線 「武蔵小金井」駅 バス11分 「はなの木通り」停 徒歩4分
                                railwayWalkMinuteStr = ""
                                railwayWalkMinute = 0
                                busStation = value.split(u"「")[1].split(u"」")[0]
                                busWalkMinuteStr = value.split(u"停 ")[1]
                                busWalkMinute = int(busWalkMinuteStr.replace(u"徒歩", "").replace(u"分", ""))
                            elif(value.find(u"「") > -1):  # 福知山線 「新三田」駅 「中央公園前」下車 徒歩1分
                                railwayWalkMinuteStr = ""
                                railwayWalkMinute = 0
                                busStation = value.split(u"「")[1].split(u"」")[0].strip()
                                busWalkMinuteStr = value.split(u"下車 ")[1].strip()
                                busWalkMinute = int(busWalkMinuteStr.replace(u"徒歩", "").replace(u"分", ""))
                            else:  # 京都市烏丸線 「烏丸御池」駅 徒歩6分
                                railwayWalkMinuteStr = value
                                railwayWalkMinute = int(railwayWalkMinuteStr.replace(u"徒歩", "").replace(u"分", ""))
                                busStation = ""
                                busWalkMinuteStr = ""
                                busWalkMinute = 0

                            if item.railwayCount == 1:
                                item.transfer1, item.railway1, item.station1, item.railwayWalkMinute1Str, item.railwayWalkMinute1, item.busStation1, item.busWalkMinute1Str, item.busWalkMinute1 = transfer, railway, station, railwayWalkMinuteStr, railwayWalkMinute, busStation, busWalkMinuteStr, busWalkMinute                      
                            if item.railwayCount == 2:
                                item.transfer2, item.railway2, item.station2, item.railwayWalkMinute2Str, item.railwayWalkMinute2, item.busStation2, item.busWalkMinute2Str, item.busWalkMinute2 = transfer, railway, station, railwayWalkMinuteStr, railwayWalkMinute, busStation, busWalkMinuteStr, busWalkMinute                      
                            if item.railwayCount == 3:
                                item.transfer3, item.railway3, item.station3, item.railwayWalkMinute3Str, item.railwayWalkMinute3, item.busStation3, item.busWalkMinute3Str, item.busWalkMinute3 = transfer, railway, station, railwayWalkMinuteStr, railwayWalkMinute, busStation, busWalkMinuteStr, busWalkMinute                      
                            if item.railwayCount == 4:
                                item.transfer4, item.railway4, item.station4, item.railwayWalkMinute4Str, item.railwayWalkMinute4, item.busStation4, item.busWalkMinute4Str, item.busWalkMinute4 = transfer, railway, station, railwayWalkMinuteStr, railwayWalkMinute, busStation, busWalkMinuteStr, busWalkMinute                      
                            if item.railwayCount == 5:
                                item.transfer5, item.railway5, item.station5, item.railwayWalkMinute5Str, item.railwayWalkMinute5, item.busStation5, item.busWalkMinute5Str, item.busWalkMinute5 = transfer, railway, station, railwayWalkMinuteStr, railwayWalkMinute, busStation, busWalkMinuteStr, busWalkMinute                      
                        
                if thTitle == u"引渡時期":
                    item.hikiwatashi = tdValue

                if thTitle == u"現況":
                    item.genkyo = tdValue

                if thTitle == u"土地権利":
                    item.tochikenri = tdValue
                    
                if thTitle == u"その他費用":
                    item.sonotaHiyouStr = tdValue  # 新規
                    
                if thTitle == u"取引態様":
                    item.torihiki = tdValue  # 新規
                    
                if thTitle == u"備考":
                    item.biko = tdValue  # 新規
        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1
        return item
    
class TokyuMansionParser(TokyuParser):

    def getRootXpath(self):
        return u'//a[contains(@href,"/kounyu/chuko-mansion/") and contains(@href, "/select-area/")]/@href'

    def getAreaXpath(self):
        return u'//a[contains(@href,"/kounyu/chuko-mansion/") and contains(@href, "/a") and not(contains(@href, "/select-town"))]/@href'

    def getPropertyListXpath(self):
        return u'//a[@class="o-product-list__menu-link rec_detail_link" and contains(@href,"/mansion/")]/@href'

    def createEntity(self):
        return  TokyuMansion()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:TokyuMansion=super()._parsePropertyDetailPage(item, response)

        item.railwayCount = 0
        for i, tr in enumerate(response.find_all("div", class_="m-status-table__wrapper")[1].find_all("dl")):
            for j, th in enumerate(tr.find_all("dt")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("dd")[j].contents[0]
                    tdValue = tdValue.strip()
                    # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
                except:
                    tdValue = ""
                    logging.warn("error. tdValue is empty. thTitle is " + thTitle)


                if thTitle == u"間取り":
                    item.madori = tdValue

                if thTitle == u"専有面積":
                    item.senyuMensekiStr = tdValue
                    senyuMensekiWork = item.senyuMensekiStr.replace(u'内法', '').replace(u'壁芯', '').replace(u'm', '')
                    item.senyuMenseki = Decimal(senyuMensekiWork)
                    
                if thTitle == u"所在階数":  # u'2階 / 地上8階 地下1階'
                    item.kaisu = tdValue
                    item.floorType_kai = int(item.kaisu.split(u"階・")[0].split(u"階 / ")[0].replace(u"地下", "-").strip())  # 新規項目
                    item.floorType_chijo = int(item.kaisu.split(u"地上")[1].split(u" 地下")[0].replace(u"階", "").replace(u"建", ""))
                    floorType_chika = 0
                    if(len(item.kaisu.split(u" 地下")) > 1):
                        floorType_chika = int(item.kaisu.split(u" 地下")[1].replace(u"階", "").replace(u"建", ""))
                    item.floorType_chika = floorType_chika

                if thTitle == u"建物構造":
                    item.kouzou = tdValue  # 鉄筋コンクリート造

                if thTitle == u"築年月":  # u1998年3月
                    item.chikunengetsuStr = tdValue
                    if (item.chikunengetsuStr == u"不詳"):
                        nen = 1900
                        tsuki = 1
                    else:
                        nen = int(item.chikunengetsuStr.split(u"年")[0])
                        tsuki = int(item.chikunengetsuStr.split(u"年")[1].split(u"月")[0])
                    item.chikunengetsu = datetime.date(nen, tsuki, 1)
                        
                if thTitle == u"バルコニー":
                    item.barukoniMensekiStr = tdValue

                if thTitle == u"向き":
                    item.saikou = tdValue

                if thTitle == u"総戸数":
                    item.soukosuStr = tdValue
                    item.soukosu = 0
                    if(item.soukosuStr != "-"):
                        item.soukosu = int(item.soukosuStr.replace(u",", "").replace(u"戸", "").strip())

                if thTitle == u"管理会社":
                    item.kanriKaisya = tdValue.replace(u" / ", "").replace(u"全部委託", "")
                    
                if thTitle == u"管理方式":
                    item.kanriKeitai = tdValue

                if thTitle == u"管理費":
                    item.kanrihiStr = tdValue
                    if "-" in item.kanrihiStr:
                        item.kanrihi = 0
                    else:
                        item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"（円/月）", ""))
                if thTitle == u"修繕積立金":
                    item.syuzenTsumitateStr = tdValue
                    if "-" in item.syuzenTsumitateStr:
                        item.syuzenTsumitate = 0
                    else:
                        item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"（円/月）", ""))

                if thTitle == u"駐車場":
                    item.tyusyajo = tdValue

                if thTitle == u"分譲会社":
                    item.bunjoKaisya = tdValue.replace(u"（新築分譲時における売主）", "")  # 新規
                    
                if thTitle == u"施工会社":
                    item.sekouKaisya = tdValue  # 新規

        # 不要項目
        item.floorType = ""
        item.saikouKadobeya = ""
        item.kadobeya = ""
        item.kanriKeitaiKaisya = ""
        
        if(item.kouzou == u"鉄筋コンクリート造"):
            item.floorType_kouzou = "ＲＣ造"
        if(item.kouzou == u"鉄骨鉄筋コンクリート造"):
            item.floorType_kouzou = "ＳＲＣ造"
        if(item.kouzou == u"鉄骨造"):
            item.floorType_kouzou = "Ｓ造"
        if(item.kouzou == u"木造"):
            item.floorType_kouzou = "木造"
        item.kyutaishin = 0
        if(item.chikunengetsu < datetime.date(1982, 1, 1)):
            item.kyutaishin = 1
        item.barukoniMenseki = 0
        if item.barukoniMensekiStr != "-":
            item.barukoniMenseki = item.barukoniMensekiStr.replace(u"m", "")
        item.senyouNiwaMenseki = 0
        item.roofBarukoniMenseki = 0
        item.kanrihi_p_heibei = item.kanrihi / item.senyuMenseki
        item.syuzenTsumitate_p_heibei = item.syuzenTsumitate / item.senyuMenseki

        return item
