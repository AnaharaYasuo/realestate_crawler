# -*- coding: utf-8 -*-
import sys
from tokenize import String
import unicodedata

from bs4 import BeautifulSoup
from package.model.mitsui import MitsuiKodate, MitsuiMansion, MitsuiTochi
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
import re


class MitsuiParser(ParserBase):
    BASE_URL='https://www.rehouse.co.jp'

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
            #yield destUrl
            yield destUrl +"city/"

    def getAreaXpath(self):
        return u''

    def getAreaDestUrl(self,linkUrl):
        return  self.BASE_URL + linkUrl + "?limit=1000"

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
            return u'//*[@id="__layout"]/div/div/div/main/section[2]/div[2]/a[contains(@class,"button-pagination-prev-next pagination-next ml-16")]/@href'

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
            item.propertyName = response.find_all("h1", class_="headline1 mb-4")[0].contents[0].strip()
        except Exception:
            raise ReadPropertyNameException()

        for i, tr in enumerate(response.find_all("tr",class_="table-row")):
            thTitle = tr.find_all("td")[0].contents[0]
            try:
                tdValue = tr.find_all("td")[1].find_all("span")[0].contents[0]
                tdValue = tdValue.strip()
                # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
            except:
                tdValue = ""
                logging.warn("error. tdValue is empty. thTitle is " + thTitle)

            if thTitle == u"価格":
                tdValue = tr.find_all("td")[1].find_all("p")[0].contents[0]
                item.priceStr = tdValue            
                priceWork = item.priceStr.replace(',', '')
                oku = 0
                man = 0
                if (u"億" in item.priceStr):
                    priceArr = priceWork.split(u"億")
                    oku = int(priceArr[0]) * 10000
                    if len(priceArr) > 1 and len(priceArr[1]) != 0:
                        man = int(priceArr[1].replace(u'万', '').replace(u'円', ''))
                else:
                    man = int(priceWork.replace(u'万', '').replace(u'円', ''))
                price = oku + man
                item.price = price
                
            elif thTitle == u"所在地":
                item.address1 = tr.find_all("td")[1].find_all("p")[0].find_all("span")[0].contents[0]
                item.address2 = tr.find_all("td")[1].find_all("p")[0].find_all("span")[1].find_all("a")[0].contents[0]
                item.address3 = tr.find_all("td")[1].find_all("p")[0].find_all("span")[2].contents[0]
                item.address = item.address1+item.address2+item.address3

            elif thTitle == u"最寄り駅":
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
        
                item.railwayCount = 0
                tdValue = tr.find_all("td")[1].contents[0]
                for j, p in enumerate(tr.find_all("td")[1].find_all("div")[0].find_all("p")):
                    transfer = ""
                    railway = p.find_all("span")[0].contents[0].strip()
                    station = p.find_all("span")[1].find_all("a")[0].contents[0].strip()
                    other = p.find_all("span")[2].contents[0].strip()
                    transfer=railway+station+other
                    item.railwayCount += 1
                    if(other.find(u"バス")>-1):
                        railwayWalkMinuteStr = ""
                        railwayWalkMinute = 0
                        busMinute=other.split(u" ")[0].strip()
                        busStation = other.split(u" ")[1].strip()
                        busWalkMinuteStr = other.split(u" ")[2].strip().split(u"停歩")[1].strip()
                        busWalkMinute = int(busWalkMinuteStr.replace(u"分", ""))
                    else:
                        railwayWalkMinuteStr=other
                        railwayWalkMinute = railwayWalkMinuteStr.replace(u"徒歩", "").replace(u"分", "")
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
                    
            elif thTitle == u"引渡時期":
                item.hikiwatashi = tdValue

            elif thTitle == u"現況":
                item.genkyo = tdValue

            elif thTitle == u"土地権利":
                item.tochikenri = tdValue
                
            elif thTitle == u"その他費用":
                item.sonotaHiyouStr = tdValue  # 新規
                
            elif thTitle == u"取引態様":
                item.torihiki = tdValue  # 新規
                
            elif thTitle == u"備考":
                item.biko = tdValue  # 新規
                    
        # 不要項目
        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1

        return item

    def _getSetudouText(self, item, value):
        item.setsudou=value
        for wkStr in item.setsudou.split(u"、"):
            douroHabaObj = re.search(r'[0-9\.]+', wkStr.split(u"ｍ")[0])
            if (douroHabaObj!=None and float(douroHabaObj.group())>float(item.douroHaba)):#複数ある場合、一番道路幅が広い面を
                item.douroHaba = douroHabaObj.group()
                item.douroKubun = wkStr.split(u"ｍ")[1].replace(u"(","").replace(u")","").strip()
                item.douroMuki = wkStr[0:(douroHabaObj.start())].split(u"：")[0]
                item.setsumen = 0

    def _getKenpeiText(self, item, value):
        if(value.find(u"前面道路幅員により")>-1 and value.find(u"前面道路幅員により前面道路幅員")==-1):
            s:String = value.split(u"前面道路幅員により")[1].split(u"％")[0]
            s=unicodedata.normalize("NFKD", s)
            sObj = re.search(r'[0-9\.]+', s)
            item.kenpei=sObj.group()
        else:
            item.kenpei = value.split("%")[0]

    def _getYousekiText(self, item, value):
        if(value.find(u"前面道路幅員により")>-1 and value.find(u"前面道路幅員により前面道路幅員")==-1):
            s:String = value.split(u"前面道路幅員により")[1].split("％")[0]
            s=unicodedata.normalize("NFKD", s)
            sObj = re.search(r'[0-9\.]+', s)
            item.youseki = sObj.group()
        else:
            item.youseki = value.split("%")[0]


