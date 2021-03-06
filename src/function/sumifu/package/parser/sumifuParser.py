# -*- coding: utf-8 -*-
import sys
from package.model.sumifu import SumifuMansion
import importlib
importlib.reload(sys)
from decimal import Decimal
import datetime
import traceback
import re
from builtins import IndexError
from concurrent.futures._base import TimeoutError
from package.parser.baseParser import ParserBase, LoadPropertyPageException, \
    ReadPropertyNameException
import logging


class SumifuMansionParser(ParserBase):

    def __init__(self, params):
        ""
        
    def getCharset(self):
        return "CP932"

    async def parseRegionPage(self, response):

        def getXpath():
            return u'//a[contains(@href,"/mansion/area_")]/@href'

        def getDestUrl(linkUrl):
            return 'https://www.stepon.co.jp' + linkUrl
        
        async for destUrl in self._parsePageCore(response, getXpath, getDestUrl):
            yield destUrl

    async def parseAreaPage(self, response):

        def getXpath():
            return u'//a[contains(@href,"/mansion/area_") and contains(@href,"/list_") and contains(text(),"（")]/@href'

        def getDestUrl(linkUrl):
            return 'https://www.stepon.co.jp' + linkUrl + "?limit=1000&mode=2"
            # return 'https://www.stepon.co.jp' + linkUrl + "?limit=10000&mode=2"
        
        async for destUrl in self._parsePageCore(response, getXpath, getDestUrl):
            yield destUrl

    async def parsePropertyListPage(self, response):

        def getXpath():
            return u'//*[@id="searchResultBlock"]/div/div/div/div[1]/*//label/h2/a/@href'

        def getDestUrl(linkUrl):
            return linkUrl
        
        async for destUrl in self._parsePageCore(response, getXpath, getDestUrl):
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

    async def parsePropertyDetailPage(self, session, url):
        item = SumifuMansion()
        # url="https://www.stepon.co.jp/mansion/detail_10393001/" #for test
        try:
            item.pageUrl = url
            response = await self.getResponseBs(session, url)
            item = self.__parsePropertyDetailPage(item, response)
        except (LoadPropertyPageException, TimeoutError) as e:
            raise e
        except (ReadPropertyNameException) as e:
            raise e
        except Exception as e:
            logging.error('Detail parse error:' + url)
            logging.error(traceback.format_exc())
            raise e
        return item
    
    def __parsePropertyDetailPage(self, item, response):
        try:
            item.propertyName = response.find_all("div", id="bukkenNameBlockIcon")[0].find_all("h2")[0].find_all("span")[1].contents[0]
        except Exception:
            raise ReadPropertyNameException()
        item.priceStr = response.find_all("dl", id="s_summaryPrice")[0].find_all("dd")[0].find_all("p")[0].find_all("em")[0].contents[0]
        priceUnit = response.find_all("dl", id="s_summaryPrice")[0].find_all("dd")[0].find_all("p")[0].contents[1]

        priceWork = item.priceStr.replace(',', '')
        oku = 0
        man = 0
        if (u"億" in item.priceStr) or (u"億" in priceUnit):
            priceArr = priceWork.split("億")
            oku = int(priceArr[0]) * 10000
            if len(priceArr) > 1 and len(priceArr[1]) != 0:
                man = int(priceArr[1])
        else:
            man = int(priceWork)
        price = oku + man
        item.price = price

        item.madori = response.find_all("dl", id="s_summaryMadori")[0].find_all("dd")[0].find_all("em")[0].string
        item.senyuMensekiStr = response.find_all("dl", id="s_summarySenyuMenseki")[0].find_all("dd")[0].contents[0]
        senyuMensekiWork = item.senyuMensekiStr.replace('m', '')
        item.senyuMenseki = Decimal(senyuMensekiWork)
        try:
            item.floorType = str(response.find_all("dl", id="s_summaryFloor")[0].find_all("dd")[0].contents[0])
            if((item.floorType.count(u'部分') > 1) 
               or (item.floorType.count(u'／') > 1)
               or (item.floorType.count(u'建') > 1)
               or (item.floorType.count(u'・') > 1)
               or (item.floorType.count(u'造') > 1)
               or (item.floorType[-1:]!="造" and item.floorType[-1:]!="他")
               ):
                logging.info("item.floorType is " + item.floorType)
                raise LoadPropertyPageException()

            try:
                item.floorType_kai = int(item.floorType.split(u"部分")[0].split(u"階")[0].replace(u"地下", "-"))  # 新規項目
                item.floorType_chijo = int(item.floorType.split(u"地上")[1].split(u"階")[0])
                item.floorType_chika = 0
                if(len(item.floorType.split(u"地下")) > 1):
                    item.floorType_chika = int(item.floorType.split(u"地下")[1].split(u"階")[0])
            except ValueError:
                logging.warn("ValueError item.floorType is " + item.floorType)
            
        except IndexError:
            logging.warn(traceback.format_exc())
            raise LoadPropertyPageException()
        item.chikunengetsuStr = response.find_all("dl", id="s_summaryChikunengetsu")[0].find_all("dd")[0].contents[0]
        if (item.chikunengetsuStr == u"築年月不詳"):
            nen = 1900
            tsuki = 1
        else:
            nen = int(item.chikunengetsuStr.split(u"年")[0])
            tsuki = int(item.chikunengetsuStr.split(u"年")[1].split(u"月")[0])
        item.chikunengetsu = datetime.date(nen, tsuki, 1)
        item.address = response.find_all("div", id="bukkenDetailBlock")[0].find_all("div")[1].find_all("dl")[5].find_all("dd")[0].contents[0]

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

