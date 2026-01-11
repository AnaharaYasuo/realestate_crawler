from bs4 import BeautifulSoup
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestment
from package.parser.baseParser import ParserBase, ReadPropertyNameException
import re
import datetime
from package.utils import converter
from package.utils.selector_loader import SelectorLoader

class MisawaParser(ParserBase):
    BASE_URL = 'https://www.misawa-mrd.co.jp'

    def __init__(self, property_type):
        self.property_type_id = property_type
        # Map ID to string type
        type_map = {'1': 'mansion', '2': 'kodate', '3': 'tochi', '4': 'investment'}
        self.property_type = type_map.get(property_type, 'mansion')
        self.selectors = SelectorLoader.load('misawa', self.property_type)

    def getCharset(self):
        return 'utf-8'

    def createEntity(self):
        if self.property_type_id == '1': # Mansion
            return MisawaMansion()
        elif self.property_type_id == '2': # Kodate
            return MisawaKodate()
        elif self.property_type_id == '3': # Tochi
            return MisawaTochi()
        elif self.property_type_id == '4': # Investment
            return MisawaInvestment()
        return None

    def getRootXpath(self):
        return self.selectors.get('root_xpath', "//ul[contains(@class, 'bukken-list')]/li/a/@href")

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith("http"):
            return linkUrl
        return self.BASE_URL + linkUrl

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # Basic Info
        # Misawa's new structure uses h2 for bukken name sometimes, or different h1
        title_selector = self.selectors.get('title', 'h1.detail-title')
        title_tag = response.select_one(title_selector)
        if not title_tag:
            title_tag = response.select_one(self.selectors.get('title_fallback_2', 'h2'))
        if not title_tag:
            title_tag = response.select_one(self.selectors.get('title_fallback', 'h1'))

        if title_tag:
            item.propertyName = title_tag.get_text(strip=True)
        else:
            raise ReadPropertyNameException()

        price_selector = self.selectors.get('price', '.detail-price .num')
        price_tag = response.select_one(price_selector)
        if price_tag:
            item.priceStr = price_tag.get_text(strip=True)
            item.price = converter.parse_price(item.priceStr)

        address_selector = self.selectors.get('address', '.detail-address')
        address_tag = response.select_one(address_selector)
        if address_tag:
            item.address = address_tag.get_text(strip=True)

        # Parse Dictionary from Table
        table_data = {}
        table_config = self.selectors.get('table', {})
        table_selector = table_config.get('selector', 'table.detail-spec')
        row_selector = table_config.get('row', 'tr')
        header_selector = table_config.get('header', 'th')
        value_selector = table_config.get('value', 'td')

        rows = response.select(f'{table_selector} {row_selector}')
        for row in rows:
            th = row.select_one(header_selector)
            td = row.select_one(value_selector)
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
        traffic_key = self.selectors.get('traffic_key', '交通')
        traffic_fallback = self.selectors.get('traffic_fallback_key', '沿線・駅')
        traffic = data.get(traffic_key) or data.get(traffic_fallback)
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

        item.landTenure = data.get(self.selectors.get('kenri_key', '権利')) or data.get(self.selectors.get('kenri_fallback_key', '土地権利'), '')
        kenpei_str = data.get(self.selectors.get('kenpei_key', '建ぺい率'))
        item.kenpei = int(kenpei_str.replace('%', '')) if kenpei_str and '%' in kenpei_str else 0
        youseki_str = data.get(self.selectors.get('youseki_key', '容積率'))
        item.youseki = int(youseki_str.replace('%', '')) if youseki_str and '%' in youseki_str else 0
        item.zoning = data.get(self.selectors.get('youto_chiiki_key', '用途地域'), '')
        item.deliveryDate = data.get(self.selectors.get('hikiwatashi_key', '引渡'), '')
        item.facilities = data.get(self.selectors.get('setsubi_key', '設備'), '')
        item.neighborhood = data.get(self.selectors.get('kankyo_key', '周辺環境'), '')
        item.schoolDistrict = data.get(self.selectors.get('school_key', '学校区'), '')
        item.transactionType = data.get(self.selectors.get('torihiki_key', '取引態様'), '')
        item.remarks = data.get(self.selectors.get('biko_key', '備考'), '')

    def _map_mansion_fields(self, item, data):
        item.senyuMenseki = converter.parse_menseki(data.get(self.selectors.get('senyu_menseki_key', '専有面積'), ''))
        item.balconyMenseki = converter.parse_menseki(data.get(self.selectors.get('balcony_key', 'バルコニー面積'), ''))
        item.madori = data.get(self.selectors.get('madori_key', '間取り'), '')
        item.floor = data.get(self.selectors.get('floor_key', '所在階'), '')
        item.structure = data.get(self.selectors.get('structure_key', '建物構造'), '')
        item.completionDate = data.get(self.selectors.get('chikunengetsu_key')) or data.get(self.selectors.get('kansei_key', '完成時期'), '')
        item.totalUnits = converter.parse_numeric(data.get(self.selectors.get('soukosu_key', '総戸数'), ''))
        item.managementType = data.get(self.selectors.get('kanri_keitai_key', '管理形態'), '')
        item.managementCompany = data.get(self.selectors.get('kanri_kaisya_key', '管理会社'), '')
        item.managementFee = converter.parse_price(data.get(self.selectors.get('kanrihi_key', '管理費'))) if data.get(self.selectors.get('kanrihi_key')) else 0
        item.repairReserve = converter.parse_price(data.get(self.selectors.get('syuzen_tsumitate_key', '修繕積立金'))) if data.get(self.selectors.get('syuzen_tsumitate_key')) else 0
        item.parkingStatus = data.get(self.selectors.get('parking_key', '駐車場'), '')

    def _map_kodate_fields(self, item, data):
        item.tochiMenseki = converter.parse_menseki(data.get(self.selectors.get('tochi_menseki_key', '土地面積'), ''))
        item.tatemonoMenseki = converter.parse_menseki(data.get(self.selectors.get('tatemono_menseki_key', '建物面積'), ''))
        item.madori = data.get(self.selectors.get('madori_key', '間取り'), '')
        item.structure = data.get(self.selectors.get('structure_key', '建物構造'), '')
        item.completionDate = data.get(self.selectors.get('chikunengetsu_key')) or data.get(self.selectors.get('kansei_key', '完成時期'), '')
        item.confirmationNumber = data.get(self.selectors.get('kakunin_key', '建築確認番号'), '')
        item.roadCondition = data.get(self.selectors.get('setsudou_key', '接道状況'), '')
        item.privateRoadFee = data.get(self.selectors.get('shido_futan_key', '私道負担'), '')
        item.setback = data.get(self.selectors.get('setback_key', 'セットバック'), '')
        item.urbanPlanning = data.get(self.selectors.get('toshi_keikaku_key', '都市計画'), '')
        item.parkingCount = data.get(self.selectors.get('parking_key', '駐車場'), '')

    def _map_tochi_fields(self, item, data):
        item.tochiMenseki = converter.parse_menseki(data.get(self.selectors.get('tochi_menseki_key', '土地面積'), ''))
        item.landCategory = data.get(self.selectors.get('chimoku_key', '地目'), '')
        item.roadCondition = data.get(self.selectors.get('setsudou_key', '接道状況'), '')
        item.buildingCondition = data.get(self.selectors.get('kenchiku_joken_key', '建築条件'), '')
        item.urbanPlanning = data.get(self.selectors.get('toshi_keikaku_key', '都市計画'), '')
        item.currentStatus = data.get(self.selectors.get('genkyo_key', '現況'), '')

    def _map_investment_fields(self, item, data):
        item.tochiMenseki = converter.parse_menseki(data.get(self.selectors.get('tochi_menseki_key', '土地面積'), ''))
        item.tatemonoMenseki = converter.parse_menseki(data.get(self.selectors.get('tatemono_menseki_key', '建物面積'), ''))
        item.structure = data.get(self.selectors.get('structure_key', '建物構造'), '')
        item.completionDate = data.get(self.selectors.get('chikunengetsu_key')) or data.get(self.selectors.get('kansei_key', '完成時期'), '')
        yield_str = data.get(self.selectors.get('yield_key', '利回り'), '')
        item.yield_rate = float(yield_str.replace('%', '')) if yield_str and '%' in yield_str else 0.0
        item.annualIncome = converter.parse_price(data.get(self.selectors.get('income_key', '年間予定賃料収入'))) if data.get(self.selectors.get('income_key')) else 0
        item.madori = data.get(self.selectors.get('madori_key', '間取り'), '')
        item.totalUnits = converter.parse_numeric(data.get(self.selectors.get('soukosu_key', '総戸数'), ''))
        item.roadCondition = data.get(self.selectors.get('setsudou_key', '接道状況'), '')
        item.managementFee = converter.parse_price(data.get(self.selectors.get('kanrihi_key', '管理費等'))) if data.get(self.selectors.get('kanrihi_key')) else 0

