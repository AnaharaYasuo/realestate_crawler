from bs4 import BeautifulSoup
from django.db import models
import logging
import re
from package.parser.investmentParser import InvestmentParser
from package.parser.baseParser import ReadPropertyNameException
from package.models.nomura import NomuraInvestmentModel
from package.utils import converter

class NomuraParser(InvestmentParser):
    def getCharset(self):
        return "utf-8"

    def createEntity(self) -> models.Model:
        return NomuraInvestmentModel()

    def _parsePropertyDetailPage(self, item: NomuraInvestmentModel, response: BeautifulSoup) -> models.Model:
        # Title
        title_el = response.select_one("h1.c_title_primary")
        if not title_el:
             title_el = response.select_one("h1")
        
        if title_el:
            item.propertyName = self._clean_text(title_el.get_text())
        else:
            raise ReadPropertyNameException()

        # Property Type Detection from breadcrumbs or title
        # Breadcrumbs: /pro/ -> [Type] -> [Details]
        breadcrumb_els = response.select(".c_breadcrumb_item")
        property_type = ""
        if len(breadcrumb_els) >= 3:
            property_type = self._clean_text(breadcrumb_els[2].get_text())
        
        # Price - Nomura Pro details often have price in .c_price_primary_value or .c_price_primary_text
        price_el = response.select_one(".c_price_primary_value")
        if not price_el:
            price_el = response.select_one(".c_price_primary_text")
        
        # Fallback for price if not in primary classes
        if not price_el:
            price_el = response.find(string=lambda t: t and ("万円" in t or "億円" in t))
        
        item.priceStr = self._clean_text(price_el.get_text() if hasattr(price_el, 'get_text') else price_el)
        item.price = self._parse_price(item.priceStr)

        # Spec Table
        specs = {}
        table = response.select_one("table.c_table_spec")
        if table:
            rows = table.select("tr")
            for row in rows:
                th = row.select_one("th")
                td = row.select_one("td")
                if th and td:
                    label = self._clean_text(th.get_text())
                    value = self._clean_text(td.get_text())
                    specs[label] = value
        
        # Base mapping
        item.address = specs.get("所在地", "")
        item.traffic = specs.get("交通", "")
        item.structure = specs.get("構造", "")
        item.yearBuilt = specs.get("築年月", "")
        item.currentStatus = specs.get("現況", "")
        
        yield_val = specs.get("利回り", "") or specs.get("表面利回り", "")
        item.grossYield = self._parse_yield(yield_val)
        
        # Type specific area mapping
        if "マンション" in property_type:
            item.buildingArea = specs.get("専有面積", "")
            item.landArea = specs.get("土地権利", "") # Often doesn't have land area for condo but right
        elif "土地" in property_type:
            item.landArea = specs.get("土地面積", "")
            item.buildingArea = None
        else: # Building or House
            item.landArea = specs.get("土地面積", "")
            item.buildingArea = specs.get("建物面積", "") or specs.get("延床面積", "")

        return item

    def parsePropertyListPage(self, response: BeautifulSoup):
        # Find property links
        # Pattern: /pro/bukken_local_id/[ID]/
        links = response.select("a[href*='/pro/bukken_local_id/']")
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
        next_link = response.select_one("a.next")
        if next_link:
            return next_link.get("href")
        return None

# Residential Parsers inheriting basic logic or defining new one
# Assuming residential follows a similar structure or we use generic logic for now
class NomuraResidentialBaseHelper:
    def parse_common(self, item, response):
        # Title
        title_el = response.select_one("h1")
        if title_el:
            item.propertyName = title_el.get_text(strip=True)
            
        # Price
        price_el = response.select_one(".price") or response.find(string=lambda t: t and "万円" in t)
        if price_el:
            item.priceStr = price_el.get_text(strip=True) if hasattr(price_el, 'get_text') else price_el.strip()
            item.price = converter.parse_price(item.priceStr)
        
        # Specs (DL/DT/DD or Table)
        # Try finding table with th/td
        specs = {}
        for tr in response.select("tr"):
            th = tr.select_one("th")
            td = tr.select_one("td")
            if th and td:
                specs[th.get_text(strip=True)] = td.get_text(strip=True)
        
        # Fallback to dl/dt/dd
        if not specs:
             for dl in response.select("dl"):
                dt = dl.select_one("dt")
                dd = dl.select_one("dd")
                if dt and dd:
                    specs[dt.get_text(strip=True)] = dd.get_text(strip=True)

        item.address = specs.get("所在地", "")
        item.traffic = specs.get("交通", "")
        return specs