class MitsuiMansionParser(MitsuiParser):

    def getRootXpath(self):
        #return u'//div/a[contains(@href,"/sitemap/buy/") and contains(@href, "-mansion/")]/@href'
        return u'//li/a[contains(@href,"/buy/mansion/prefecture/")]/@href'

    def getAreaXpath(self):
        #return u'//a[contains(@href,"https://www.rehouse.co.jp/list/area/mansion/")]/@href'
        return u'//a[contains(@href,"/buy/mansion/prefecture/") and contains(@href, "city/") and @class="link"]/@href'

    def getPropertyListXpath(self):
        # "https://www.rehouse.co.jp/mansion/bkdetail/FWRX7A04/"
        #return u'//a[contains(@href,"https://www.rehouse.co.jp/mansion/bkdetail/")]/@href'
        return u'//a[contains(@href,"/buy/mansion/bkdetail/") and not (contains(@href, "/inquiry/input/"))]/@href'

    def createEntity(self):
        return  MitsuiMansion()
    
    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        for i, tr in enumerate(response.find_all("tr",class_="table-row")):
            thTitle = tr.find_all("td")[0].contents[0]
            try:
                tdValue = tr.find_all("td")[1].find_all("span")[0].contents[0]
                tdValue = tdValue.strip()
                # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
            except:
                tdValue = ""
                logging.warn("error. tdValue is empty. thTitle is " + thTitle)

            if thTitle == u"間取り":
                item.madori = tdValue

            elif thTitle == u"専有面積":
                item.senyuMensekiStr = tdValue
                senyuMensekiWork = item.senyuMensekiStr.split(u'㎡')[0]
                item.senyuMenseki = Decimal(senyuMensekiWork)
                
            elif thTitle == u"階数 / 階建":  # 6階／地上13階建
                item.kaisu = tdValue  # 新規項目

            elif thTitle == u"建物構造":
                item.kouzou = tdValue  # 新規項目

            elif thTitle == u"築年月":
                item.chikunengetsuStr = tdValue
                if (item.chikunengetsuStr == u"不詳"):
                    nen = 1900
                    tsuki = 1
                else:
                    nen = int(item.chikunengetsuStr.split(u"年")[0])
                    tsuki = int(item.chikunengetsuStr.split(u"年")[1].split(u"月")[0])
                item.chikunengetsu = datetime.date(nen, tsuki, 1)

                    
            elif thTitle == u"バルコニー":
                item.barukoniMensekiStr = tdValue

            elif thTitle == u"向き":
                item.saikou = tdValue

            elif thTitle == u"総戸数":
                item.soukosuStr = tdValue
                item.soukosu = 0
                if(item.soukosuStr != "-"):
                    item.soukosu = int(item.soukosuStr.replace(u",", "").replace(u"戸", "").strip())

            elif thTitle == u"管理会社":
                item.kanriKaisya = tdValue
                
            elif thTitle == u"管理方式":
                item.kanriKeitai = tdValue

            elif thTitle == u"管理費等":
                item.kanrihiStr = tdValue
                if "-" in item.kanrihiStr:
                    item.kanrihi = 0
                else:
                    item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"円", ""))
            elif thTitle == u"修繕積立金":
                item.syuzenTsumitateStr = tdValue
                if "-" in item.syuzenTsumitateStr:
                    item.syuzenTsumitate = 0
                else:
                    item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"円", ""))

            elif thTitle == u"駐車場":
                item.tyusyajo = tdValue

            elif thTitle == u"分譲会社":
                item.bunjoKaisya = tdValue.replace(u" (新築分譲時における売主)", "")  # 新規
                
            elif thTitle == u"施工会社":
                item.sekouKaisya = tdValue  # 新規
                                        
        # 不要項目
        item.floorType = ""
        item.saikouKadobeya = ""
        item.kadobeya = ""
        item.kanriKeitaiKaisya = ""
        
        item.floorType_kai = int(item.kaisu.split(u"階 / ")[0].replace(u"地下", "-").strip())  # 新規項目
        item.floorType_chijo = int(item.kaisu.split(u" / 地上")[1].split(u" 地下")[0].replace(u"階", "").replace(u"建", ""))
        floorType_chika = 0
        if(len(item.kaisu.split(u" 地下")) > 1):
            floorType_chika = int(item.kaisu.split(u" 地下")[1].replace(u"階", "").replace(u"建", ""))
        item.floorType_chika = floorType_chika
        if(item.kouzou == u"鉄筋コンクリート造"):
            item.floorType_kouzou = "ＲＣ造"
        elif(item.kouzou == u"鉄骨鉄筋コンクリート造"):
            item.floorType_kouzou = "ＳＲＣ造"
        elif(item.kouzou == u"鉄骨造"):
            item.floorType_kouzou = "Ｓ造"
        elif(item.kouzou == u"木造"):
            item.floorType_kouzou = "木造"
        item.kyutaishin = 0
        if(item.chikunengetsu < datetime.date(1982, 1, 1)):
            item.kyutaishin = 1
        item.barukoniMenseki = 0
        if item.barukoniMensekiStr != "-":
            item.barukoniMenseki = item.barukoniMensekiStr.replace(u"㎡", "")
        item.senyouNiwaMenseki = 0
        item.roofBarukoniMenseki = 0
        item.kanrihi_p_heibei = item.kanrihi / item.senyuMenseki
        item.syuzenTsumitate_p_heibei = item.syuzenTsumitate / item.senyuMenseki

        return item

