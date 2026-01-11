from bs4 import BeautifulSoup
from django.db import models
import logging
import re
from package.parser.investmentParser import InvestmentParser
from package.models.nomura import NomuraInvestmentModel
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class NomuraParser(InvestmentParser):
    property_type = 'investment'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('nomura', self.property_type)

    def getCharset(self):
        return "utf-8"

    def createEntity(self) -> models.Model:
        return NomuraInvestmentModel()

    def _parsePropertyDetailPage(self, item: NomuraInvestmentModel, response: BeautifulSoup) -> models.Model:
        # Title
        title_selector = self.selectors.get('title')
        title_el = response.select_one(title_selector)
        if not title_el:
             title_fallback = self.selectors.get('title_fallback', 'h1')
             title_el = response.select_one(title_fallback)
        
        if title_el:
            item.propertyName = self._clean_text(title_el.get_text())
        else:
            raise ReadPropertyNameException()

        # Property Type Detection from breadcrumbs or title
        # Breadcrumbs: /pro/ -> [Type] -> [Details]
        breadcrumb_selector = self.selectors.get('breadcrumb', '.c_breadcrumb_item')
        breadcrumb_els = response.select(breadcrumb_selector)
        property_type = ""
        if len(breadcrumb_els) >= 3:
            property_type = self._clean_text(breadcrumb_els[2].get_text())
        
        # Price - Nomura Pro details often have price in .c_price_primary_value or .c_price_primary_text
        price_selector = self.selectors.get('price', '.c_price_primary_value')
        price_el = response.select_one(price_selector)
        if not price_el:
            price_fallback = self.selectors.get('price_fallback', '.c_price_primary_text')
            price_el = response.select_one(price_fallback)
        
        # Fallback for price if not in primary classes
        if not price_el:
            price_el = response.find(string=lambda t: t and ("万円" in t or "億円" in t))
        
        item.priceStr = self._clean_text(price_el.get_text() if hasattr(price_el, 'get_text') else price_el)
        item.price = self._parse_price(item.priceStr)

        # Spec Table
        specs = {}
        table_config = self.selectors.get('table', {})
        table_selector = table_config.get('selector', 'table.c_table_spec')
        header_selector = table_config.get('header', 'th')
        value_selector = table_config.get('value', 'td')

        table = response.select_one(table_selector)
        if table:
            rows = table.select("tr")
            for row in rows:
                th = row.select_one(header_selector)
                td = row.select_one(value_selector)
                if th and td:
                    label = self._clean_text(th.get_text())
                    value = self._clean_text(td.get_text())
                    specs[label] = value
        
        # Base mapping
        item.address = specs.get(self.selectors.get('address_key', "所在地"), "")
        item.traffic = specs.get(self.selectors.get('traffic_key', "交通"), "")
        item.structure = specs.get(self.selectors.get('structure_key', "構造"), "")
        item.yearBuilt = specs.get(self.selectors.get('year_built_key', "築年月"), "")
        item.currentStatus = specs.get(self.selectors.get('current_status_key', "現況"), "")
        
        yield_val = specs.get(self.selectors.get('yield_key', "利回り"), "") or specs.get(self.selectors.get('surface_yield_key', "表面利回り"), "")
        item.grossYield = self._parse_yield(yield_val)
        
        # Type specific area mapping
        menseki_key = self.selectors.get('menseki_key', "専有面積")
        tochikenri_key = self.selectors.get('tochikenri_key', "土地権利")
        tochi_menseki_key = self.selectors.get('tochi_menseki_key', "土地面積")
        tatemono_menseki_key = self.selectors.get('tatemono_menseki_key', "建物面積")
        nobeyuka_menseki_key = self.selectors.get('nobeyuka_menseki_key', "延床面積")

        if "マンション" in property_type:
            item.buildingArea = specs.get(menseki_key, "")
            item.landArea = specs.get(tochikenri_key, "") # Often doesn't have land area for condo but right
        elif "土地" in property_type:
            item.landArea = specs.get(tochi_menseki_key, "")
            item.buildingArea = None
        else: # Building or House
            item.landArea = specs.get(tochi_menseki_key, "")
            item.buildingArea = specs.get(tatemono_menseki_key, "") or specs.get(nobeyuka_menseki_key, "")

        return item

    async def parsePropertyListPage(self, response: BeautifulSoup):
        # Find property links
        # Pattern: /pro/bukken_local_id/[ID]/
        links_selector = self.selectors.get('property_links', "a[href*='/pro/bukken_local_id/']")
        links = response.select(links_selector)
        for link in links:
            href = link.get("href")
            # Make absolute URL found in baseParser usually handled by getDestUrl but here we yield full URL?
            # Base parser uses getDestUrl callback. 
            # But the interface here is async iterator yielding URLs.
            # Let's ensure it returns absolute URLs.
            if href.startswith("/"):
                href = "https://www.nomu.com" + href
            yield href

    def parseNextPage(self, response: BeautifulSoup):
        # Find next page link
        # Usually class "next"
        next_selector = self.selectors.get('next_page', "a.next")
        next_link = response.select_one(next_selector)
        if next_link:
            return next_link.get("href")
        return None