class NomuraMansionParser(InvestmentParser, NomuraResidentialBaseHelper):
    def createEntity(self):
        from package.models.nomura import NomuraMansion
        return NomuraMansion()
        
    def _parsePropertyDetailPage(self, item, response):
        specs = self.parse_common(item, response)
        item.madori = specs.get("間取り", "")
        item.senyuMensekiStr = specs.get("専有面積", "")
        item.yearBuilt = specs.get("築年月", "")
        
        item.balconyArea = specs.get("バルコニー面積", "")
        item.facing = specs.get("向き", "")
        item.otherArea = specs.get("その他面積", "")
        item.structure = specs.get("構造", "")
        item.floorNumber = specs.get("所在階", "")
        item.totalUnits = specs.get("総戸数", "")
        item.landRights = specs.get("土地権利", "")
        item.zoning = specs.get("用途地域", "")
        item.managementCompany = specs.get("管理会社", "")
        item.managementForm = specs.get("管理形態", "")
        item.manager = specs.get("管理員", "")
        item.managementFee = specs.get("管理費", "")
        item.repairReserveFund = specs.get("修繕積立金", "")
        item.otherFees = specs.get("その他使用料", "")
        item.parking = specs.get("駐車場", "")
        item.currentStatus = specs.get("現況", "")
        item.deliveryDate = specs.get("引　渡", "")
        item.transactionMode = specs.get("取引態様", "")
        item.remarks = specs.get("備　考", "")
        item.updateDate = specs.get("更新日", "")
        item.nextUpdateDate = specs.get("次回更新予定日", "")
        
        return item

class NomuraKodateParser(InvestmentParser, NomuraResidentialBaseHelper):
    def createEntity(self):
        from package.models.nomura import NomuraKodate
        return NomuraKodate()

    def _parsePropertyDetailPage(self, item, response):
        specs = self.parse_common(item, response)
        
        # Basic Residential Fields
        item.landArea = specs.get("土地面積", "")
        item.buildingArea = specs.get("建物面積", "")
        item.structure = specs.get("構造", "")
        item.yearBuilt = specs.get("築年月", "")
        
        # Extended Fields
        item.parking = specs.get("駐車場", "")
        item.landRights = specs.get("土地権利", "")
        item.landCategory = specs.get("地目", "")
        item.privateRoadBurden = specs.get("私道負担", "")
        item.setback = specs.get("セットバック", "")
        item.cityPlanning = specs.get("都市計画", "")
        item.zoning = specs.get("用途地域", "")
        item.buildingCoverageRatio = specs.get("建ぺい率", "")
        item.floorAreaRatio = specs.get("容積率", "")
        item.roadAccess = specs.get("接道状況", "")
        item.facilities = specs.get("設備", "")
        item.currentStatus = specs.get("現況", "")
        item.deliveryDate = specs.get("引　渡", "")
        item.transactionMode = specs.get("取引態様", "")
        item.remarks = specs.get("備　考", "")
        item.updateDate = specs.get("更新日", "")
        item.nextUpdateDate = specs.get("次回更新予定日", "")
        
        return item

class NomuraTochiParser(InvestmentParser, NomuraResidentialBaseHelper):
    def createEntity(self):
        from package.models.nomura import NomuraTochi
        return NomuraTochi()

    def _parsePropertyDetailPage(self, item, response):
        specs = self.parse_common(item, response)
        
        item.landArea = specs.get("土地面積", "")
        
        # Extended Fields
        item.landRights = specs.get("土地権利", "")
        item.landCategory = specs.get("地目", "")
        item.privateRoadBurden = specs.get("私道負担", "")
        item.setback = specs.get("セットバック", "")
        item.cityPlanning = specs.get("都市計画", "")
        item.zoning = specs.get("用途地域", "")
        item.buildingCoverageRatio = specs.get("建ぺい率", "")
        item.floorAreaRatio = specs.get("容積率", "")
        item.roadAccess = specs.get("接道状況", "")
        item.facilities = specs.get("設備", "")
        item.currentStatus = specs.get("現況", "")
        item.deliveryDate = specs.get("引　渡", "")
        item.transactionMode = specs.get("取引態様", "")
        item.remarks = specs.get("備　考", "")
        item.updateDate = specs.get("更新日", "")
        item.nextUpdateDate = specs.get("次回更新予定日", "")
        
        return item
