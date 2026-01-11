# -*- coding: utf-8 -*-
import sys

from bs4 import BeautifulSoup
from package.models.tokyu import TokyuMansion, TokyuTochi, TokyuKodate, TokyuInvestment
from package.parser.investmentParser import InvestmentParser
from django.db import models
import re
from package.utils import converter
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
from package.utils.selector_loader import SelectorLoader

class TokyuParser(ParserBase):
    BASE_URL='https://www.livable.co.jp'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('tokyu', self.property_type)
        
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
        logging.info("getPropertyListNextPageUrl")
        next_page_xpath = self.selectors.get('next_page_xpath')
        linkUrlList = response.xpath(next_page_xpath)
        if (len(linkUrlList) > 0):
            linkUrl = linkUrlList[0]
            return self.BASE_URL + linkUrl
        return ""

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            title_selector = self.selectors.get('title')
            h1 = response.select_one(title_selector)
            if h1 and h1.contents:
                item.propertyName = h1.contents[0]
            else:
                logging.warn("Could not find property name")
                item.propertyName = "" # Default
        except Exception:
             logging.error("Error parsing property name")
             raise ReadPropertyNameException()
        item.railwayCount = 0
        
        table_config = self.selectors.get('table', {})
        table_selector = table_config.get('selector', 'div.m-status-table__wrapper')
        dl_selector = table_config.get('dl_selector', 'dl')
        header_selector = table_config.get('header', 'dt')
        value_selector = table_config.get('value', 'dd')

        wrappers = response.select(table_selector)
        target_wrapper = wrappers[1] if len(wrappers) > 1 else (wrappers[0] if wrappers else None)
        
        if target_wrapper:
            for i, tr in enumerate(target_wrapper.select(dl_selector)):
                dds = tr.select(value_selector)
                for j, th in enumerate(tr.select(header_selector)):
                    if len(th.contents) > 0:
                        thTitle = th.contents[0]
                    else:
                        thTitle = "Unknown"

                    try:
                        if len(dds) > j and len(dds[j].contents) > 0:
                            tdValue = dds[j].contents[0]
                            if isinstance(tdValue, str):
                                tdValue = tdValue.strip()
                        else:
                            tdValue = ""
                    except:
                        tdValue = ""
                        logging.warn("error. tdValue is empty. thTitle is " + str(thTitle))

                if thTitle == self.selectors.get('price_key', u"価格"):
                    price_selector = self.selectors.get('price')
                    if price_selector:
                        price_tag = tr.select_one(price_selector)
                        if price_tag:
                            tdValue = price_tag.text
                            item.priceStr = tdValue
                            item.price = converter.parse_price(item.priceStr)

                if thTitle == self.selectors.get('address_key', u"所在地"):
                    address_selector = self.selectors.get('address')
                    dd = tr.find("dd")
                    if dd:
                        links = []
                        if address_selector:
                             links = dd.select(address_selector)
                        
                        if len(links) >= 3:
                            item.address1 = links[0].text
                            item.address2 = links[1].text
                            item.address3 = links[2].text
                        else:
                            item.address1 = dd.get_text(strip=True)
                            item.address2 = ""
                            item.address3 = ""
                    
                    item.addressKyoto = ""
                    item.address = item.address1 + item.address2 + item.address3

                if thTitle == self.selectors.get('transport_key', u"交通"):
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
                        
                if thTitle == self.selectors.get('hikiwatashi_key', u"引渡時期"):
                    item.hikiwatashi = tdValue

                if thTitle == self.selectors.get('genkyo_key', u"現況"):
                    item.genkyo = tdValue

                if thTitle == self.selectors.get('tochikenri_key', u"土地権利"):
                    item.tochikenri = tdValue
                    
                if thTitle == self.selectors.get('sonota_hiyou_key', u"その他費用"):
                    item.sonotaHiyouStr = tdValue  # 新規
                    
                if thTitle == self.selectors.get('torihiki_key', u"取引態様"):
                    item.torihiki = tdValue  # 新規
                    
                if thTitle == self.selectors.get('biko_key', u"備考"):
                    item.biko = tdValue  # 新規
        item.busUse1 = 0
        if(item.busWalkMinute1 > 0):
            item.busUse1 = 1
        return item
    