# Residential Parsers inheriting basic logic or defining new one
# Assuming residential follows a similar structure or we use generic logic for now
class NomuraResidentialBaseHelper:
    def parse_common(self, item, response, selectors):
        # Title
        title_selector = selectors.get('title', 'h1')
        title_el = response.select_one(title_selector)
        if title_el:
            item.propertyName = title_el.get_text(strip=True)
            
        # Price
        price_selector = selectors.get('price', '.price')
        price_el = response.select_one(price_selector) or response.find(string=lambda t: t and "万円" in t)
        if price_el:
            item.priceStr = price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else price_el.strip()
            item.price = converter.parse_price(item.priceStr)
        
        # Specs (DL/DT/DD or Table)
        # Try finding table with th/td
        specs = {}
        table_config = selectors.get('table', {})
        table_selector = table_config.get('selector', 'table')
        row_selector = table_config.get('row', 'tr')
        header_selector = table_config.get('header', 'th')
        value_selector = table_config.get('value', 'td')

        for tr in response.select(f"{table_selector} {row_selector}"):
            th = tr.select_one(header_selector)
            td = tr.select_one(value_selector)
            if th and td:
                specs[th.get_text(strip=True)] = td.get_text(strip=True)
        
        # Fallback to dl/dt/dd
        if not specs:
             dl_config = selectors.get('dl_table', {})
             dl_selector = dl_config.get('selector', 'dl')
             dt_selector = dl_config.get('header', 'dt')
             dd_selector = dl_config.get('value', 'dd')
             for dl in response.select(dl_selector):
                dt = dl.select_one(dt_selector)
                dd = dl.select_one(dd_selector)
                if dt and dd:
                    specs[dt.get_text(strip=True)] = dd.get_text(strip=True)

        item.address = specs.get(selectors.get('address_key', "所在地"), "")
        item.traffic = specs.get(selectors.get('traffic_key', "交通"), "")
        return specs


class NomuraMansionParser(InvestmentParser, NomuraResidentialBaseHelper):
    property_type = 'mansion'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('nomura', self.property_type)

    def createEntity(self):
        from package.models.nomura import NomuraMansion
        return NomuraMansion()
        
    def _parsePropertyDetailPage(self, item, response):
        specs = self.parse_common(item, response, self.selectors)
        item.madori = specs.get(self.selectors.get('madori_key', "間取り"), "")
        item.senyuMensekiStr = specs.get(self.selectors.get('senyu_menseki_key', "専有面積"), "")
        item.yearBuilt = specs.get(self.selectors.get('year_built_key', "築年月"), "")
        
        item.balconyArea = specs.get(self.selectors.get('balcony_key', "バルコニー面積"), "")
        item.facing = specs.get(self.selectors.get('facing_key', "向き"), "")
        item.otherArea = specs.get(self.selectors.get('other_area_key', "その他面積"), "")
        item.structure = specs.get(self.selectors.get('structure_key', "構造"), "")
        item.floorNumber = specs.get(self.selectors.get('floor_key', "所在階"), "")
        item.totalUnits = specs.get(self.selectors.get('soukosu_key', "総戸数"), "")
        item.landRights = specs.get(self.selectors.get('tochikenri_key', "土地権利"), "")
        item.zoning = specs.get(self.selectors.get('youto_chiiki_key', "用途地域"), "")
        item.managementCompany = specs.get(self.selectors.get('kanri_kaisya_key', "管理会社"), "")
        item.managementForm = specs.get(self.selectors.get('kanri_keitai_key', "管理形態"), "")
        item.manager = specs.get(self.selectors.get('manager_key', "管理員"), "")
        item.managementFee = specs.get(self.selectors.get('kanrihi_key', "管理費"), "")
        item.repairReserveFund = specs.get(self.selectors.get('syuzen_tsumitate_key', "修繕積立金"), "")
        item.otherFees = specs.get(self.selectors.get('sonota_hiyou_key', "その他使用料"), "")
        item.parking = specs.get(self.selectors.get('parking_key', "駐車場"), "")
        item.currentStatus = specs.get(self.selectors.get('genkyo_key', "現況"), "")
        item.deliveryDate = specs.get(self.selectors.get('hikiwatashi_key', "引　渡"), "")
        item.transactionMode = specs.get(self.selectors.get('torihiki_key', "取引態様"), "")
        item.remarks = specs.get(self.selectors.get('biko_key', "備　考"), "")
        item.updateDate = specs.get(self.selectors.get('update_date_key', "更新日"), "")
        item.nextUpdateDate = specs.get(self.selectors.get('next_update_date_key', "次回更新予定日"), "")
        
        return item

