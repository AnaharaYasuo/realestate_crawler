# -*- coding: utf-8 -*-
from django.test import TestCase
from bs4 import BeautifulSoup
from package.parser.athomeParser import AthomeTochiParser
from package.models.athome import AthomeTochi
from decimal import Decimal

class AthomeTochiParserTest(TestCase):
    def test_parse_tochi_details(self):
        html = """
        <html>
            <body>
                <table>
                    <tr><th>所在地</th><td>東京都品川区大井３丁目</td></tr>
                    <tr><th>価格</th><td>5,800万円</td></tr>
                    <tr><th>土地面積</th><td>100.50㎡</td></tr>
                    <tr><th>用途地域</th><td>第一種中高層住居専用地域</td></tr>
                    <tr><th>建ぺい率</th><td>60%</td></tr>
                    <tr><th>容積率</th><td>150%</td></tr>
                    <tr><th>地目</th><td>宅地</td></tr>
                    <tr><th>前面道路</th><td>北側 幅員約6.0m 公道</td></tr>
                    <tr><th>接道状況</th><td>一方：北側幅員6mの公道に間口12.5m接する</td></tr>
                    <tr><th>間口</th><td>12.5m</td></tr>
                </table>
            </body>
        </html>
        """
        parser = AthomeTochiParser()
        soup = BeautifulSoup(html, "html.parser")
        item = parser.createEntity()
        
        # モックのために get_specs_table メソッドのテスト
        specs = parser._get_specs_table(soup)
        self.assertEqual(specs.get("土地面積"), "100.50㎡")
        self.assertEqual(specs.get("用途地域"), "第一種中高層住居専用地域")
        
        # 実際にパース
        parsed_item = parser._parsePropertyDetailPage(item, soup)
        
        self.assertEqual(parsed_item.tochiMenseki, Decimal("100.50"))
        self.assertEqual(parsed_item.youtoChiiki, "第一種中高層住居専用地域")
        self.assertEqual(parsed_item.kenpei, Decimal("60"))
        self.assertEqual(parsed_item.youseki, Decimal("150"))
        self.assertEqual(parsed_item.chimoku, "宅地")
        
        # 正規表現抽出の検証
        self.assertEqual(parsed_item.maguchi, Decimal("12.5"))
        self.assertEqual(parsed_item.roadWidth, Decimal("6.0"))
        self.assertEqual(parsed_item.roadDirection, "北")
        self.assertEqual(parsed_item.roadType, "公道")
        self.assertEqual(parsed_item.roadStructure, "中間地") # 正規表現にマッチし、かつ角地等ではないので中間地