class TokyuMansionParser(TokyuParser):
    property_type = 'mansion'

    def getRootXpath(self):
        return self.selectors.get('root_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return  TokyuMansion()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:TokyuMansion=super()._parsePropertyDetailPage(item, response)

        item.railwayCount = 0
        wrappers = response.find_all("div", class_="m-status-table__wrapper")
        target_wrapper = wrappers[1] if len(wrappers) > 1 else (wrappers[0] if wrappers else None)
        
        if target_wrapper:
            for i, tr in enumerate(target_wrapper.find_all("dl")):
                for j, th in enumerate(tr.find_all("dt")):
                    thTitle = th.contents[0]
                    try:
                        tdValue = tr.find_all("dd")[j].contents[0]
                        tdValue = tdValue.strip()
                        # logging.info("tdValue is " + tdValue + ". thTitle is " + thTitle)
                    except:
                        tdValue = ""
                        logging.warn("error. tdValue is empty. thTitle is " + thTitle)


                    if thTitle == self.selectors.get('madori_key', u"間取り"):
                        item.madori = tdValue

                    if thTitle == self.selectors.get('senyu_menseki_key', u"専有面積"):
                        item.senyuMensekiStr = tdValue
                        item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)
                        
                    if thTitle == self.selectors.get('kaisu_key', u"所在階数"):  # u'2階 / 地上8階 地下1階'
                        item.kaisu = tdValue
                        try:
                            # Try generic regex for "X階" or "Xbe" extraction
                            import re
                            # Current floor
                            floors = re.findall(r'(\d+)', item.kaisu.split("/")[0])
                            if floors:
                                item.floorType_kai = int(floors[0])
                                if "地下" in item.kaisu.split("/")[0]:
                                    item.floorType_kai = -item.floorType_kai
                            
                            # Total floors (Above ground)
                            chijo = re.search(r'地上(\d+)', item.kaisu)
                            if chijo:
                                item.floorType_chijo = int(chijo.group(1))
                            else:
                                # Fallback if just "X階建"
                                total = re.search(r'(\d+)階建', item.kaisu)
                                if total: item.floorType_chijo = int(total.group(1))

                            # Total floors (Below ground)
                            floorType_chika = 0
                            chika = re.search(r'地下(\d+)', item.kaisu)
                            if chika:
                                floorType_chika = int(chika.group(1))
                            item.floorType_chika = floorType_chika
                        except Exception as e:
                            logging.warning(f"Failed to parse floor info '{item.kaisu}': {e}")

                    if thTitle == self.selectors.get('kouzou_key', u"建物構造"):
                        item.kouzou = tdValue  # 鉄筋コンクリート造

                    if thTitle == self.selectors.get('chikunengetsu_key', u"築年月"):  # u1998年3月
                        item.chikunengetsuStr = tdValue
                        item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)
                            
                    if thTitle == self.selectors.get('balcony_key', u"バルコニー"):
                        item.barukoniMensekiStr = tdValue

                    if thTitle == self.selectors.get('saikou_key', u"向き"):
                        item.saikou = tdValue

                    if thTitle == self.selectors.get('soukosu_key', u"総戸数"):
                        item.soukosuStr = tdValue
                        item.soukosu = 0
                        if(item.soukosuStr != "-"):
                            item.soukosu = int(item.soukosuStr.replace(u",", "").replace(u"戸", "").strip())

                    if thTitle == self.selectors.get('kanri_kaisya_key', u"管理会社"):
                        item.kanriKaisya = tdValue.replace(u" / ", "").replace(u"全部委託", "")
                        
                    if thTitle == self.selectors.get('kanri_keitai_key', u"管理方式"):
                        item.kanriKeitai = tdValue

                    if thTitle == self.selectors.get('kanrihi_key', u"管理費"):
                        item.kanrihiStr = tdValue
                        if "-" in item.kanrihiStr:
                            item.kanrihi = 0
                        else:
                            try:
                                item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"（円/月）", "").replace(u"円/月", "").replace(u"円", "").strip())
                            except: item.kanrihi = 0
                            
                    if thTitle == self.selectors.get('syuzen_tsumitate_key', u"修繕積立金"):
                        item.syuzenTsumitateStr = tdValue
                        if "-" in item.syuzenTsumitateStr:
                            item.syuzenTsumitate = 0
                        else:
                            try:
                                item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"（円/月）", "").replace(u"円/月", "").replace(u"円", "").strip())
                            except: item.syuzenTsumitate = 0

                    if thTitle == self.selectors.get('parking_key', u"駐車場"):
                        item.tyusyajo = tdValue

                    if thTitle == self.selectors.get('bunjo_kaisya_key', u"分譲会社"):
                        item.bunjoKaisya = tdValue.replace(u"（新築分譲時における売主）", "")  # 新規
                        
                    if thTitle == self.selectors.get('sekou_kaisya_key', u"施工会社"):
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
        if(item.chikunengetsu and item.chikunengetsu < datetime.date(1982, 1, 1)):
            item.kyutaishin = 1
        item.barukoniMenseki = 0
        if item.barukoniMensekiStr != "-":
            item.barukoniMenseki = converter.parse_menseki(item.barukoniMensekiStr)
        item.senyouNiwaMenseki = 0
        item.roofBarukoniMenseki = 0
        if item.senyuMenseki and item.senyuMenseki > 0:
            item.kanrihi_p_heibei = item.kanrihi / item.senyuMenseki
            item.syuzenTsumitate_p_heibei = item.syuzenTsumitate / item.senyuMenseki
        else:
            item.kanrihi_p_heibei = 0
            item.syuzenTsumitate_p_heibei = 0
            
        return item


