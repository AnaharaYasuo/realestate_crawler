# -*- coding: utf-8 -*-
import sys
from tokenize import String
import unicodedata

from bs4 import BeautifulSoup
from package.models.mitsui import MitsuiKodate, MitsuiMansion, MitsuiTochi
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
        
        # Fallback if xpath fails or is not supported (BS4 usually doesn't support xpath directly unless configured)
        # Fallback using xpath since response is lxml HtmlElement
        fallback_xpath = '//a[contains(@class, "pagination-next")]/@href'
        linkUrlList = response.xpath(fallback_xpath)
        if (len(linkUrlList) > 0):
            return self.BASE_URL + linkUrlList[0]
            
        return ""

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        item=super()._parsePropertyDetailPage(item, response)
        try:
            name_tag = response.select_one("h1.headline1")
            if name_tag:
                 item.propertyName = name_tag.get_text(strip=True)
            else:
                 fallback = response.select_one("h1.headline1.mb-4")
                 if fallback:
                     item.propertyName = fallback.get_text(strip=True)
            
            if not getattr(item, 'propertyName', None): # Check if propertyName was set by previous attempts
                # Generic fallback
                generic_h1 = response.select_one("h1")
                if generic_h1:
                    item.propertyName = generic_h1.get_text(strip=True)

            if not getattr(item, 'propertyName', None):
                raise ReadPropertyNameException("Could not find property name")
        except Exception:
            raise ReadPropertyNameException()

        for i, tr in enumerate(response.find_all("tr",class_="table-row")):
            th_tag = tr.select_one("td.table-header.label")
            if not th_tag: continue
            thTitle = th_tag.get_text(strip=True)
            
            try:
                td_content = tr.select_one("td.table-data.content")
                if td_content: tdValue = td_content.get_text(strip=True)
                else: 
                     tds = tr.find_all("td")
                     if len(tds) > 1:
                         spans = tds[1].find_all("span")
                         if spans:
                             tdValue = spans[0].get_text(strip=True)
                         else:
                             tdValue = tds[1].get_text(strip=True)
                     else: tdValue = ""
            except:
                tdValue = ""
                logging.warn("error. tdValue is empty. thTitle is " + thTitle)

            if thTitle == u"価格":
                if not tdValue:
                     try: 
                         tds = tr.find_all("td")
                         if len(tds) > 1:
                             ps = tds[1].find_all("p")
                             if ps: tdValue = ps[0].get_text(strip=True)
                     except: pass

                item.priceStr = tdValue            
                priceWork = item.priceStr.replace(',', '')
                oku = 0
                man = 0
                if (u"億" in item.priceStr):
                    priceArr = priceWork.split(u"億")
                    try: oku = int(priceArr[0]) * 10000
                    except: pass
                    if len(priceArr) > 1 and len(priceArr[1]) != 0:
                        try: man = int(priceArr[1].replace(u'万', '').replace(u'円', ''))
                        except: pass
                else:
                    try: man = int(priceWork.replace(u'万', '').replace(u'円', ''))
                    except: pass
                price = oku + man
                item.price = price
                
            elif thTitle == u"所在地":
                item.address = tdValue
                parts = tdValue.split(" ")
                if len(parts) >= 1: item.address1 = parts[0]
                if len(parts) >= 2: item.address2 = parts[1]
                if len(parts) >= 3: item.address3 = "".join(parts[2:])

            elif thTitle == u"最寄り駅":
                lines = []
                td_content = tr.select_one("td.table-data.content")
                if td_content:
                    lines = [p.get_text(strip=True) for p in td_content.find_all("p")]
                    if not lines: lines = [td_content.get_text(strip=True)]
                
                item.railwayCount = 0
                for i, line in enumerate(lines):
                    if i >= 5: break
                    item.railwayCount += 1
                    if i == 0: item.transfer1 = line
                    elif i == 1: item.transfer2 = line
                    elif i == 2: item.transfer3 = line
                    elif i == 3: item.transfer4 = line
                    elif i == 4: item.transfer5 = line
                    
            elif thTitle == u"引渡時期":
                item.hikiwatashi = tdValue
            elif thTitle == u"現況":
                item.genkyo = tdValue
            elif thTitle == u"土地権利":
                item.tochikenri = tdValue
            elif thTitle == u"その他費用":
                item.sonotaHiyouStr = tdValue
            elif thTitle == u"取引態様":
                item.torihiki = tdValue
            elif thTitle == u"備考":
                item.biko = tdValue
                    
        # 不要項目
        item.busUse1 = 0
        if hasattr(item, 'busWalkMinute1') and item.busWalkMinute1 > 0:
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
        item:MitsuiMansion=super()._parsePropertyDetailPage(item, response)
        
        # Helper to extract table data (same as base but repeated for clarity or could be mixing lookup)
        # We need to scan finding table-row again or rely on super()?
        # Super sets base fields. Subclass iterates for specific fields.
        
        def get_table_value_sub(tr):
            try:
                td_content = tr.select_one("td.table-data.content")
                if td_content: return td_content.get_text(strip=True)
                tds = tr.find_all("td")
                if len(tds) > 1: return tds[1].get_text(strip=True)
                return ""
            except: return ""

        for tr in response.select("tr.table-row"):
            th_tag = tr.select_one("td.table-header.label")
            if not th_tag: continue
            thTitle = th_tag.get_text(strip=True)
            tdValue = get_table_value_sub(tr)

            if thTitle == u"間取り":
                item.madori = tdValue

            elif thTitle == u"専有面積":
                item.senyuMensekiStr = tdValue
                try:
                    senyuMensekiWork = item.senyuMensekiStr.split(u'㎡')[0]
                    item.senyuMenseki = Decimal(senyuMensekiWork)
                except:
                    item.senyuMenseki = 0
                
            elif thTitle == u"階数 / 階建" or thTitle == u"階建 / 階":
                item.kaisu = tdValue

            elif thTitle == u"建物構造":
                item.kouzou = tdValue

            elif thTitle == u"築年月":
                item.chikunengetsuStr = tdValue
                if (item.chikunengetsuStr == u"不詳"):
                    nen = 1900
                    tsuki = 1
                else:
                    try:
                        nen = int(item.chikunengetsuStr.split(u"年")[0])
                        tsuki = int(item.chikunengetsuStr.split(u"年")[1].split(u"月")[0])
                    except:
                        nen = 1900
                        tsuki = 1
                item.chikunengetsu = datetime.date(nen, tsuki, 1)

            elif thTitle == u"バルコニー":
                item.barukoniMensekiStr = tdValue

            elif thTitle == u"向き":
                item.saikou = tdValue

            elif thTitle == u"総戸数":
                item.soukosuStr = tdValue
                item.soukosu = 0
                if(item.soukosuStr != "-"):
                    try: item.soukosu = int(item.soukosuStr.replace(u",", "").replace(u"戸", "").strip())
                    except: pass

            elif thTitle == u"管理会社":
                item.kanriKaisya = tdValue
                
            elif thTitle == u"管理方式":
                item.kanriKeitai = tdValue

            elif thTitle == u"管理費等":
                item.kanrihiStr = tdValue
                if "-" in item.kanrihiStr:
                    item.kanrihi = 0
                else:
                    try: item.kanrihi = int(item.kanrihiStr.replace(",", "").replace(u"円", ""))
                    except: item.kanrihi = 0
                    
            elif thTitle == u"修繕積立金":
                item.syuzenTsumitateStr = tdValue
                if "-" in item.syuzenTsumitateStr:
                    item.syuzenTsumitate = 0
                else:
                    try: item.syuzenTsumitate = int(item.syuzenTsumitateStr.replace(",", "").replace(u"円", ""))
                    except: item.syuzenTsumitate = 0

            elif thTitle == u"駐車場":
                item.tyusyajo = tdValue

            elif thTitle == u"分譲会社":
                item.bunjoKaisya = tdValue.replace(u" (新築分譲時における売主)", "")
                
            elif thTitle == u"施工会社":
                item.sekouKaisya = tdValue
                                        
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
        item:MitsuiTochi=super()._parsePropertyDetailPage(item, response)

        def get_table_value_sub(tr):
            try:
                td_content = tr.select_one("td.table-data.content")
                if td_content: return td_content.get_text(strip=True)
                tds = tr.find_all("td")
                if len(tds) > 1: return tds[1].get_text(strip=True)
                return ""
            except: return ""

        for tr in response.select("tr.table-row"):
            th_tag = tr.select_one("td.table-header.label")
            if not th_tag: continue
            thTitle = th_tag.get_text(strip=True)
            tdValue = get_table_value_sub(tr)

            if thTitle == u"土地面積":
                item.tochiMensekiStr = tdValue
                try: item.tochiMenseki = Decimal(item.tochiMensekiStr.replace(",","").split("㎡")[0].strip())
                except: item.tochiMenseki = 0

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
        item:MitsuiKodate=super()._parsePropertyDetailPage(item, response)

        def get_table_value_sub(tr):
            try:
                td_content = tr.select_one("td.table-data.content")
                if td_content: return td_content.get_text(strip=True)
                return tr.find_all("td")[1].get_text(strip=True)
            except: return ""

        for tr in response.select("tr.table-row"):
            th_tag = tr.select_one("td.table-header.label")
            if not th_tag: continue
            thTitle = th_tag.get_text(strip=True)
            tdValue = get_table_value_sub(tr)

            if thTitle == u"建物面積":
                item.tatemonoMensekiStr = tdValue
                try: item.tatemonoMenseki = Decimal(item.tatemonoMensekiStr.replace(",","").split("㎡")[0].strip())
                except: item.tatemonoMenseki = 0

            elif thTitle == u"土地面積":
                item.tochiMensekiStr = tdValue
                try: item.tochiMenseki = Decimal(item.tochiMensekiStr.replace(",","").split("㎡")[0].strip())
                except: item.tochiMenseki = 0

            elif thTitle == u"建物構造":
                item.kaisuKouzou  = tdValue
                if(item.kaisuKouzou.find(u"その他")>-1):
                    item.kouzou=u"その他"
                    try: item.kaisu = item.kaisuKouzou.split(u"その他")[1].strip()
                    except: item.kaisu = ""
                elif(item.kaisuKouzou.find(u"-")>-1):
                    item.kouzou=u"-"
                else:
                    try:
                        item.kouzou = item.kaisuKouzou.split(u"造")[0].strip()+u"造"
                        item.kaisu  = item.kaisuKouzou.split(u"造")[1].strip()
                    except:
                        item.kouzou = item.kaisuKouzou
                        item.kaisu = ""

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