class NomuraKodateParser(InvestmentParser, NomuraResidentialBaseHelper):
    property_type = 'kodate'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('nomura', self.property_type)

    def createEntity(self):
        from package.models.nomura import NomuraKodate
        return NomuraKodate()

    def _parsePropertyDetailPage(self, item, response):
        specs = self.parse_common(item, response, self.selectors)
        
        # Basic Residential Fields
        item.landArea = specs.get(self.selectors.get('tochi_menseki_key', "土地面積"), "")
        item.buildingArea = specs.get(self.selectors.get('tatemono_menseki_key', "建物面積"), "")
        item.structure = specs.get(self.selectors.get('structure_key', "構造"), "")
        item.yearBuilt = specs.get(self.selectors.get('year_built_key', "築年月"), "")
        
        # Extended Fields
        item.parking = specs.get(self.selectors.get('parking_key', "駐車場"), "")
        item.landRights = specs.get(self.selectors.get('tochikenri_key', "土地権利"), "")
        item.landCategory = specs.get(self.selectors.get('chimoku_key', "地目"), "")
        item.privateRoadBurden = specs.get(self.selectors.get('shido_futan_key', "私道負担"), "")
        item.setback = specs.get(self.selectors.get('setback_key', "セットバック"), "")
        item.cityPlanning = specs.get(self.selectors.get('toshi_keikaku_key', "都市計画"), "")
        item.zoning = specs.get(self.selectors.get('youto_chiiki_key', "用途地域"), "")
        item.buildingCoverageRatio = specs.get(self.selectors.get('kenpei_key', "建ぺい率"), "")
        item.floorAreaRatio = specs.get(self.selectors.get('youseki_key', "容積率"), "")
        item.roadAccess = specs.get(self.selectors.get('setsudou_key', "接道状況"), "")
        item.facilities = specs.get(self.selectors.get('setsubi_key', "設備"), "")
        item.currentStatus = specs.get(self.selectors.get('genkyo_key', "現況"), "")
        item.deliveryDate = specs.get(self.selectors.get('hikiwatashi_key', "引　渡"), "")
        item.transactionMode = specs.get(self.selectors.get('torihiki_key', "取引態様"), "")
        item.remarks = specs.get(self.selectors.get('biko_key', "備　考"), "")
        item.updateDate = specs.get(self.selectors.get('update_date_key', "更新日"), "")
        item.nextUpdateDate = specs.get(self.selectors.get('next_update_date_key', "次回更新予定日"), "")
        
        return item

class NomuraTochiParser(InvestmentParser, NomuraResidentialBaseHelper):
    property_type = 'tochi'
    def __init__(self, params=None):
        self.selectors = SelectorLoader.load('nomura', self.property_type)

    def createEntity(self):
        from package.models.nomura import NomuraTochi
        return NomuraTochi()

    def _parsePropertyDetailPage(self, item, response):
        specs = self.parse_common(item, response, self.selectors)
        
        item.landArea = specs.get(self.selectors.get('tochi_menseki_key', "土地面積"), "")
        
        # Extended Fields
        item.landRights = specs.get(self.selectors.get('tochikenri_key', "土地権利"), "")
        item.landCategory = specs.get(self.selectors.get('chimoku_key', "地目"), "")
        item.privateRoadBurden = specs.get(self.selectors.get('shido_futan_key', "私道負担"), "")
        item.setback = specs.get(self.selectors.get('setback_key', "セットバック"), "")
        item.cityPlanning = specs.get(self.selectors.get('toshi_keikaku_key', "都市計画"), "")
        item.zoning = specs.get(self.selectors.get('youto_chiiki_key', "用途地域"), "")
        item.buildingCoverageRatio = specs.get(self.selectors.get('kenpei_key', "建ぺい率"), "")
        item.floorAreaRatio = specs.get(self.selectors.get('youseki_key', "容積率"), "")
        item.roadAccess = specs.get(self.selectors.get('setsudou_key', "接道状況"), "")
        item.facilities = specs.get(self.selectors.get('setsubi_key', "設備"), "")
        item.currentStatus = specs.get(self.selectors.get('genkyo_key', "現況"), "")
        item.deliveryDate = specs.get(self.selectors.get('hikiwatashi_key', "引　渡"), "")
        item.transactionMode = specs.get(self.selectors.get('torihiki_key', "取引態様"), "")
        item.remarks = specs.get(self.selectors.get('biko_key', "備　考"), "")
        item.updateDate = specs.get(self.selectors.get('update_date_key', "更新日"), "")
        item.nextUpdateDate = specs.get(self.selectors.get('next_update_date_key', "次回更新予定日"), "")
        
        return item
