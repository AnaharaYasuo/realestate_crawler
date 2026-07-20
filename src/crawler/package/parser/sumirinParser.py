# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from package.parser.baseParser import ParserBase
from package.models.sumirin import SumirinMansion, SumirinKodate, SumirinTochi, SumirinInvestment
from package.utils import converter
import re
import urllib.parse

class SumirinParser(ParserBase):
    BASE_URL = 'https://www.suminavi.com'
    property_type = ''

    def __init__(self, params=None):
        super().__init__()
        # YAMLセレクタは使わないが、ダミーとして残す
        self.selectors = {}

    def getCharset(self):
        return "utf-8"

    def getRootDestUrl(self, linkUrl):
        if linkUrl.startswith('http'):
            return linkUrl
        if linkUrl.startswith('/'):
            return self.BASE_URL + linkUrl
        return self.BASE_URL + '/' + linkUrl

    async def parseNextPage(self, response: BeautifulSoup):
        # ページネーションの「次へ」リンクを探す
        next_a = response.select_one("li.next a, a.next, .pager .next a")
        if next_a:
            href = next_a.get("href")
            if href:
                return self.getRootDestUrl(href)
        return ""

    async def parseRootPage(self, response: BeautifulSoup):
        detail_links = set()
        
        # 物件種別から実際のURLパス名へのマッピング
        type_map = {
            'mansion': 'mansion',
            'tochi': 'land',
            'kodate': 'house',
            'investment': 'business'
        }
        target_path = type_map.get(self.property_type, 'mansion')
        
        # 詳細ページのパターン (物件種別に応じて動的に絞り込み、末尾スラッシュは任意)
        pattern = re.compile(rf'/buy/estate/estateInfo/{target_path}/[a-z]+/(\d+)/?')
        for a in response.find_all("a", href=pattern):
            href = a.get("href")
            if href:
                full_url = self.getRootDestUrl(href)
                # パスパラメータの正規化 (クエリパラメータの除去)
                parsed = urllib.parse.urlparse(full_url)
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if normalized not in detail_links:
                    detail_links.add(normalized)
                    yield normalized

    def _get_specs(self, response: BeautifulSoup):
        specs = {}
        # 「物件概要」セクションを探す
        outline_sec = None
        for sec in response.find_all("section"):
            h2 = sec.find("h2")
            if h2 and "物件概要" in h2.get_text():
                outline_sec = sec
                break
        if not outline_sec:
            outline_sec = response.find(class_=re.compile(r'outline|summary|spec', re.I)) or response

        # dl.inner が並ぶ構造
        for dl in outline_sec.find_all("dl", class_="inner"):
            dt = dl.find("dt", class_="hdg")
            dd = dl.find("dd", class_="dtl")
            if dt and dd:
                key = dt.get_text().strip().replace('\n', '').replace(' ', '').replace('\u3000', '')
                val = dd.get_text().strip().replace('\n', ' ')
                specs[key] = val

        # 一般的な dl/dt/dd および table/tr/th/td のパース（フォールバック）
        for dl in outline_sec.select("dl"):
            for dt, dd in zip(dl.select("dt"), dl.select("dd")):
                key = dt.get_text().strip().replace("\n", "").replace(" ", "").replace("\u3000", "").replace("：", "")
                if key and key not in specs:
                    specs[key] = dd.get_text().strip()
        for table in outline_sec.select("table"):
            for tr in table.select("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if th and td:
                    key = th.get_text().strip().replace("\n", "").replace(" ", "").replace("\u3000", "")
                    if key and key not in specs:
                        specs[key] = td.get_text().strip()

        # キーの表記揺れ標準化
        fallback_mappings = {
            "建ぺい率": ["建ペイ率"],
            "容積率": ["容積率"],
            "建ぺい率/容積率": ["建ぺい・容積率", "建ペイ・容積率", "建ペイ率/容積率", "建ぺい率／容積率"],
            "想定年間収入": ["満室想定年収", "想定年収", "想定賃料(年間)", "想定年間賃料", "年間想定賃料", "年間想定収入", "想定収入"],
            "想定利回り": ["表面利回り", "利回り", "グロス利回り", "想定グロス利回り"],
            "総戸数": ["戸数", "総区画", "総戸数/総区画"],
            "建物構造": ["構造", "構造・規模"],
            "築年月": ["完成時期", "築年"]
        }
        for std_key, alt_keys in fallback_mappings.items():
            for alt in alt_keys:
                if alt in specs and std_key not in specs:
                    specs[std_key] = specs[alt]
                if std_key in specs and alt not in specs:
                    specs[alt] = specs[std_key]
        return specs

    def _split_address(self, address):
        return super()._split_address(address)

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):

        # 共通部分のパース
        item = super()._parsePropertyDetailPage(item, response)
        
        # タイトル/物件名
        h1 = response.find("h1")
        if h1:
            item.propertyName = h1.get_text().strip()

        # 物件概要スペック表の取得
        specs = self._get_specs(response)
        
        # 価格
        price_str = specs.get("価格", "")
        # 不要な「ローンシミュレーション」などのテキストが入るためクリーンアップ
        if price_str:
            item.priceStr = price_str.split("ローン")[0].strip()
            item.price = converter.parse_price(item.priceStr)

        # 所在地
        item.address = specs.get("所在地", "")
        if item.address:
            item.address1, item.address2, item.address3 = self._split_address(item.address)

        # 交通
        traffic_str = specs.get("交通", "")
        if traffic_str:
            # スペース区切りなどで最大5つの路線情報を抽出
            traffic_lines = re.split(r'\s{2,}', traffic_str)
            if len(traffic_lines) <= 1:
                traffic_lines = traffic_str.split(" ")
            self._populateTraffic(item, [t.strip() for t in traffic_lines if t.strip()])

        item.biko = specs.get("備考", "")
        item.genkyo = specs.get("現況", "")
        item.tochikenri = specs.get("土地権利", "")
        item.torihiki = specs.get("取引態様", "")

        return item

    def _parse_kenpei_youseki(self, item, specs):
        kenpei_str = specs.get("建ぺい率", "") or specs.get("建ぺい率/容積率", "")
        youseki_str = specs.get("容積率", "") or specs.get("建ぺい率/容積率", "")
        
        if "／" in kenpei_str:
            parts = kenpei_str.split("／")
            if len(parts) >= 2:
                item.kenpeiStr = parts[0].strip()
                item.yousekiStr = parts[1].strip()
        elif "/" in kenpei_str:
            parts = kenpei_str.split("/")
            if len(parts) >= 2:
                item.kenpeiStr = parts[0].strip()
                item.yousekiStr = parts[1].strip()
        else:
            item.kenpeiStr = kenpei_str
            item.yousekiStr = youseki_str
            
        item.kenpei = converter.parse_ratio(item.kenpeiStr)
        item.youseki = converter.parse_ratio(item.yousekiStr)

