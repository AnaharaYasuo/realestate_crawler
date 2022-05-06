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
            yield destUrl

    def getAreaXpath(self):
        return u''

    def getAreaDestUrl(self,linkUrl):
        return linkUrl + "?limit=1000"
        # "https://www.rehouse.co.jp/list/area/mansion/syutoken/tokyo/13-101/?limit=100"

    async def parseAreaPage(self, response):        
        async for destUrl in self._parsePageCore(response, self.getAreaXpath, self.getAreaDestUrl):
            yield destUrl

    def getPropertyListXpath(self):
        return u''

    def getPropertyListDestUrl(self,linkUrl):
        return linkUrl

    async def parsePropertyListPage(self, response):
        
        async for destUrl in self._parsePageCore(response, self.getPropertyListXpath, self.getPropertyListDestUrl):
            yield destUrl

    async def getPropertyListNextPageUrl(self, response):
        logging.info("getPropertyListNextPageUrl")
        # 次のページをひらくURLを取得数
        nextPageXpath = '//*[@id="searchCondition"]/div/div[2]/div[2]/div[1]/ul/li[last()]/a'
        nextPageTag = response.xpath(nextPageXpath)
        if(len(nextPageTag) == 0):  # 複数のページが存在しない場合
            return None
        elif(nextPageTag[0].text != "次へ"):  # 最後が"次へ"ではない場合(すでに最終ページを開いている場合)
            return None
        nextPageUrl = 'https://www.stepon.co.jp' + nextPageTag[0].get("href")
        logging.info("getPropertyListNextPageUrl nextPageUrl:" + nextPageUrl)
        return nextPageUrl

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            item.propertyName = response.find_all("span", class_="mrh-heading2-article__title")[0].contents[0]
        except Exception:
            raise ReadPropertyNameException()

        for i, tr in enumerate(response.find_all("div", id="info")[0].find_all("tr")):
            for j, th in enumerate(tr.find_all("th")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("td")[j].contents[0]
                    tdValue = tdValue.strip()
                    # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
                except:
                    tdValue = ""
                    logging.warn("error. tdValue is empty. thTitle is " + thTitle)

                if thTitle == u"価格":
                    tdValue = tr.find_all("td")[j].find_all("span")[0].contents[0]
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
                    addressSplit = tdValue.split(u"　")
                    addressFrontSplit = addressSplit[0].split("\xa0")
                    item.address1 = addressFrontSplit[0]  # 新規項目
                    if(len(addressFrontSplit) > 1):
                        item.address2 = addressFrontSplit[1]  # 新規項目
                    if(len(addressFrontSplit) > 2):
                        item.address3 = addressFrontSplit[2]  # 新規項目
                    if(len(addressSplit) == 2):
                        item.addressKyoto = addressSplit[1]  # 新規項目
                    item.address = tdValue.replace("\xa0", "").replace(u"　", "")

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
                    for i, content in enumerate(tr.find_all("td")[j].contents):
                        value = content
                        if(type(content) == NavigableString):
                            value = str(content)
                        if(type(content) == Tag):
                            value = str(content.string)
                        if((u"「") in value and not (u"」") in value):
                        # if(value.contains(u"「") and not value.contains(u"」停")):
                            item.railwayCount += 1
                            transfer = tr.find_all("td")[j].contents[i].strip() + tr.find_all("td")[j].contents[1 + i].contents[0].strip() + tr.find_all("td")[j].contents[2 + i].strip()
                            railway = tr.find_all("td")[j].contents[i].replace(u"「", "").strip()
                            station = tr.find_all("td")[j].contents[1 + i].contents[0].strip()
                            
                            busSprit = tr.find_all("td")[j].contents[2 + i].split(u"」駅 バス")

                            if(len(busSprit) > 1):  # 」駅 バス17分 「武蔵野北高校」 停歩2分
                                railwayWalkMinuteStr = ""
                                railwayWalkMinute = 0
                                busStation = busSprit[1].split(u"「")[1].split(u"」 停歩")[0].strip()
                                busWalkMinuteStr = busSprit[1].split(u"」 停歩")[1].strip()
                                busWalkMinute = int(busWalkMinuteStr.replace(u"分", ""))
                            else:
                                railwayWalkMinuteStr = tr.find_all("td")[j].contents[2 + i].replace(u"」駅", "").strip()
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
        for wkStr in item.setsudou.split(u","):
            douroHabaObj = re.search(r'[0-9\.]+', wkStr.split("M")[0])
            if (douroHabaObj!=None and float(douroHabaObj.group())>float(item.douroHaba)):#複数ある場合、一番道路幅が広い面を
                item.douroHaba = douroHabaObj.group()
                item.douroKubun = wkStr.split("M")[1]
                item.douroMuki = wkStr[0:(douroHabaObj.start())]
                item.setsumen = 0

    def _getKenpeiText(self, item, value):
        if(value.find(u"前面道路幅員により")>-1 and value.find(u"前面道路幅員により前面道路幅員")==-1):
            s:String = value.split(u"前面道路幅員により")[1].split("％")[0]
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
        # "https://www.rehouse.co.jp/sitemap/buy/syutoken/tokyo-mansion/"
        return u'//div/a[contains(@href,"/sitemap/buy/") and contains(@href, "-mansion/")]/@href'

    def getAreaXpath(self):
        # "https://www.rehouse.co.jp/list/area/mansion/syutoken/tokyo/13-101/"
        return u'//a[contains(@href,"https://www.rehouse.co.jp/list/area/mansion/")]/@href'

    def getPropertyListXpath(self):
        # "https://www.rehouse.co.jp/mansion/bkdetail/FWRX7A04/"
        return u'//a[contains(@href,"https://www.rehouse.co.jp/mansion/bkdetail/")]/@href'

    def createEntity(self):
        return  MitsuiMansion()
    
    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            item.propertyName = response.find_all("span", class_="mrh-heading2-article__title")[0].contents[0]
        except Exception:
            raise ReadPropertyNameException()

        for i, tr in enumerate(response.find_all("div", id="info")[0].find_all("tr")):
            for j, th in enumerate(tr.find_all("th")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("td")[j].contents[0]
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
                    
                elif thTitle == u"階数／階建":  # 6階／地上13階建
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

                        
                elif thTitle == u"バルコニー面積":
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
                    item.kanrihiStr = tr.find_all("td")[j].contents[0]
                    if "-" in item.kanrihiStr:
                        item.kanrihi = 0
                    else:
                        item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"円／月", ""))
                elif thTitle == u"修繕積立金":
                    item.syuzenTsumitateStr = tr.find_all("td")[j].contents[0]
                    if "-" in item.syuzenTsumitateStr:
                        item.syuzenTsumitate = 0
                    else:
                        item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"円／月", ""))

                elif thTitle == u"駐車場":
                    item.tyusyajo = tdValue

                elif thTitle == u"分譲会社":
                    item.bunjoKaisya = tdValue.replace(u"（新築分譲時における売主）", "")  # 新規
                    
                elif thTitle == u"施工会社":
                    item.sekouKaisya = tdValue  # 新規
                                        
        # 不要項目
        item.floorType = ""
        item.saikouKadobeya = ""
        item.kadobeya = ""
        item.kanriKeitaiKaisya = ""
        
        item.floorType_kai = int(item.kaisu.split(u"階／")[0].replace(u"地下", "-").strip())  # 新規項目
        item.floorType_chijo = int(item.kaisu.split(u"／地上")[1].split(u" 地下")[0].replace(u"階", "").replace(u"建", ""))
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
        # "https://www.rehouse.co.jp/sitemap/buy/syutoken/tokyo-mansion/"
        return u'//div/a[contains(@href,"/sitemap/buy/") and contains(@href, "-tochi/")]/@href'

    def getAreaXpath(self):
        # "https://www.rehouse.co.jp/list/area/mansion/syutoken/tokyo/13-101/"
        return u'//a[contains(@href,"https://www.rehouse.co.jp/list/area/tochi/")]/@href'

    def getPropertyListXpath(self):
        # "https://www.rehouse.co.jp/mansion/bkdetail/FWRX7A04/"
        return u'//a[contains(@href,"https://www.rehouse.co.jp/tochi/bkdetail/")]/@href'
    
    def createEntity(self):
        return  MitsuiTochi()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            item.propertyName = response.find_all("span", class_="mrh-heading2-article__title")[0].contents[0]
        except Exception:
            raise ReadPropertyNameException()

        for i, tr in enumerate(response.find_all("div", id="info")[0].find_all("tr")):
            for j, th in enumerate(tr.find_all("th")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("td")[j].contents[0]
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
        return u'//div/a[contains(@href,"/sitemap/buy/") and contains(@href, "-kodate/")]/@href'

    def getAreaXpath(self):
        return u'//a[contains(@href,"https://www.rehouse.co.jp/list/area/kodate/")]/@href'

    def getPropertyListXpath(self):
        return u'//a[contains(@href,"https://www.rehouse.co.jp/kodate/bkdetail/")]/@href'
    
    def createEntity(self):
        return  MitsuiKodate()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            item.propertyName = response.find_all("span", class_="mrh-heading2-article__title")[0].contents[0]
        except Exception:
            raise ReadPropertyNameException()

        for i, tr in enumerate(response.find_all("div", id="info")[0].find_all("tr")):
            for j, th in enumerate(tr.find_all("th")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("td")[j].contents[0]
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

