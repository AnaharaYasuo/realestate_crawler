from bs4 import BeautifulSoup
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentApartment, MisawaInvestmentKodate
from package.parser.baseParser import ParserBase, ReadPropertyNameException
import re
import datetime
import logging
from package.utils import converter
from package.utils.selector_loader import SelectorLoader
from decimal import Decimal, ROUND_HALF_UP


class MisawaParser(ParserBase):
    """Misawa共通基底クラス"""
    BASE_URL = 'https://realestate.misawa.co.jp'
    property_type = None  # Subclasses must define

    def __init__(self, params=None):
        if self.property_type:
            self.selectors = SelectorLoader.load('misawa', self.property_type)

    def getCharset(self):
        return None  # Auto-detect

    async def parsePropertyListPage(self, response: BeautifulSoup):
        sections = response.select('div.searchList div.section')
        
        if not sections:
             links = response.select('a[href*="detail_"]')
             for link in links:
                 yield self.getRootDestUrl(link.get('href'))
             return

        for section in sections:
            a_tag = section.select_one('h3 a')
            if a_tag and a_tag.get('href'):
                href = a_tag.get('href')
                full_url = self.getRootDestUrl(href)
                yield full_url

    async def parseNextPage(self, response: BeautifulSoup):
        next_tag = response.select_one('li.next a')
        if next_tag and next_tag.get('href'):
            return self.getRootDestUrl(next_tag.get('href'))
        return ""

    def getRootXpath(self):
        return self.selectors.get('root_xpath', "//ul[contains(@class, 'bukken-list')]/li/a/@href")

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith("http"):
            return linkUrl
        return self.BASE_URL + linkUrl

    def _get_specs(self, response: BeautifulSoup):
        if not hasattr(self, '_specs_cache'):
             self._specs_cache = {}
        
        # Check if response object is the same (simple check)
        # In a real scenario, we might want to tag the response object
        if getattr(self, '_last_response_id', None) != id(response):
             self._specs_cache = {}
             self._last_response_id = id(response)
             
        if not self._specs_cache:
             table_data = self._scrape_to_dict(response)
             self._specs_cache = {k: v.get_text(strip=True) for k, v in table_data.items()}
             
        return self._specs_cache

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        # Basic Info
        item.propertyName = self._parsePropertyName(response)
        item.priceStr = self._parsePriceStr(response)
        item.price = self._parsePrice(response)
        item.address = self._parseAddress(response)

        # Traffic
        item.railwayCount = self._parseRailwayCount(response)
        
        item.transfer1 = self._parseTransfer1(response)
        item.railway1 = self._parseRailway1(response)
        item.station1 = self._parseStation1(response)
        item.railwayWalkMinute1Str = self._parseRailwayWalkMinute1Str(response)
        item.railwayWalkMinute1 = self._parseRailwayWalkMinute1(response)
        item.busStation1 = self._parseBusStation1(response)
        item.busWalkMinute1Str = self._parseBusWalkMinute1Str(response)
        item.busWalkMinute1 = self._parseBusWalkMinute1(response)
        item.busUse1 = self._parseBusUse1(response)
        
        item.transfer2 = self._parseTransfer2(response)
        item.railway2 = self._parseRailway2(response)
        item.station2 = self._parseStation2(response)
        item.railwayWalkMinute2Str = self._parseRailwayWalkMinute2Str(response)
        item.railwayWalkMinute2 = self._parseRailwayWalkMinute2(response)
        item.busStation2 = self._parseBusStation2(response)
        item.busWalkMinute2Str = self._parseBusWalkMinute2Str(response)
        item.busWalkMinute2 = self._parseBusWalkMinute2(response)
        item.busUse2 = self._parseBusUse2(response)
        
        item.transfer3 = self._parseTransfer3(response)
        item.railway3 = self._parseRailway3(response)
        item.station3 = self._parseStation3(response)
        item.railwayWalkMinute3Str = self._parseRailwayWalkMinute3Str(response)
        item.railwayWalkMinute3 = self._parseRailwayWalkMinute3(response)
        item.busStation3 = self._parseBusStation3(response)
        item.busWalkMinute3Str = self._parseBusWalkMinute3Str(response)
        item.busWalkMinute3 = self._parseBusWalkMinute3(response)
        item.busUse3 = self._parseBusUse3(response)
        
        item.transfer4 = self._parseTransfer4(response)
        item.railway4 = self._parseRailway4(response)
        item.station4 = self._parseStation4(response)
        item.railwayWalkMinute4Str = self._parseRailwayWalkMinute4Str(response)
        item.railwayWalkMinute4 = self._parseRailwayWalkMinute4(response)
        item.busStation4 = self._parseBusStation4(response)
        item.busWalkMinute4Str = self._parseBusWalkMinute4Str(response)
        item.busWalkMinute4 = self._parseBusWalkMinute4(response)
        item.busUse4 = self._parseBusUse4(response)

        item.transfer5 = self._parseTransfer5(response)
        item.railway5 = self._parseRailway5(response)
        item.station5 = self._parseStation5(response)
        item.railwayWalkMinute5Str = self._parseRailwayWalkMinute5Str(response)
        item.railwayWalkMinute5 = self._parseRailwayWalkMinute5(response)
        item.busStation5 = self._parseBusStation5(response)
        item.busWalkMinute5Str = self._parseBusWalkMinute5Str(response)
        item.busWalkMinute5 = self._parseBusWalkMinute5(response)
        item.busUse5 = self._parseBusUse5(response)

        # Common Fields
        item.tochikenri = self._parseTochikenri(response)
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)
        item.youtoChiiki = self._parseYoutoChiiki(response)
        item.deliveryDate = self._parseDeliveryDate(response)
        item.facilities = self._parseFacilities(response)
        item.neighborhood = self._parseNeighborhood(response)
        item.schoolDistrict = self._parseSchoolDistrict(response)
        item.transactionType = self._parseTransactionType(response)
        item.biko = self._parseBiko(response)
        item.kakuninBango = self._parseKakuninBango(response)
        item.setback = self._parseSetback(response)
        item.urbanPlanning = self._parseUrbanPlanning(response)
        item.privateRoadFee = self._parsePrivateRoadFee(response)
        item.infoUpdateDate = self._parseInfoUpdateDate(response)
        item.nextUpdateDate = self._parseNextUpdateDate(response)

        # Timestamps
        item.inputDate = datetime.date.today()
        item.inputDateTime = datetime.datetime.now()
        
        return item
    
    def _parsePropertyName(self, response):
        title_tag = response.select_one(self.selectors.get('title', 'h2.title'))
        if not title_tag:
            title_tag = response.select_one(self.selectors.get('title_fallback', 'h1'))
        if not title_tag:
            title_tag = response.select_one(self.selectors.get('title_fallback_2', 'h2'))

        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove "物件番号：XXXXXX" if present
            title = re.sub(r'物件番号：\d+$', '', title).strip()
            return title
        
        raise ReadPropertyNameException("Could not find property name in Misawa detail page")

    def _parsePriceStr(self, response):
        price_selector = self.selectors.get('price', '.detail-price .num')
        price_tag = response.select_one(price_selector)
        return price_tag.get_text(strip=True) if price_tag else ""

    def _parsePrice(self, response):
        priceStr = self._parsePriceStr(response)
        return converter.parse_price(priceStr)

    def _parseAddress(self, response):
        address_selector = self.selectors.get('address', '.detail-address')
        address_tag = response.select_one(address_selector)
        return address_tag.get_text(strip=True) if address_tag else ""

    def _parseTrafficFull(self, response):
        specs = self._get_specs(response)
        traffic_key = self.selectors.get('traffic_key', '交通')
        traffic_fallback = self.selectors.get('traffic_fallback_key', '沿線・駅')
        return specs.get(traffic_key) or specs.get(traffic_fallback)

    def _parseTrafficMatches(self, response):
        traffic = self._parseTrafficFull(response)
        if not traffic: return []
        
        norm_traffic = traffic.replace("・", " ").replace("　", " ")
        # Try various patterns
        # 1. Standard pattern: 線駅 徒歩/バス分
        matches = re.findall(r'(\S+線)\s+(\S+駅)\s*(.*?(?:徒歩|停歩|バス)\s*\d+\s*分(?:.*?停歩\s*\d+\s*分)?)', norm_traffic)
        
        if not matches:
             # 2. Bracketed station name: 線 「駅」 徒歩/バス分
             matches = re.findall(r'([^「」\s]+(?:線|ライン|ライナー|鉄道)?)\s*「([^「」]+)」\s*(.*?(?:徒歩|停歩|バス)\s*\d+\s*分(?:.*?停歩\s*\d+\s*分)?)', norm_traffic)
        
        if not matches:
             # 3. Simple sequence: 沿線 駅 徒歩分
             matches = re.findall(r'(\S+)\s+(\S+駅)\s*(徒歩|停歩|バス)\s*(\d+)\s*分', norm_traffic)
             if matches:
                 # Standardize to (railway, station, access)
                 matches = [(m[0], m[1], f"{m[2]}{m[3]}分") for m in matches]

        return matches

    def _parseRailwayCount(self, response):
        return len(self._parseTrafficMatches(response))

    def _getTrafficField(self, response, index, field_to_get, default):
        matches = self._parseTrafficMatches(response)
        if index > len(matches): return default
        
        match = matches[index-1]
        railway, station, walk_access = match[0].strip(), match[1].strip(), match[2].strip()
        
        if field_to_get == 'transfer':
            return f"{railway}「{station}」{walk_access}"
        elif field_to_get == 'railway':
            return railway
        elif field_to_get == 'station':
            return station
        elif field_to_get == 'railwayWalkMinuteStr':
            m_walk = re.search(r'(?:徒歩|停歩)\s*(\d+)\s*分', walk_access)
            return str(m_walk.group(1)) if m_walk else default
        elif field_to_get == 'railwayWalkMinute':
             m_walk = re.search(r'(?:徒歩|停歩)\s*(\d+)\s*分', walk_access)
             return int(m_walk.group(1)) if m_walk else 0
        elif field_to_get == 'busWalkMinuteStr':
            m_bus = re.search(r'バス\s*(\d+)\s*分', walk_access)
            return str(m_bus.group(1)) if m_bus else default
        elif field_to_get == 'busWalkMinute':
            m_bus = re.search(r'バス\s*(\d+)\s*分', walk_access)
            return int(m_bus.group(1)) if m_bus else 0
        elif field_to_get == 'busStation':
             m_stop = re.search(r'「([^」]+)」', walk_access)
             return m_stop.group(1) if m_stop else default
        elif field_to_get == 'busUse':
             return 1 if "バス" in walk_access else 0
            
        return default

    def _parseTransfer1(self, response): return self._getTrafficField(response, 1, 'transfer', "")
    def _parseRailway1(self, response): return self._getTrafficField(response, 1, 'railway', "")
    def _parseStation1(self, response): return self._getTrafficField(response, 1, 'station', "")
    def _parseRailwayWalkMinute1Str(self, response): return self._getTrafficField(response, 1, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute1(self, response): return self._getTrafficField(response, 1, 'railwayWalkMinute', 0)
    def _parseBusStation1(self, response): return self._getTrafficField(response, 1, 'busStation', "")
    def _parseBusWalkMinute1Str(self, response): return self._getTrafficField(response, 1, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute1(self, response): return self._getTrafficField(response, 1, 'busWalkMinute', 0)
    def _parseBusUse1(self, response): return self._getTrafficField(response, 1, 'busUse', 0)

    def _parseTransfer2(self, response): return self._getTrafficField(response, 2, 'transfer', "")
    def _parseRailway2(self, response): return self._getTrafficField(response, 2, 'railway', "")
    def _parseStation2(self, response): return self._getTrafficField(response, 2, 'station', "")
    def _parseRailwayWalkMinute2Str(self, response): return self._getTrafficField(response, 2, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute2(self, response): return self._getTrafficField(response, 2, 'railwayWalkMinute', 0)
    def _parseBusStation2(self, response): return self._getTrafficField(response, 2, 'busStation', "")
    def _parseBusWalkMinute2Str(self, response): return self._getTrafficField(response, 2, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute2(self, response): return self._getTrafficField(response, 2, 'busWalkMinute', 0)
    def _parseBusUse2(self, response): return self._getTrafficField(response, 2, 'busUse', 0)

    def _parseTransfer3(self, response): return self._getTrafficField(response, 3, 'transfer', "")
    def _parseRailway3(self, response): return self._getTrafficField(response, 3, 'railway', "")
    def _parseStation3(self, response): return self._getTrafficField(response, 3, 'station', "")
    def _parseRailwayWalkMinute3Str(self, response): return self._getTrafficField(response, 3, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute3(self, response): return self._getTrafficField(response, 3, 'railwayWalkMinute', 0)
    def _parseBusStation3(self, response): return self._getTrafficField(response, 3, 'busStation', "")
    def _parseBusWalkMinute3Str(self, response): return self._getTrafficField(response, 3, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute3(self, response): return self._getTrafficField(response, 3, 'busWalkMinute', 0)
    def _parseBusUse3(self, response): return self._getTrafficField(response, 3, 'busUse', 0)

    def _parseTransfer4(self, response): return self._getTrafficField(response, 4, 'transfer', "")
    def _parseRailway4(self, response): return self._getTrafficField(response, 4, 'railway', "")
    def _parseStation4(self, response): return self._getTrafficField(response, 4, 'station', "")
    def _parseRailwayWalkMinute4Str(self, response): return self._getTrafficField(response, 4, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute4(self, response): return self._getTrafficField(response, 4, 'railwayWalkMinute', 0)
    def _parseBusStation4(self, response): return self._getTrafficField(response, 4, 'busStation', "")
    def _parseBusWalkMinute4Str(self, response): return self._getTrafficField(response, 4, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute4(self, response): return self._getTrafficField(response, 4, 'busWalkMinute', 0)
    def _parseBusUse4(self, response): return self._getTrafficField(response, 4, 'busUse', 0)

    def _parseTransfer5(self, response): return self._getTrafficField(response, 5, 'transfer', "")
    def _parseRailway5(self, response): return self._getTrafficField(response, 5, 'railway', "")
    def _parseStation5(self, response): return self._getTrafficField(response, 5, 'station', "")
    def _parseRailwayWalkMinute5Str(self, response): return self._getTrafficField(response, 5, 'railwayWalkMinuteStr', "")
    def _parseRailwayWalkMinute5(self, response): return self._getTrafficField(response, 5, 'railwayWalkMinute', 0)
    def _parseBusStation5(self, response): return self._getTrafficField(response, 5, 'busStation', "")
    def _parseBusWalkMinute5Str(self, response): return self._getTrafficField(response, 5, 'busWalkMinuteStr', "")
    def _parseBusWalkMinute5(self, response): return self._getTrafficField(response, 5, 'busWalkMinute', 0)
    def _parseBusUse5(self, response): return self._getTrafficField(response, 5, 'busUse', 0)

    def _parseTochikenri(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kenri_key', '権利')) or specs.get(self.selectors.get('kenri_fallback_key', '土地権利'), '')

    def _parseKenpeiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kenpei_key', '建ぺい率/容積率'), '')

    def _parseKenpei(self, response):
        kenpeiStr = self._parseKenpeiStr(response)
        if not kenpeiStr:
            return None
        # Handle "60% / 150%" format
        parts = kenpeiStr.split('/')
        if parts:
             val = parts[0].strip()
             try:
                 # Model expects Int, not Decimal
                 return int(Decimal(val.replace('%', '').strip()))
             except:
                 return None
        return None

    def _parseYousekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('youseki_key', '建ぺい率/容積率'), '')

    def _parseYouseki(self, response):
        yousekiStr = self._parseYousekiStr(response)
        if not yousekiStr:
            return None
        # Handle "60% / 150%" format
        parts = yousekiStr.split('/')
        if len(parts) > 1:
             val = parts[1].strip()
             try:
                 # Model expects Int, not Decimal
                 return int(Decimal(val.replace('%', '').strip()))
             except:
                 return None
        return None

    def _parseYoutoChiiki(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('youto_chiiki_key', '用途地域'), '')

    def _parseDeliveryDate(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('hikiwatashi_key', '引渡'), '')

    def _parseFacilities(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('setsubi_key', '設備'), '')

    def _parseNeighborhood(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('neighborhood_key', '周辺施設')) or "-"

    def _parseSchoolDistrict(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('school_district_key', '学区')) or "-"

    def _parseTransactionType(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('transaction_type_key', '取引態様')) or "-"
    
    def _parseUrbanPlanning(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('urban_planning_key', '都市計画')) or "-"

    def _parseKakuninBango(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kakunin_bango_key', '建築確認番号')) or "-"
        
    def _parseSetback(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('setback_key', 'セットバック')) or "-"

    def _parseBiko(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('biko_key', '備考')) or "-"

    def _parsePrivateRoadFee(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('shido_futan_key', '私道負担面積')) or "-"

    def _parseInfoUpdateDate(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('info_update_date_key', '情報更新日'), '')

    def _parseNextUpdateDate(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('next_update_date_key', '次回更新予定日'), '')


# ========== Mansion Parser ==========
class MisawaMansionParser(MisawaParser):
    property_type = 'mansion'
    
    def createEntity(self):
        return MisawaMansion()
        
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        
        item.senyuMensekiStr = self._parseSenyuMensekiStr(response)
        item.senyuMenseki = self._parseSenyuMenseki(response)
        item.balconyMensekiStr = self._parseBalconyMensekiStr(response)
        item.balconyMenseki = self._parseBalconyMenseki(response)
        item.madori = self._parseMadori(response)
        item.kaisu = self._parseKaisu(response)
        item.kouzou = self._parseKouzou(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.soukosuStr = self._parseTotalUnitsStr(response)
        item.soukosu = self._parseTotalUnits(response)
        item.kanriKeitai = self._parseManagementType(response)
        item.kanriKaisya = self._parseManagementCompany(response)
        item.kanrihiStr = self._parseManagementFeeStr(response)
        item.kanrihi = self._parseManagementFee(response)
        item.syuzenTsumitateStr = self._parseRepairReserveStr(response)
        item.syuzenTsumitate = self._parseRepairReserve(response)
        item.tyusyajo = self._parseParkingStatus(response)
        
        return item

    def _parseSenyuMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('senyu_menseki_key', '専有面積'), '')

    def _parseBalconyMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('balcony_key', 'バルコニー面積'), '')

    def _parseSenyuMenseki(self, response):
        return converter.parse_menseki(self._parseSenyuMensekiStr(response))

    def _parseBalconyMenseki(self, response):
        return converter.parse_menseki(self._parseBalconyMensekiStr(response))

    def _parseMadori(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('madori_key', '間取り'), '')

    def _parseKaisu(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('floor_key', '所在階'), '')

    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('structure_key', '建物構造'), '')

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('chikunengetsu_key')) or specs.get(self.selectors.get('kansei_key', '完成時期'), '')

    def _parseTotalUnitsStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('soukosu_key', '総戸数'), '')

    def _parseTotalUnits(self, response):
        return converter.parse_numeric(self._parseTotalUnitsStr(response))

    def _parseManagementType(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kanri_keitai_key', '管理形態'), '')

    def _parseManagementCompany(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kanri_kaisya_key', '管理会社'), '')

    def _parseManagementFeeStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kanrihi_key', '管理費'), '')

    def _parseManagementFee(self, response):
        val = self._parseManagementFeeStr(response)
        if not val:
            return None
        # if ends with '円' and doesn't contain '万', it's likely just Yen.
        # converter.parse_price adds *10000 at the end if no '万'/'億'
        # Wait, converter.parse_price(val) for "8,680円" -> 8680 * 10000 = 86,800,000
        # This is because it assumes the input is always in "Man-Yen" if no unit.
        if '円' in val and '万' not in val and '億' not in val:
            num_val = re.search(r'(\d+(?:,\d+)*)', val)
            if num_val:
                return int(num_val.group(1).replace(',', ''))
        return converter.parse_price(val)

    def _parseRepairReserveStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('syuzen_tsumitate_key', '修繕積立金'), '')

    def _parseRepairReserve(self, response):
        val = self._parseRepairReserveStr(response)
        if not val:
            return None
        if '円' in val and '万' not in val and '億' not in val:
            num_val = re.search(r'(\d+(?:,\d+)*)', val)
            if num_val:
                return int(num_val.group(1).replace(',', ''))
        return converter.parse_price(val)

    def _parseParkingStatus(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('parking_key', '駐車場'), '')


# ========== Kodate Parser ==========
class MisawaKodateParser(MisawaParser):
    property_type = 'kodate'
    
    def createEntity(self):
        return MisawaKodate()
        
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        item.madori = self._parseMadori(response)
        item.kouzou = self._parseKouzou(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.setsudou = self._parseSetsudou(response)
        item.tyusyajo = self._parseParkingCount(response)
        
        return item

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('tochi_menseki_key', '土地面積'), '')

    def _parseTatemonoMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('tatemono_menseki_key', '建物面積'), '')

    def _parseTochiMenseki(self, response):
        return converter.parse_menseki(self._parseTochiMensekiStr(response))

    def _parseTatemonoMenseki(self, response):
        return converter.parse_menseki(self._parseTatemonoMensekiStr(response))

    def _parseMadori(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('madori_key', '間取り'), '')

    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('structure_key', '建物構造'), '')

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('chikunengetsu_key')) or specs.get(self.selectors.get('kansei_key', '完成時期'), '')

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('setsudou_key', '接道状況'), '')

    def _parseParkingCount(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('parking_key', '駐車場'), '')


# ========== Tochi Parser ==========
class MisawaTochiParser(MisawaParser):
    property_type = 'tochi'
    
    def createEntity(self):
        return MisawaTochi()
        
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.chimoku = self._parseChimoku(response)
        item.setsudou = self._parseSetsudou(response)
        item.buildingCondition = self._parseBuildingCondition(response)
        item.currentStatus = self._parseCurrentStatus(response)
        
        return item

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('tochi_menseki_key', '土地面積'), '')

    def _parseTochiMenseki(self, response):
        specs = self._get_specs(response)
        return converter.parse_menseki(specs.get(self.selectors.get('tochi_menseki_key', '土地面積'), ''))

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('chimoku_key', '地目'), '')

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('setsudou_key', '接道状況'), '')

    def _parseBuildingCondition(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('kenchiku_joken_key', '建築条件'), '')

    def _parseCurrentStatus(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('genkyo_key', '現況'), '')