class SumirinMansionParser(SumirinParser):
    property_type = 'mansion'

    def createEntity(self):
        return SumirinMansion()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")
        
        item.senyuMensekiStr = specs.get("専有面積", "") or specs.get("面積", "")
        if item.senyuMensekiStr:
            item.senyuMenseki = converter.parse_menseki(item.senyuMensekiStr)

        # 所在階/階数
        item.kaisuStr = specs.get("所在階/階数", "") or specs.get("所在階", "") or specs.get("階数", "") or specs.get("階建", "")
        if item.kaisuStr:
            m = re.search(r'(\d+)階', item.kaisuStr)
            if m:
                item.floorType_kai = int(m.group(1))
            m = re.search(r'／(\d+)階建', item.kaisuStr) or re.search(r'(\d+)階建', item.kaisuStr)
            if m:
                item.floorType_chijo = int(m.group(1))
            m = re.search(r'地下(\d+)階', item.kaisuStr)
            if m:
                item.floorType_chika = int(m.group(1))

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.balconyMensekiStr = specs.get("バルコニー面積", "") or specs.get("バルコニー", "")
        if item.balconyMensekiStr:
            item.balconyMenseki = converter.parse_menseki(item.balconyMensekiStr)

        # 総戸数
        item.soukosuStr = specs.get("空き物件数/総戸数", "") or specs.get("総戸数", "") or specs.get("戸数", "")
        if item.soukosuStr:
            m = re.search(r'／(\d+)戸', item.soukosuStr)
            if m:
                item.soukosu = int(m.group(1))
            else:
                item.soukosu = converter.parse_numeric(item.soukosuStr)

        item.kanrihiStr = specs.get("管理費", "") or specs.get("管理費等", "")
        if item.kanrihiStr:
            item.kanrihi = converter.parse_rent(item.kanrihiStr)

        item.syuzenTsumitateStr = specs.get("修繕積立金", "") or specs.get("修繕積立金等", "")
        if item.syuzenTsumitateStr:
            item.syuzenTsumitate = converter.parse_rent(item.syuzenTsumitateStr)

        item.kouzou = specs.get("建物構造", "") or specs.get("構造", "")
        item.kanriKeitai = specs.get("管理", "") or specs.get("管理形態", "")

        return item

