# -*- coding: utf-8 -*-
"""
Issue #794 回帰テスト: 残留50課題解消およびデータバリデーション・パーサー適正化の検証
"""
from bs4 import BeautifulSoup
from types import SimpleNamespace
from datetime import datetime, timezone

from package.utils.data_validator import PropertyDataValidator
from package.parser.baseParser import ParserBase
from package.parser.tokyuParser import TokyuMansionParser


class DummyParser(ParserBase):
    def getPropertyListXpath(self): return ""
    def getPropertyListNextPageUrl(self, response): return ""
    def getPropertyListDestUrl(self, link_url): return ""
    def parsePropertyListPage(self, response): pass
    def _parseAddress(self, response, specs=None): return ""
    def _parsePrice(self, response, specs=None): return 0
    def _parsePriceStr(self, response, specs=None): return ""
    def _parsePropertyName(self, response, specs=None): return ""
    def _parseTransport1(self, response, specs=None): return ""
    def createEntity(self): return None
    def getCharset(self): return "utf-8"


def test_base_parser_get_value_by_label_with_td():
    """td.table-header を使用したテーブル構造から _getValueByLabel が正常に値を取得できること"""
    html = """
    <table>
      <tr>
        <td class="table-header label">交通</td>
        <td class="table-data content"><p>東京メトロ千代田線 新御茶ノ水駅 徒歩3分</p></td>
      </tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = DummyParser()
    val_elem = parser._getValueByLabel(soup, "交通")
    assert val_elem is not None
    assert "新御茶ノ水駅" in val_elem.get_text()


def test_tokyu_scrape_specs_fallback_dl():
    """最新 SCSS モジュールの dl 構造から TokyuMansionParser が階数・スペックを抽出できること"""
    html = """
    <div class="index-module-scss-module__cv1pAa__detail">
      <dl class="index-module-scss-module__cv1pAa__propertyInfo">
        <dt>建物構造</dt><dd>ＲＣ</dd>
        <dt>階数</dt><dd>地上7階</dd>
        <dt>総戸数</dt><dd>46戸</dd>
      </dl>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = TokyuMansionParser()
    specs = parser._scrape_specs(soup)
    assert "階数" in specs
    assert specs["階数"]["value"] == "地上7階"
    assert specs["建物構造"]["value"] == "ＲＣ"


def test_data_validator_investment_yield_zero_allowed():
    """利回り 0.0% (未記載) や 100%超 (ボロ戸建て投資) がエラー判定されないこと"""
    item = SimpleNamespace(
        propertyName="テスト一棟アパート",
        address="東京都新宿区1-1-1",
        traffic="新宿駅徒歩5分",
        station1="新宿",
        price=50000000,
        tatemonoMenseki=120.0,
        yieldRate=0.0,
        pageUrl="https://toushi.homes.co.jp/bukkendetail/index/123/",
    )
    valid, reasons = PropertyDataValidator.validate_property(item, "investmentapartment")
    assert valid, f"Expected valid but got reasons: {reasons}"

    # 150% の超高利回り物件（格安物件）
    item.price = 1000000
    item.yieldRate = 150.0
    valid, reasons = PropertyDataValidator.validate_property(item, "investmentapartment")
    assert valid, f"Expected valid but got reasons: {reasons}"


def test_data_validator_old_age_allowed():
    """1882年 (明治15年) の京町家・古民家が築年数異常と判定されないこと"""
    item = SimpleNamespace(
        propertyName="京都市下京区高辻西洞院町戸建",
        address="京都府京都市下京区",
        traffic="四条駅徒歩7分",
        station1="四条",
        price=150000000,
        madori="5LDK",
        chikunengetsuStr="1882年1月",
        chikunengetsu=datetime(1882, 1, 1, tzinfo=timezone.utc),
        tatemonoMenseki=150.0,
        tochiMenseki=100.0,
        pageUrl="https://www.stepon.co.jp/kodate/detail_36362005/",
    )
    valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
    assert valid, f"Expected valid but got reasons: {reasons}"


def test_data_validator_mansion_kaisu_str_fallback():
    """floorType_kai が空でも kaisuStr に所在階情報がある場合は所在階欠損としないこと"""
    item = SimpleNamespace(
        propertyName="ライオンズマンション北綾瀬第７",
        address="東京都足立区大谷田５丁目",
        traffic="北綾瀬駅徒歩17分",
        station1="北綾瀬",
        price=42900000,
        madori="3LDK",
        senyuMenseki=68.36,
        floorType_kai=None,
        shozaikai=None,
        kaisu=None,
        kaisuStr="3階 / 地上7階",
        chikunengetsuStr="1995年8月",
        pageUrl="https://www.livable.co.jp/mansion/C13267Q02/",
    )
    valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert valid, f"Expected valid but got reasons: {reasons}"