# ========== Investment Base Parser ==========
class MisawaInvestmentParser(MisawaParser):
    """投資用物件共通パーサー"""
    property_type = 'investment'
    
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        
        item.grossYield = self._parseGrossYield(response)
        item.annualRent = self._parseAnnualRent(response)
        item.monthlyRent = self._parseMonthlyRent(response)
        
        item.currentStatus = self._parseCurrentStatus(response)

        # Required base model fields (override common fields with investment-specific defaults)
        item.tochikenri = self._parseTochikenri_I(response)
        item.youtoChiiki = self._parseYoutoChiiki_I(response)
        item.deliveryDate = self._parseDeliveryDate_I(response)
        item.facilities = self._parseFacilities_I(response)
        item.neighborhood = self._parseNeighborhood_I(response)
        item.schoolDistrict = self._parseSchoolDistrict_I(response)
        item.transactionType = self._parseTransactionType_I(response)
        item.biko = self._parseBiko_I(response)
        
        item.kenpeiStr = self._parseKenpeiStr(response)
        item.kenpei = self._parseKenpei(response)
        item.yousekiStr = self._parseYousekiStr(response)
        item.youseki = self._parseYouseki(response)

        # Common investment fields
        item.kouzou = self._parseKouzou(response)
        item.chikunengetsuStr = self._parseChikunengetsuStr(response)
        item.chikunengetsu = self._parseChikunengetsu(response)
        item.tochiMensekiStr = self._parseTochiMensekiStr(response)
        item.tochiMenseki = self._parseTochiMenseki(response)
        item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response)
        item.tatemonoMenseki = self._parseTatemonoMenseki(response)
        
        return item

    def _parseGrossYield(self, response):
        specs = self._get_specs(response)
        yield_str = specs.get(self.selectors.get('yield_key', '利回り'), '')
        if yield_str:
            match = re.search(r'(\d+(?:\.\d+)?)', yield_str)
            if match:
                return Decimal(match.group(1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                logging.warning(f"Could not parse yield number from: {yield_str}")
                return None
        return None

    def _parseAnnualRent(self, response):
        specs = self._get_specs(response)
        val = specs.get(self.selectors.get('income_key', '年間予定賃料収入')) or \
              specs.get('年間想定賃料収入') or \
              specs.get('年間収入')
        return converter.parse_price(val)

    def _parseMonthlyRent(self, response):
        annualRent = self._parseAnnualRent(response)
        return (annualRent // 12) if annualRent else None

    def _parseCurrentStatus(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('status_key', '現況'), '') or specs.get('賃貸状況', '')

    def _parseTochikenri_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('tochikenri_key', '土地権利'), '') or "所有権"

    def _parseYoutoChiiki_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('youto_chiiki_key', '用途地域'), '')

    def _parseDeliveryDate_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('delivery_key', '引渡時期'), '') or "即時"

    def _parseFacilities_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('facilities_key', '設備'), '')

    def _parseNeighborhood_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('neighborhood_key', '周辺施設'), '')

    def _parseSchoolDistrict_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('school_key', '学区'), '')

    def _parseTransactionType_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('transaction_key', '取引態様'), '') or "仲介"

    def _parseBiko_I(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('remarks_key', '備考'), '')

    def _parseKouzou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('structure_key', '建物構造'), '')

    def _parseChikunengetsuStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('chikunengetsu_key')) or specs.get(self.selectors.get('kansei_key', '完成時期'), '')

    def _parseChikunengetsu(self, response):
        chikunengetsuStr = self._parseChikunengetsuStr(response)
        return converter.parse_chikunengetsu(chikunengetsuStr) if chikunengetsuStr else None

    def _parseTochiMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('tochi_menseki_key', '土地面積'), '')

    def _parseTochiMenseki(self, response):
        return converter.parse_menseki(self._parseTochiMensekiStr(response))

    def _parseTatemonoMensekiStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('tatemono_menseki_key', '建物面積'), '') or \
               specs.get('延床面積') or specs.get('専有面積', '')

    def _parseTatemonoMenseki(self, response):
        return converter.parse_menseki(self._parseTatemonoMensekiStr(response))