# <dd id="s_summaryTransfer">
#    <a href="/mansion/rail_13/station_70_2311/">小田急小田原線</a>「
#    <a href="/mansion/rail_13/list_02311140/">成城学園前</a>」駅よりバス5  分「ＮＴＴ中央研修センタ」バス停徒歩4  分<br>
#    <a href="/mansion/rail_13/station_60_2301/">京王線</a>「
#    <a href="/mansion/rail_13/list_02301140/">つつじヶ丘    </a>」駅よりバス11 分「ＮＴＴ中央研修センタ」バス停徒歩4  分<br>
#    <a href="/mansion/rail_13/station_60_2301/">京王線</a>「
#    <a href="/mansion/rail_13/list_02301130/">仙川</a>」駅よりバス2  分「稲荷前」バス停徒歩9  分
# </dd>
        for i in response.select("br"):
            i.replace_with("\n")  # brタグを改行コードに変換
        transferList = re.split("\n", response.select('dd[id="s_summaryTransfer"]')[0].text)
        transList = response.select('dd[id="s_summaryTransfer"]>a')
        item.railwayCount = int(len(transList) // 2)
        for i in range(item.railwayCount):
            try:                    
                railway = response.select('dd[id="s_summaryTransfer"]>a:nth-child(' + str(i * 2 + 1) + ')')[0].contents[0]  # 東海道本線
                station = response.select('dd[id="s_summaryTransfer"]>a:nth-child(' + str(i * 2 + 2) + ')')[0].contents[0]  # 戸塚
                transfer = transferList[i].replace(" ", "")  # 「東海道本線戸塚」駅よりバス10分「上矢部」バス停徒歩6分
                wkTransferList = transfer.split("」駅より")
                walkStr = "」駅より" + wkTransferList[1]  # 」駅よりバス10分「上矢部」バス停徒歩6分
                if i == 0:
                    item.transfer1, item.railway1, item.station1, item.railwayWalkMinute1Str, item.railwayWalkMinute1, item.busStation1, item.busWalkMinute1Str, item.busWalkMinute1 = self.__getRailWayPropertyValues(transfer, railway, station, walkStr)
                elif i == 1:
                    item.transfer2, item.railway2, item.station2, item.railwayWalkMinute2Str, item.railwayWalkMinute2, item.busStation2, item.busWalkMinute2Str, item.busWalkMinute2 = self.__getRailWayPropertyValues(transfer, railway, station, walkStr)
                elif i == 1:
                    item.transfer3, item.railway3, item.station3, item.railwayWalkMinute3Str, item.railwayWalkMinute3, item.busStation3, item.busWalkMinute3Str, item.busWalkMinute3 = self.__getRailWayPropertyValues(transfer, railway, station, walkStr)
                elif i == 1:
                    item.transfer4, item.railway4, item.station4, item.railwayWalkMinute4Str, item.railwayWalkMinute4, item.busStation4, item.busWalkMinute4Str, item.busWalkMinute4 = self.__getRailWayPropertyValues(transfer, railway, station, walkStr)
                elif i == 1:
                    item.transfer5, item.railway5, item.station5, item.railwayWalkMinute5Str, item.railwayWalkMinute5, item.busStation5, item.busWalkMinute5Str, item.busWalkMinute5 = self.__getRailWayPropertyValues(transfer, railway, station, walkStr)
            except IndexError:
                logging.warn("transfer:" + transfer)
                raise LoadPropertyPageException()

        for i, tr in enumerate(response.find_all("div", id="detailBlock")[0].find_all("tr")):
            for j, th in enumerate(tr.find_all("th")):
                thTitle = th.contents[0]
                try:
                    tdValue = tr.find_all("td")[j].contents[0]
                except:
                    tdValue = ""
                    logging.warn("tdValue is empty. thTitle is " + thTitle)
                if thTitle == "バルコニー（テラス）面積":
                    item.barukoniMensekiStr = tdValue
                if thTitle == "採光方向":
                    item.saikouKadobeya = tdValue
                    temp = item.saikouKadobeya.split(u"／")
                    if len(temp) == 1:
                        item.saikou = item.saikouKadobeya
                        item.kadobeya = ""
                    else:
                        item.saikou = temp[0]
                        item.kadobeya = temp[1]
                if thTitle == "総戸数":
                    item.soukosuStr = tdValue
                    item.soukosu = int(item.soukosuStr.replace(u"戸", "").strip())
                if thTitle == "管理方式／管理会社":
                    item.kanriKeitaiKaisya = tdValue
                    temp = item.kanriKeitaiKaisya.split(u"／")
                    if len(temp) == 1:
                        item.kanriKeitai = temp[0]
                        item.kanriKaisya = ""
                    else:
                        item.kanriKeitai = temp[0]
                        item.kanriKaisya = temp[1]
                if thTitle == "管理費(月額)":
                    item.kanrihiStr = tdValue
                    if "-" in item.kanrihiStr:
                        item.kanrihi = 0
                    else:
                        item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"円", ""))
                if thTitle == "修繕積立金(月額)":
                    item.syuzenTsumitateStr = tdValue
                    if "-" in item.syuzenTsumitateStr:
                        item.syuzenTsumitate = 0
                    else:
                        item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"円", ""))
                if thTitle == "引渡時期":
                    item.hikiwatashi = tdValue
                if thTitle == "現況":
                    item.genkyo = tdValue
                if thTitle == "駐車場":
                    item.tyusyajo = tdValue
                if thTitle == "土地権利":
                    item.tochikenri = tdValue
                if thTitle == "施工会社":
                    item.sekouKaisya = tdValue
                if thTitle == "取引態様":
                    item.torihiki = tdValue
                if thTitle == "備考":
                    item.biko = ""

        # 不要項目
        item.kaisu = ""
        item.kouzou = ""
        item.address1 = ""
        item.address2 = ""
        item.address3 = ""
        item.addressKyoto = ""
        item.sonotaHiyouStr = ""
        item.bunjoKaisya = ""
        
        if(item.floorType.count(u"・ＲＣ造") > 0):
            item.floorType_kouzou = "ＲＣ造"
        if(item.floorType.count(u"・ＳＲＣ造") > 0):
            item.floorType_kouzou = "ＳＲＣ造"
        if(item.floorType.count(u"・Ｓ造") > 0):
            item.floorType_kouzou = "Ｓ造"
        if(item.floorType.count(u"・木造") > 0):
            item.floorType_kouzou = "木造"
        if(item.floorType.count(u"・その他") > 0):
            item.floorType_kouzou = "その他"

        item.kyutaishin = 0
        if(item.chikunengetsu < datetime.date(1982, 1, 1)):
            item.kyutaishin = 1
        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1
            
        item.barukoniMenseki = 0
        if item.barukoniMensekiStr != "--":
            barukoniMenseki = item.barukoniMensekiStr.split(u"／")[0].split(u"専用庭面積")[0].split(u"ルーフバルコニー面積")[0].split(u"m")[0].strip()
            if(len(barukoniMenseki) > 0):
                item.barukoniMenseki = Decimal(barukoniMenseki)

        item.senyouNiwaMenseki = 0
        senyouNiwaList = item.barukoniMensekiStr.split(u"専用庭面積")
        if(len(senyouNiwaList) > 1):
            item.senyouNiwaMenseki = Decimal(senyouNiwaList[1].split(u"m")[0])
        
        item.roofBarukoniMenseki = 0
        roofList = item.barukoniMensekiStr.split(u"ルーフバルコニー面積")
        if(len(roofList) > 1):
            item.roofBarukoniMenseki = Decimal(roofList[1].split(u"m")[0])

        item.kanrihi_p_heibei = item.kanrihi / item.senyuMenseki
        item.syuzenTsumitate_p_heibei = item.syuzenTsumitate / item.senyuMenseki

        return item

    def __getTransferText(self, transList1, transList2, i):
        sum_transfer = transList1[i] + self.__getRailwayText(transList2, i) + self.__getRailwayStationText(transList2, i) + transList1[i + 1].replace(' ', '')
        return sum_transfer

    def __getRailwayText(self, transList2, i):
        return transList2[i]

    def __getRailwayStationText(self, transList2, i):
        return transList2[i + 1]

    def __getBusStationText(self, walkStr):
        if u"バス" in walkStr:
            return walkStr[walkStr.find(u"「") + 1:walkStr.rfind(u"」")]
        return ""

    def __getWalkMinute(self, walkStr):
        return walkStr[walkStr.find(u"徒歩") + 2:walkStr.rfind(u"分")].replace(' ', '')

    def __getRailwayWalkText(self, walkStr):
        if u"バス" in walkStr:
            return "0"
        return self.__getWalkMinute(walkStr)

    def __getBusWalkText(self, walkStr):
        if u"バス" in walkStr:
            return self.__getWalkMinute(walkStr)
        return "0"
    
    def __getRailWayPropertyValues(self, _transfer, _railway, _station, _walkStr):
        try:
            _railwayWalkMinuteStr = self.__getRailwayWalkText(_walkStr)
            _railwayWalkMinute = int(_railwayWalkMinuteStr)
            _busStation = self.__getBusStationText(_walkStr)
            _busWalkMinuteStr = self.__getBusWalkText(_walkStr)
            _busWalkMinute = int(_busWalkMinuteStr)
            return _transfer, _railway, _station, _railwayWalkMinuteStr, _railwayWalkMinute, _busStation, _busWalkMinuteStr, _busWalkMinute
        except ValueError as e:
            logging.warn(traceback.format_exc())
            raise LoadPropertyPageException()
        except Exception as e:
            logging.error("error __getRailWayPropertyValues:" + _walkStr)
            logging.error("error __getRailWayPropertyValues:" + _railwayWalkMinuteStr)
            raise e

    def __getPropertyValues(self, transList1, transList2, i):
        _transfer1 = self.__getTransferText(transList1, transList2, i)
        _railway1 = self.__getRailwayText(transList2, i)
        _station1 = self.__getRailwayStationText(transList2, i)
        _railwayWalkMinute1Str = self.__getRailwayWalkText(transList1[i + 1])
        if len(_railwayWalkMinute1Str) > 0:
            _railwayWalkMinute1 = int(_railwayWalkMinute1Str)
        _busStation1 = self.__getBusStationText(transList1[i + 1])
        _busWalkMinute1Str = self.__getBusWalkText(transList1[i + 1])
        _busWalkMinute1 = 0
        if len(_busWalkMinute1Str) > 0:
            _busWalkMinute1 = int(_busWalkMinute1Str)

        return _transfer1, _railway1, _station1, _railwayWalkMinute1Str, _railwayWalkMinute1, _busStation1, _busWalkMinute1Str, _busWalkMinute1