class MitsuiInvestmentParser(MitsuiParser):
    def getRootXpath(self):
        return u''

    def getAreaXpath(self):
        return u''

    def getPropertyListXpath(self):
        return u''
    
    def createEntity(self):
        from package.models.mitsui import MitsuiInvestment
        return MitsuiInvestment()

    def _parsePropertyDetailPage(self, item, response:BeautifulSoup):
        # Specific investment logic
        # Usually investment pages might have similar layout but different fields
        # For now, reuse base logic and add specific fields
        item = super()._parsePropertyDetailPage(item, response)
        
        # Override or add specific extractions
        # Example: Yield
        # Look for "利回り" in table
        for tr in response.select("tr.table-row"):
            th_tag = tr.select_one("td.table-header.label")
            if not th_tag: continue
            thTitle = th_tag.get_text(strip=True)
            
            # Helper to get value
            def get_val(r):
                 try:
                    td = r.select_one("td.table-data.content")
                    if td: return td.get_text(strip=True)
                    return r.find_all("td")[1].get_text(strip=True)
                 except: return ""

            tdValue = get_val(tr)

            if "利回り" in thTitle or "表面利回り" in thTitle:
                try:
                    val = tdValue.replace("%", "").strip()
                    item.grossYield = Decimal(val)
                except:
                    item.grossYield = 0
            
            if "現況" in thTitle:
                item.currentStatus = tdValue
                
            if "構造" in thTitle:
                 item.structure = tdValue
            
            if "築年月" in thTitle:
                 item.yearBuilt = tdValue

            if "土地面積" in thTitle:
                 item.landArea = tdValue
            
            if "建物面積" in thTitle or "専有面積" in thTitle:
                 item.buildingArea = tdValue

        return item