class SumirinTochiParser(SumirinParser):
    property_type = 'tochi'

    def createEntity(self):
        return SumirinTochi()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.tochiMensekiStr = specs.get("土地面積", "") or specs.get("敷地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.chimoku = specs.get("地目", "")
        
        self._parse_kenpei_youseki(item, specs)

        item.youtoChiiki = specs.get("用途地域", "")
        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item

class SumirinInvestmentParser(SumirinParser):
    property_type = 'investment'

    def createEntity(self):
        return SumirinInvestment()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        # 表面利回り
        gross_yield_str = specs.get("想定利回り", "") or specs.get("表面利回り", "") or specs.get("利回り", "")
        if gross_yield_str:
            item.grossYield = converter.parse_ratio(gross_yield_str)

        # 年間想定賃料
        annual_rent_str = specs.get("想定年間収入", "") or specs.get("年間想定収入", "") or specs.get("想定収入", "")
        if annual_rent_str:
            rent_val = converter.parse_rent(annual_rent_str)
            if rent_val:
                item.annualRent = rent_val
                item.monthlyRent = rent_val // 12

        item.currentStatus = specs.get("現況", "") or specs.get("現況状況", "")
        item.kouzou = specs.get("建物構造", "") or specs.get("構造", "")

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        # 総戸数
        soukosu_str = specs.get("空き物件数/総戸数", "") or specs.get("総戸数", "") or specs.get("戸数", "")
        if soukosu_str:
            m = re.search(r'／(\d+)戸', soukosu_str)
            if m:
                item.soukosu = int(m.group(1))
            else:
                item.soukosu = converter.parse_numeric(soukosu_str)

        item.kaisuStr = specs.get("所在階/階数", "") or specs.get("所在階", "") or specs.get("階数", "") or specs.get("階建", "")

        item.tochiMensekiStr = specs.get("土地面積", "") or specs.get("敷地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "") or specs.get("専有面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        self._parse_kenpei_youseki(item, specs)

        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")
        item.chimoku = specs.get("地目", "")
        item.youtoChiiki = specs.get("用途地域", "")

        # 物件種別の判定 (タイトル等から)
        h1_text = item.propertyName or ""
        if "アパート" in h1_text:
            item.propertyType = "Apartment"
        elif "マンション" in h1_text:
            item.propertyType = "Mansion"
        elif "ビル" in h1_text or "店舗" in h1_text or "事務所" in h1_text:
            item.propertyType = "Building"
        else:
            item.propertyType = "Apartment" # fallback

        return item

class SumirinKodateParser(SumirinParser):
    property_type = 'kodate'

    def createEntity(self):
        return SumirinKodate()

    def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
        item = super()._parsePropertyDetailPage(item, response)
        specs = self._get_specs(response)

        item.madori = specs.get("間取り", "")

        item.tochiMensekiStr = specs.get("土地面積", "") or specs.get("敷地面積", "")
        if item.tochiMensekiStr:
            item.tochiMenseki = converter.parse_menseki(item.tochiMensekiStr)

        item.tatemonoMensekiStr = specs.get("建物面積", "") or specs.get("延床面積", "") or specs.get("専有面積", "")
        if item.tatemonoMensekiStr:
            item.tatemonoMenseki = converter.parse_menseki(item.tatemonoMensekiStr)

        # 築年月
        item.chikunengetsuStr = specs.get("築年月", "") or specs.get("完成時期", "")
        if item.chikunengetsuStr:
            item.chikunengetsu = converter.parse_chikunengetsu(item.chikunengetsuStr)

        item.kouzou = specs.get("建物構造", "") or specs.get("構造", "")
        item.kaisuStr = specs.get("所在階/階数", "") or specs.get("所在階", "") or specs.get("階数", "") or specs.get("階建", "")

        self._parse_kenpei_youseki(item, specs)

        item.youtoChiiki = specs.get("用途地域", "")
        item.setsudou = specs.get("接道状況", "") or specs.get("接道", "")

        return item
