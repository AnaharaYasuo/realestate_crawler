from bs4 import BeautifulSoup
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestment
from package.parser.baseParser import ParserBase, ReadPropertyNameException
import re
import datetime
from package.utils import converter

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
            item.price = converter.parse_price(item.priceStr)

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
        kenpei_str = data.get('建ぺい率')
        item.kenpei = int(kenpei_str.replace('%', '')) if kenpei_str and '%' in kenpei_str else 0
        youseki_str = data.get('容積率')
        item.youseki = int(youseki_str.replace('%', '')) if youseki_str and '%' in youseki_str else 0
        item.zoning = data.get('用途地域', '')
        item.deliveryDate = data.get('引渡', '')
        item.facilities = data.get('設備', '')
        item.neighborhood = data.get('周辺環境', '')
        item.schoolDistrict = data.get('学校区', '')
        item.transactionType = data.get('取引態様', '')
        item.remarks = data.get('備考', '')

    def _map_mansion_fields(self, item, data):
        item.senyuMenseki = converter.parse_menseki(data.get('専有面積', ''))
        item.balconyMenseki = converter.parse_menseki(data.get('バルコニー面積', ''))
        item.madori = data.get('間取り', '')
        item.floor = data.get('所在階', '')
        item.structure = data.get('建物構造', '')
        item.completionDate = data.get('築年月') or data.get('完成時期', '')
        item.totalUnits = converter.parse_numeric(data.get('総戸数', ''))
        item.managementType = data.get('管理形態', '')
        item.managementCompany = data.get('管理会社', '')
        item.managementFee = converter.parse_price(data.get('管理費', '')) if data.get('管理費') else 0
        item.repairReserve = converter.parse_price(data.get('修繕積立金', '')) if data.get('修繕積立金') else 0
        item.parkingStatus = data.get('駐車場', '')

    def _map_kodate_fields(self, item, data):
        item.tochiMenseki = converter.parse_menseki(data.get('土地面積', ''))
        item.tatemonoMenseki = converter.parse_menseki(data.get('建物面積', ''))
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
        item.tochiMenseki = converter.parse_menseki(data.get('土地面積', ''))
        item.landCategory = data.get('地目', '')
        item.roadCondition = data.get('接道状況', '')
        item.buildingCondition = data.get('建築条件', '')
        item.urbanPlanning = data.get('都市計画', '')
        item.currentStatus = data.get('現況', '')

    def _map_investment_fields(self, item, data):
        item.tochiMenseki = converter.parse_menseki(data.get('土地面積', ''))
        item.tatemonoMenseki = converter.parse_menseki(data.get('建物面積', ''))
        item.structure = data.get('建物構造', '')
        item.completionDate = data.get('築年月') or data.get('完成時期', '')
        yield_str = data.get('利回り', '')
        item.yield_rate = float(yield_str.replace('%', '')) if yield_str and '%' in yield_str else 0.0
        item.annualIncome = converter.parse_price(data.get('年間予定賃料収入', '')) if data.get('年間予定賃料収入') else 0
        item.madori = data.get('間取り', '')
        item.totalUnits = converter.parse_numeric(data.get('総戸数', ''))
        item.roadCondition = data.get('接道状況', '')
        item.managementFee = converter.parse_price(data.get('管理費等', '')) if data.get('管理費等') else 0

