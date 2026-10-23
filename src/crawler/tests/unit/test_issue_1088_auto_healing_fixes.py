# -*- coding: utf-8 -*-
"""
Issue 1088: Auto-Healing Pipeline & Data Quality Fixes Unit Tests
"""
from bs4 import BeautifulSoup
from django.test import TestCase

from package.models.daikyo import DaikyoMansion
from package.models.daiwa import DaiwaMansion
from package.models.totate import TotateMansion
from package.parser.daikyoParser import DaikyoMansionParser
from package.parser.daiwaParser import DaiwaMansionParser
from package.parser.mitsuiParser import MitsuiMansionParser
from package.parser.totateParser import TotateMansionParser
from package.utils.data_validator import PropertyDataValidator
from package.utils.url_router import UrlRouter


class TestAutoHealingFixes(TestCase):

    def test_mitsui_sectional_unit_guard(self):
        """MitsuiMansionParser has sectional unit guard enabled."""
        parser = MitsuiMansionParser(None)
        self.assertTrue(getattr(parser, "sectional_unit_guard_enabled", False))

    def test_daikyo_floor_parsing(self):
        """Daikyo parser extracts floorType_kai and kaisuStr from 所在階/建物階数."""
        parser = DaikyoMansionParser(None)
        item = DaikyoMansion()
        specs = {"所在階/建物階数": "4階/地上4階"}
        parser._parse_floors(item, specs)
        self.assertEqual(item.floorType_kai, 4)
        self.assertEqual(item.floorType_chijo, 4)
        self.assertIn("4階", item.kaisuStr)

    def test_daiwa_floor_parsing(self):
        """Daiwa parser extracts floorType_kai and kaisuStr from 階数/階."""
        parser = DaiwaMansionParser(None)
        item = DaiwaMansion()
        html = "<table><tr><th>階数/階</th><td>（地下2階）地上40階建 /8階</td></tr></table>"
        soup = BeautifulSoup(html, "html.parser")
        item = parser._parsePropertyDetailPage(item, soup)
        item = parser.clean_parsed_item(item)
        self.assertEqual(item.floorType_kai, 8)
        self.assertIn("8階", item.kaisuStr)

    def test_totate_floor_parsing(self):
        """Totate parser extracts floorType_kai when kaisuStr is '7階'."""
        parser = TotateMansionParser(None)
        item = TotateMansion()
        html = "<table><tr><th>所在階</th><td>7階</td></tr></table>"
        soup = BeautifulSoup(html, "html.parser")
        item = parser._parsePropertyDetailPage(item, soup)
        item = parser.clean_parsed_item(item)
        self.assertEqual(item.floorType_kai, 7)

    def test_url_router_athome_buy_other(self):
        """UrlRouter routes athome /buy_other/ to AthomeInvestmentApartmentParser when property_type is apartment or detected."""
        url = "https://www.athome.co.jp/buy_other/1198396219/?BKLISTID=001LPC"
        parser = UrlRouter.create_parser(url, property_type="apartment")
        self.assertEqual(parser.__class__.__name__, "AthomeInvestmentApartmentParser")

    def test_data_validator_floor_recognition(self):
        """PropertyDataValidator recognizes various floor string representations."""
        self.assertTrue(PropertyDataValidator._has_located_floor("4階/地上4階"))
        self.assertTrue(PropertyDataValidator._has_located_floor("7階"))
        self.assertTrue(PropertyDataValidator._has_located_floor("地上40階建 / 8階"))
        self.assertFalse(PropertyDataValidator._has_located_floor("地上7階建"))
        self.assertFalse(PropertyDataValidator._has_located_floor("7階建"))