# ========== Investment Kodate Parser ==========
class MisawaInvestmentKodateParser(MisawaInvestmentParser):
    def createEntity(self):
        return MisawaInvestmentKodate()
    
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        
        # 動的判定ロジック: 「物件種目」ラベルを確認
        specs = self._get_specs(response)
        syumoku = specs.get("物件種目", "")
        
        # If not in table, check title/propertyName
        if not syumoku:
            # item.propertyName is already parsed by super()
            syumoku = item.propertyName
            
        if not any(x in syumoku for x in ["戸建", "一戸建て", "借地権付建物"]):
             logging.info(f"[MisawaKodate] Skipping non-kodate property: {syumoku} at {item.pageUrl}")
             from package.parser.baseParser import SkipPropertyException
             raise SkipPropertyException()

        item.propertyType = "Kodate"
        
        item.setsudou = self._parseSetsudou(response)
        item.chimoku = self._parseChimoku(response)
        
        return item

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('setsudou_key', '接道状況'), '')

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('chimoku_key', '地目'), '')


# ========== Investment Apartment Parser ==========
class MisawaInvestmentApartmentParser(MisawaInvestmentParser):
    def createEntity(self):
        return MisawaInvestmentApartment()
    
    def _parsePropertyDetailPage(self, item, response):
        item = super()._parsePropertyDetailPage(item, response)
        
        # 動的判定ロジック: 「物件種目」ラベルを確認
        specs = self._get_specs(response)
        syumoku = specs.get("物件種目", "")
        
        # If not in table, check title/propertyName
        if not syumoku:
            syumoku = item.propertyName
            
        if not any(x in syumoku for x in ["アパート", "一棟アパート", "一棟マンション", "ビル", "店舗"]):
             logging.info(f"[MisawaApartment] Skipping non-apartment property: {syumoku} at {item.pageUrl}")
             from package.parser.baseParser import SkipPropertyException
             raise SkipPropertyException()

        item.propertyType = "Apartment"
        
        item.soukosuStr = self._parseSoukosuStr(response)
        item.soukosu = self._parseSoukosu(response)
        item.setsudou = self._parseSetsudou(response)
        item.chimoku = self._parseChimoku(response)
        
        return item

    def _parseSoukosuStr(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('soukosu_key', '総戸数'), '')

    def _parseSoukosu(self, response):
        return converter.parse_numeric(self._parseSoukosuStr(response))

    def _parseSetsudou(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('setsudou_key', '接道状況'), '')

    def _parseChimoku(self, response):
        specs = self._get_specs(response)
        return specs.get(self.selectors.get('chimoku_key', '地目'), '')