class MitsuiTochiParser(MitsuiParser):
    def getRootXpath(self):
        #return u'//div/a[contains(@href,"/sitemap/buy/") and contains(@href, "-tochi/")]/@href'
        return u'//li/a[contains(@href,"/buy/tochi/prefecture/")]/@href'

    def getAreaXpath(self):
        #return u'//a[contains(@href,"https://www.rehouse.co.jp/list/area/tochi/")]/@href'
        return u'//a[contains(@href,"/buy/tochi/prefecture/") and contains(@href, "city/") and @class="link"]/@href'

    def getPropertyListXpath(self):
        #return u'//a[contains(@href,"https://www.rehouse.co.jp/tochi/bkdetail/")]/@href'
        return u'//a[contains(@href,"/buy/tochi/bkdetail/") and not (contains(@href, "/inquiry/input/"))]/@href'


    def createEntity(self):
        return  MitsuiTochi()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)

        for i, tr in enumerate(response.find_all("tr",class_="table-row")):
            thTitle = tr.find_all("td")[0].contents[0]
            try:
                tdValue = tr.find_all("td")[1].find_all("span")[0].contents[0]
                tdValue = tdValue.strip()
                # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
            except:
                tdValue = ""
                logging.warn("error. tdValue is empty. thTitle is " + thTitle)

            if thTitle == u"土地面積":
                item.tochiMensekiStr = tdValue
                item.tochiMenseki = Decimal(item.tochiMensekiStr.replace(",","").split("㎡")[0].strip())

            elif thTitle == u"建築条件":
                item.kenchikuJoken = tdValue

            elif thTitle == u"地目":
                item.chimoku = tdValue

            elif thTitle == u"接道状況":
                self._getSetudouText(item,tdValue)

            elif thTitle == u"建ぺい率":
                self._getKenpeiText(item,tdValue)

            elif thTitle == u"容積率":
                self._getYousekiText(item,tdValue)

            elif thTitle == u"用途地域":
                item.youtoChiiki = tdValue
            elif thTitle == u"都市計画":
                item.kuiki = tdValue
            elif thTitle == u"国土法届出要否":
                item.kokudoHou = tdValue

        return item

