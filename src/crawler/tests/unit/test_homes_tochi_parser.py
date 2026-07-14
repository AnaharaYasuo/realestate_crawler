# -*- coding: utf-8 -*-
from django.test import TestCase
from bs4 import BeautifulSoup
from package.parser.homesParser import HomesTochiParser
from package.models.homes import HomesTochi
from decimal import Decimal

class HomesTochiParserTest(TestCase):
    def test_parse_tochi_details(self):
        html = """
        <html>
            <body>
                <table>
                    <tr><td class="prg-nameTableItem">品川区大井３丁目 売地</td></tr>
                    <tr><td class="prg-addressTableItem">東京都品川区大井３丁目</td></tr>
                    <tr><td class="prg-priceTableItem">5,800万円</td></tr>
                    <tr><td class="prg-landAreaTableItem">100.50m²</td></tr>
                    <tr><td class="prg-useDistrictTableItem">第一種中高層住居専用地域</td></tr>
                    <tr><td class="prg-buildingCoverageTableItem">60%</td></tr>
                    <tr><td class="prg-floorAreaRatioTableItem">150%</td></tr>
                    <tr><td class="prg-landCategoryTableItem">宅地</td></tr>
                    <tr><td class="prg-roadTableItem">西側 幅員約4.5m 私道（位置指定道路）間口8.2mに接する</td></tr>
                    <tr><td class="prg-rightTableItem">所有権</td></tr>
                </table>
            </body>
        </html>
        """
        parser = HomesTochiParser()
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        
        # パース
        parsed_item = parser._parsePropertyDetailPage(item, soup)
        
        self.assertEqual(parsed_item.tochiMenseki, Decimal("100.50"))
        self.assertEqual(parsed_item.youtoChiiki, "第一種中高層住居専用地域")
        self.assertEqual(parsed_item.kenpei, Decimal("60"))
        self.assertEqual(parsed_item.youseki, Decimal("150"))
        self.assertEqual(parsed_item.chimoku, "宅地")
        self.assertEqual(parsed_item.tochikenri, "所有権")
        
        # 正規表現抽出の検証
        self.assertEqual(parsed_item.maguchi, Decimal("8.2"))
        self.assertEqual(parsed_item.roadWidth, Decimal("4.5"))
        self.assertEqual(parsed_item.roadDirection, "西")
        self.assertEqual(parsed_item.roadType, "私道")
        self.assertEqual(parsed_item.roadStructure, "中間地")
