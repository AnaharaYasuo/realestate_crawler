from bs4 import BeautifulSoup

from package.api.smtrc import (
    ParseSmtrcMansionStartAsync,
    ParseSmtrcKodateStartAsync,
    ParseSmtrcTochiStartAsync,
    ParseSmtrcInvestmentStartAsync,
)
from package.parser.smtrcParser import SmtrcMansionParser
from package.models.smtrc import SmtrcMansion
from package.utils.data_validator import PropertyDataValidator, ERR_MISSING_FLOOR


def test_smtrc_api_timeouts():
    """smtrcクローラーの巡回タイムアウトが各2400秒であることを検証"""
    assert ParseSmtrcMansionStartAsync()._getTimeOutSecond() == 2400
    assert ParseSmtrcKodateStartAsync()._getTimeOutSecond() == 2400
    assert ParseSmtrcTochiStartAsync()._getTimeOutSecond() == 2400
    assert ParseSmtrcInvestmentStartAsync()._getTimeOutSecond() == 2400


def test_smtrc_mansion_parser_floor_formats():
    """所在階/階建などの複合ヘッダーから階数が正しくパースされることを検証"""
    parser = SmtrcMansionParser()

    html_composite = """
    <html>
      <body>
        <table class="detail-table">
          <tr><th>間取り</th><td>3LDK</td></tr>
          <tr><th>専有面積</th><td>70.5m²</td></tr>
          <tr><th>所在階/階建</th><td>3階 / 地上10階建</td></tr>
        </table>
      </body>
    </html>
    """
    item = parser.createEntity()
    soup = BeautifulSoup(html_composite, "html.parser")
    parsed_item = parser._parsePropertyDetailPage(item, soup)

    assert parsed_item.kaisuStr == "3階 / 地上10階建"
    assert parsed_item.floorType_kai == 3
    assert parsed_item.floorType_chijo == 10

    # 所在階／階建（全角スラッシュ）
    html_composite_zenkaku = """
    <html>
      <body>
        <table class="detail-table">
          <tr><th>間取り</th><td>2LDK</td></tr>
          <tr><th>専有面積</th><td>55.0m²</td></tr>
          <tr><th>所在階／階建</th><td>5階／地上14階建</td></tr>
        </table>
      </body>
    </html>
    """
    item2 = parser.createEntity()
    soup2 = BeautifulSoup(html_composite_zenkaku, "html.parser")
    parsed_item2 = parser._parsePropertyDetailPage(item2, soup2)

    assert parsed_item2.kaisuStr == "5階／地上14階建"
    assert parsed_item2.floorType_kai == 5
    assert parsed_item2.floorType_chijo == 14


def test_validator_floor_fallbacks():
    """PropertyDataValidatorがfloorType_kaiやkaisuStrをフォールバックとして認識することを検証"""
    item = SmtrcMansion()
    item.senyuMenseki = 70.0
    item.floorType_kai = 3
    item.kaisuStr = "3階"

    # shozaikai, kaisu 属性を持たないモデルでも floorType_kai/kaisuStr があれば正常
    _is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert ERR_MISSING_FLOOR not in reasons

    # 階数情報が全くない場合は ERR_MISSING_FLOOR が検知される
    item_empty = SmtrcMansion()
    item_empty.senyuMenseki = 70.0
    item_empty.floorType_kai = None
    item_empty.kaisuStr = ""

    is_valid_empty, reasons_empty = PropertyDataValidator.validate_property(item_empty, "mansion")
    assert ERR_MISSING_FLOOR in reasons_empty
    assert is_valid_empty is False