class MitsuiKodateParser(MitsuiParser):
    def getRootXpath(self):
        #return u'//div/a[contains(@href,"/sitemap/buy/") and contains(@href, "-kodate/")]/@href' 以前のレイアウト
        return u'//li/a[contains(@href,"/buy/kodate/prefecture/")]/@href'

    def getAreaXpath(self):
        #return u'//a[contains(@href,"https://www.rehouse.co.jp/list/area/kodate/")]/@href'
        return u'//a[contains(@href,"/buy/kodate/prefecture/") and contains(@href, "city/") and @class="link"]/@href'

    def getPropertyListXpath(self):
        #return u'//a[contains(@href,"https://www.rehouse.co.jp/kodate/bkdetail/")]/@href'
        return u'//a[contains(@href,"/buy/kodate/bkdetail/") and not (contains(@href, "/inquiry/input/"))]/@href'
    
    def createEntity(self):
        return  MitsuiKodate()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)

        for i, tr in enumerate(response.find_all("tr",class_="table-row")):
            thTitle = tr.find_all("td")[0].contents[0]
            try:
                tdValue = tr.find_all("td")[1].find_all("span")[0].contents[0]
                tdValue = tdValue.strip()
                # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
            except:
                tdValue = ""
                logging.warn("error. tdValue is empty. thTitle is " + thTitle)

            if thTitle == u"建物面積":
                item.tatemonoMensekiStr = tdValue
                item.tatemonoMenseki = Decimal(item.tatemonoMensekiStr.replace(",","").split("㎡")[0].strip())

            elif thTitle == u"土地面積":
                item.tochiMensekiStr = tdValue
                item.tochiMenseki = Decimal(item.tochiMensekiStr.replace(",","").split("㎡")[0].strip())

            elif thTitle == u"建物構造":
                item.kaisuKouzou  = tdValue
                if(item.kaisuKouzou.find(u"その他")>-1):
                    item.kouzou=u"その他"
                    item.kaisu = item.kaisuKouzou.split(u"その他")[1].strip()
                elif(item.kaisuKouzou.find(u"-")>-1):
                    item.kouzou=u"-"
                else:
                    item.kouzou = item.kaisuKouzou.split(u"造")[0].strip()+u"造"
                    item.kaisu  = item.kaisuKouzou.split(u"造")[1].strip()

            elif thTitle == u"駐車場":
                item.tyusyajo = tdValue

            elif thTitle == u"地目":
                item.chimoku = tdValue

            elif thTitle == u"接道状況":
                self._getSetudouText(item,tdValue)

            elif thTitle == u"建ぺい率":
                self._getKenpeiText(item,tdValue)

            elif thTitle == u"容積率":
                self._getYousekiText(item,tdValue)

            elif thTitle == u"用途地域":
                item.youtoChiiki = tdValue

            elif thTitle == u"都市計画":
                item.kuiki = tdValue

        return item

