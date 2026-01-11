from bs4 import BeautifulSoup
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestment
from package.parser.baseParser import ParserBase, ReadPropertyNameException
import re
import datetime

class MisawaParser(ParserBase):
    BASE_URL = 'https://www.misawa-mrd.co.jp'

    def __init__(self, property_type):
        self.property_type = property_type

    def getCharset(self):
        return 'utf-8'

    def createEntity(self):
        if self.property_type == '1': # Mansion
            return MisawaMansion()
        elif self.property_type == '2': # Kodate
            return MisawaKodate()
        elif self.property_type == '3': # Tochi
            return MisawaTochi()
        elif self.property_type == '4': # Investment
            return MisawaInvestment()
        return None

    def getRootXpath(self):
        return "//ul[contains(@class, 'bukken-list')]/li/a/@href"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith("http"):
            return linkUrl
        return self.BASE_URL + linkUrl

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # Basic Info
        # Misawa's new structure uses h2 for bukken name sometimes, or different h1
        title_tag = response.select_one('h1.detail-title')
        if not title_tag:
            title_tag = response.select_one('h2')
        if not title_tag:
            title_tag = response.select_one('h1')

        if title_tag:
            item.propertyName = title_tag.get_text(strip=True)
        else:
            raise ReadPropertyNameException()

        price_tag = response.select_one('.detail-price .num')
        if price_tag:
            item.priceStr = price_tag.get_text(strip=True)
            item.price = self._parse_price(item.priceStr)

        address_tag = response.select_one('.detail-address')
        if address_tag:
            item.address = address_tag.get_text(strip=True)

        # Parse Dictionary from Table
        table_data = {}
        rows = response.select('table.detail-spec tr')
        for row in rows:
            th = row.select_one('th')
            td = row.select_one('td')
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                table_data[key] = val

        # Common Fields Map
        self._map_common_fields(item, table_data)

        # Type Specific Fields
        if isinstance(item, MisawaMansion):
            self._map_mansion_fields(item, table_data)
        elif isinstance(item, MisawaKodate):
            self._map_kodate_fields(item, table_data)
        elif isinstance(item, MisawaTochi):
            self._map_tochi_fields(item, table_data)
        elif isinstance(item, MisawaInvestment):
            self._map_investment_fields(item, table_data)

        # Timestamps
        item.inputDate = datetime.date.today()
        item.inputDateTime = datetime.datetime.now()
        
        return item

    def _map_common_fields(self, item, data):
        # Railway/Station needs parsing from data.get('交通') or '沿線・駅'
        # Simplified for now to take raw text
        traffic = data.get('交通') or data.get('沿線・駅')
        if traffic:
            # Example: "JR山手線 新宿駅 徒歩10分"
            parts = traffic.split()
            if len(parts) >= 1:
                 item.railway1 = parts[0] # Very rough heuristics
            if len(parts) >= 2:
                 item.station1 = parts[1]
            
            # Extract walk minutes
            match = re.search(r'徒歩(\d+)分', traffic)
            if match:
                item.walkMinute1 = int(match.group(1))

        item.landTenure = data.get('権利', '') # or 土地権利
        item.kenpei = self._parse_percentage(data.get('建ぺい率'))
        item.youseki = self._parse_percentage(data.get('容積率'))
        item.zoning = data.get('用途地域', '')
        item.deliveryDate = data.get('引渡', '')
        item.facilities = data.get('設備', '')
        item.neighborhood = data.get('周辺環境', '')
        item.schoolDistrict = data.get('学校区', '')
        item.transactionType = data.get('取引態様', '')
        item.remarks = data.get('備考', '')

    def _map_mansion_fields(self, item, data):
        item.senyuMenseki = self._parse_area(data.get('専有面積'))
        item.balconyMenseki = self._parse_area(data.get('バルコニー面積'))
        item.madori = data.get('間取り', '')
        item.floor = data.get('所在階', '')
        item.structure = data.get('建物構造', '')
        item.completionDate = data.get('築年月') or data.get('完成時期', '')
        item.totalUnits = self._parse_int(data.get('総戸数'))
        item.managementType = data.get('管理形態', '')
        item.managementCompany = data.get('管理会社', '')
        item.managementFee = self._parse_money(data.get('管理費'))
        item.repairReserve = self._parse_money(data.get('修繕積立金'))
        item.parkingStatus = data.get('駐車場', '')

    def _map_kodate_fields(self, item, data):
        item.tochiMenseki = self._parse_area(data.get('土地面積'))
        item.tatemonoMenseki = self._parse_area(data.get('建物面積'))
        item.madori = data.get('間取り', '')
        item.structure = data.get('建物構造', '')
        item.completionDate = data.get('築年月') or data.get('完成時期', '')
        item.confirmationNumber = data.get('建築確認番号', '')
        item.roadCondition = data.get('接道状況', '')
        item.privateRoadFee = data.get('私道負担', '')
        item.setback = data.get('セットバック', '')
        item.urbanPlanning = data.get('都市計画', '')
        item.parkingCount = data.get('駐車場', '')

    def _map_tochi_fields(self, item, data):
        item.tochiMenseki = self._parse_area(data.get('土地面積'))
        item.landCategory = data.get('地目', '')
        item.roadCondition = data.get('接道状況', '')
        item.buildingCondition = data.get('建築条件', '')
        item.urbanPlanning = data.get('都市計画', '')
        item.currentStatus = data.get('現況', '')

    def _map_investment_fields(self, item, data):
        item.tochiMenseki = self._parse_area(data.get('土地面積'))
        item.tatemonoMenseki = self._parse_area(data.get('建物面積'))
        item.structure = data.get('建物構造', '')
        item.completionDate = data.get('築年月') or data.get('完成時期', '')
        item.yield_rate = self._parse_percentage(data.get('利回り'))
        item.annualIncome = self._parse_money(data.get('年間予定賃料収入'))
        item.madori = data.get('間取り', '')
        item.totalUnits = self._parse_int(data.get('総戸数'))
        item.roadCondition = data.get('接道状況', '')
        item.managementFee = self._parse_money(data.get('管理費等'))

    # Helper methods
    def _parse_price(self, text):
        if not text: return 0
        try:
            # Assume 3,580万円 -> 35800000
            val = text.replace(',', '').replace('万円', '')
            val = float(val) * 10000
            return int(val)
        except:
            return 0

    def _parse_money(self, text):
        if not text: return None
        try:
            # 10,000円 -> 10000
            val = re.sub(r'[^\d]', '', text)
            return int(val)
        except:
            return 0

    def _parse_area(self, text):
        if not text: return None
        try:
            val = re.search(r'([\d\.]+)', text)
            if val:
                return float(val.group(1))
        except:
            pass
        return None

    def _parse_percentage(self, text):
        if not text: return None
        try:
             # 5.5% -> 5.5
            val = re.search(r'([\d\.]+)', text)
            if val:
                return float(val.group(1))
        except:
            pass
        return None
        
    def _parse_int(self, text):
        if not text: return None
        try:
            val = re.sub(r'[^\d]', '', text)
            return int(val)
        except:
            return None