class TokyuTochiParser(TokyuParser):
    property_type = 'tochi'

    def getRootXpath(self):
        return self.selectors.get('root_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return  TokyuTochi()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:TokyuTochi=super()._parsePropertyDetailPage(item, response)

        item.railwayCount = 0
        wrappers = response.find_all("div", class_="m-status-table__wrapper")
        target_wrapper = wrappers[1] if len(wrappers) > 1 else (wrappers[0] if wrappers else None)
        
        if target_wrapper:
            for i, tr in enumerate(target_wrapper.find_all("dl")):
                for j, th in enumerate(tr.find_all("dt")):
                    thTitle = th.contents[0]
                    try:
                        tdValue = tr.find_all("dd")[j].contents[0]
                        tdValue = tdValue.strip()
                    except:
                        tdValue = ""
                        logging.warn("error. tdValue is empty. thTitle is " + thTitle)

                    if thTitle == self.selectors.get('tochi_menseki_key', u"土地面積"):
                        item.tochiMensekiStr = tdValue
                        try:
                            tochiMensekiWork = item.tochiMensekiStr.replace(u'実測', '').replace(u'公簿', '').replace(u'm', '').strip()
                            item.tochiMenseki = Decimal(tochiMensekiWork)
                        except:
                            item.tochiMenseki = 0
                    
                    if thTitle == self.selectors.get('chimoku_key', u"地目"):
                        item.chimoku = tdValue

                    if thTitle == self.selectors.get('chisei_key', u"地勢"):
                        item.chisei = tdValue

                    if thTitle == self.selectors.get('setsudou_key', u"接道状況"):
                        item.setsudou = tdValue # Example: 北東側 4.00m 公道 接面11.00m

                    if thTitle == self.selectors.get('kenpei_key', u"建ぺい率"):
                        item.kenpeiYousekiStr += "建ぺい率:" + tdValue + " "
                        try:
                            item.kenpei = int(tdValue.replace("%", ""))
                        except:
                            pass
                    
                    if thTitle == self.selectors.get('youseki_key', u"容積率"):
                        item.kenpeiYousekiStr += "容積率:" + tdValue
                        try:
                            item.youseki = int(tdValue.replace("%", ""))
                        except:
                            pass
                    
                    if thTitle == self.selectors.get('youto_chiiki_key', u"用途地域"):
                        item.youtoChiiki = tdValue

                    if thTitle == self.selectors.get('kuiki_key', u"都市計画"):
                        item.kuiki = tdValue
                        
                    if thTitle == self.selectors.get('kokudohou_key', u"国土法届出"):
                        item.kokudoHou = tdValue

                    if thTitle == self.selectors.get('kenchiku_joken_key', u"建築条件"):
                        item.kenchikuJoken = tdValue

        return item


class TokyuKodateParser(TokyuParser):
    property_type = 'kodate'

    def getRootXpath(self):
        return self.selectors.get('root_xpath')

    def getAreaXpath(self):
        return self.selectors.get('area_xpath')

    def getPropertyListXpath(self):
        return self.selectors.get('property_links_xpath')

    def createEntity(self):
        return  TokyuKodate()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item:TokyuKodate=super()._parsePropertyDetailPage(item, response)

        item.railwayCount = 0
        wrappers = response.find_all("div", class_="m-status-table__wrapper")
        target_wrapper = wrappers[1] if len(wrappers) > 1 else (wrappers[0] if wrappers else None)
        
        if target_wrapper:
            for i, tr in enumerate(target_wrapper.find_all("dl")):
                for j, th in enumerate(tr.find_all("dt")):
                    thTitle = th.contents[0]
                    try:
                        tdValue = tr.find_all("dd")[j].contents[0]
                        tdValue = tdValue.strip()
                    except:
                        tdValue = ""
                        logging.warn("error. tdValue is empty. thTitle is " + thTitle)

                    if thTitle == self.selectors.get('madori_key', u"間取り"): # Mansion ok
                        item.madori = tdValue

                    if thTitle == self.selectors.get('tatemono_menseki_key', u"建物面積"):
                        item.tatemonoMensekiStr = tdValue
                        item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

                    if thTitle == self.selectors.get('tochi_menseki_key', u"土地面積"):
                        item.tochiMensekiStr = tdValue
                        try:
                            tochiMensekiWork = item.tochiMensekiStr.replace(u'実測', '').replace(u'公簿', '').replace(u'm', '').strip()
                            item.tochiMenseki = Decimal(tochiMensekiWork)
                        except:
                            item.tochiMenseki = 0

                    if thTitle == self.selectors.get('kouzou_key', u"建物構造"):
                        item.kouzou = tdValue
                        item.kaisuKouzou = tdValue # Combined field for Kodate

                    if thTitle == self.selectors.get('chikunengetsu_key', u"築年月"): # Mansion ok
                        item.chikunengetsuStr = tdValue
                        item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

                    if thTitle == self.selectors.get('chimoku_key', u"地目"):
                        item.chimoku = tdValue

                    if thTitle == self.selectors.get('youto_chiiki_key', u"用途地域"):
                        item.youtoChiiki = tdValue

                    if thTitle == self.selectors.get('setsudou_key', u"接道状況"):
                        item.setsudou = tdValue

                    if thTitle == self.selectors.get('kenpei_key', u"建ぺい率"):
                        item.kenpeiYousekiStr += "建ぺい率:" + tdValue + " "
                        try:
                            item.kenpei = int(tdValue.replace("%", ""))
                        except:
                            pass
                    
                    if thTitle == self.selectors.get('youseki_key', u"容積率"):
                        item.kenpeiYousekiStr += "容積率:" + tdValue
                        try:
                            item.youseki = int(tdValue.replace("%", ""))
                        except:
                            pass
                    
                    if thTitle == self.selectors.get('kuiki_key', u"都市計画"):
                        item.kuiki = tdValue

        return item


class TokyuInvestmentParser(InvestmentParser):
    property_type = 'investment'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('tokyu', self.property_type)

    def getCharset(self):
        return "utf-8"

    def createEntity(self) -> models.Model:
        return TokyuInvestment()

    def _parsePropertyDetailPage(self, item: TokyuInvestment, response: BeautifulSoup) -> models.Model:
        # Title
        title_selector = self.selectors.get('title', 'h1')
        title_el = response.select_one(title_selector)
        item.propertyName = self._clean_text(title_el.get_text()) if title_el else ""

        # Robust extraction from dataLayer script if present
        details_script = response.find(string=lambda t: t and 'dataLayer.push({"event":"tlab.event.user.view.detail"' in t)
        property_type = ""
        if details_script:
            import json
            try:
                # Extract JSON string from dataLayer.push({...})
                match = re.search(r'dataLayer\.push\((\{.*?\})\);', details_script, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    prop = data.get("tlab.property", {})
                    item.priceStr = prop.get("price", "")
                    item.address = prop.get("address", "")
                    item.traffic = prop.get("access", "")
                    property_type = prop.get("property_type", "")
                    # price parsing
                    item.price = self._parse_price(item.priceStr)
            except Exception as e:
                logging.warning(f"Failed to parse dataLayer for Tokyu: {e}")

        # Fallback to selectors if dataLayer failed or missing fields
        if not item.priceStr:
            price_selector = self.selectors.get('price', ".price")
            price_el = response.select_one(price_selector)
            if not price_el:
                price_text = response.find(string=lambda t: "万円" in t or "億円" in t)
                item.priceStr = self._clean_text(price_text) if price_text else ""
            else:
                item.priceStr = self._clean_text(price_el.get_text())
            item.price = self._parse_price(item.priceStr)

        # Specs in DL list
        table_config = self.selectors.get('table', {})
        dl_selector = table_config.get('selector', 'dl')
        header_selector = table_config.get('header', 'dt')
        value_selector = table_config.get('value', 'dd')

        specs = {}
        dl_list = response.select(dl_selector)
        for dl in dl_list:
            dts = dl.select(header_selector)
            dds = dl.select(value_selector)
            for dt, dd in zip(dts, dds):
                label = self._clean_text(dt.get_text())
                value = self._clean_text(dd.get_text())
                specs[label] = value

        # Mapping with type sensitivity
        item.address = item.address or specs.get(self.selectors.get('address_key', "所在地"), "")
        item.traffic = item.traffic or specs.get(self.selectors.get('traffic_key', "交通"), "")
        item.structure = specs.get(self.selectors.get('structure_key', "構造"), "")
        item.yearBuilt = specs.get(self.selectors.get('year_built_key', "築年月"), "")
        
        # Area branching
        menseki_key = self.selectors.get('menseki_key', "専有面積")
        tochikenri_key = self.selectors.get('tochikenri_key', "土地権利")
        tochi_menseki_key = self.selectors.get('tochi_menseki_key', "土地面積")
        tatemono_menseki_key = self.selectors.get('tatemono_menseki_key', "建物面積")
        nobeyuka_menseki_key = self.selectors.get('nobeyuka_menseki_key', "延床面積")

        if "マンション" in property_type:
            item.buildingArea = specs.get(menseki_key, "")
            item.landArea = specs.get(tochikenri_key, "")
        elif "土地" in property_type:
            item.landArea = specs.get(tochi_menseki_key, "")
            item.buildingArea = None
        else: # Building, House, Apartment
            item.landArea = specs.get(tochi_menseki_key, "")
            item.buildingArea = specs.get(tatemono_menseki_key, "") or specs.get(nobeyuka_menseki_key, "")

        # Yield
        yield_key = self.selectors.get('yield_key', u"利回り")
        surface_yield_key = self.selectors.get('surface_yield_key', u"表面利回り")
        yield_val = specs.get(yield_key, "") or specs.get(surface_yield_key, "")
        item.grossYield = self._parse_yield(yield_val)

        return item

    def parsePropertyListPage(self, response: BeautifulSoup):
        # Pattern: /fudosan-toushi/C[ID]/
        links_selector = self.selectors.get('property_links')
        if links_selector:
            links = response.select(links_selector)
            for link in links:
                href = link.get("href")
                if href and href.startswith("/"):
                    href = "https://www.livable.co.jp" + href
                if href: yield href


    def parseNextPage(self, response: BeautifulSoup):
        # a contains "次へ"
        next_text = self.selectors.get('next_page', "次へ")
        next_link = response.find("a", string=lambda t: t and next_text in t)
        if next_link:
            href = next_link.get("href")
            if href.startswith("/"):
                return "https://www.livable.co.jp" + href
            return href
        return ""
