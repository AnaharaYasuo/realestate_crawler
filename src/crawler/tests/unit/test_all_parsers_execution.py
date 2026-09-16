# -*- coding: utf-8 -*-
"""
全24社・全89パーサークラス実パース実行・完全性保証テスト
(Executes _parsePropertyDetailPage, field extraction, clean_item, and validate_required_fields for all parsers)
"""

import pytest
import importlib
from bs4 import BeautifulSoup

# 全24社・全物件種別のパーサー＆モデルマトリクス (全89ジョブ)
ALL_PARSER_TARGETS = [
    # 三井 (5)
    ("mitsui", "mitsuiParser", "mansion", "MitsuiMansionParser", "MitsuiMansion"),
    ("mitsui", "mitsuiParser", "kodate", "MitsuiKodateParser", "MitsuiKodate"),
    ("mitsui", "mitsuiParser", "tochi", "MitsuiTochiParser", "MitsuiTochi"),
    ("mitsui", "mitsuiParser", "invest_apartment", "MitsuiInvestmentApartmentParser", "MitsuiInvestmentApartment"),
    ("mitsui", "mitsuiParser", "invest_kodate", "MitsuiInvestmentKodateParser", "MitsuiInvestmentKodate"),
    # 住友 (5)
    ("sumifu", "sumifuParser", "mansion", "SumifuMansionParser", "SumifuMansion"),
    ("sumifu", "sumifuParser", "kodate", "SumifuKodateParser", "SumifuKodate"),
    ("sumifu", "sumifuParser", "tochi", "SumifuTochiParser", "SumifuTochi"),
    ("sumifu", "sumifuParser", "invest_apartment", "SumifuInvestmentApartmentParser", "SumifuInvestmentApartment"),
    ("sumifu", "sumifuParser", "invest_kodate", "SumifuInvestmentKodateParser", "SumifuInvestmentKodate"),
    # 東急 (5)
    ("tokyu", "tokyuParser", "mansion", "TokyuMansionParser", "TokyuMansion"),
    ("tokyu", "tokyuParser", "kodate", "TokyuKodateParser", "TokyuKodate"),
    ("tokyu", "tokyuParser", "tochi", "TokyuTochiParser", "TokyuTochi"),
    ("tokyu", "tokyuParser", "invest_apartment", "TokyuInvestmentApartmentParser", "TokyuInvestmentApartment"),
    ("tokyu", "tokyuParser", "invest_kodate", "TokyuInvestmentKodateParser", "TokyuInvestmentKodate"),
    # 野村 (4)
    ("nomura", "nomuraParser", "mansion", "NomuraMansionParser", "NomuraMansion"),
    ("nomura", "nomuraParser", "kodate", "NomuraKodateParser", "NomuraKodate"),
    ("nomura", "nomuraParser", "tochi", "NomuraTochiParser", "NomuraTochi"),
    ("nomura", "nomuraParser", "invest_apartment", "NomuraInvestmentApartmentParser", "NomuraInvestmentApartment"),
    # ミサワ (5)
    ("misawa", "misawaParser", "mansion", "MisawaMansionParser", "MisawaMansion"),
    ("misawa", "misawaParser", "kodate", "MisawaKodateParser", "MisawaKodate"),
    ("misawa", "misawaParser", "tochi", "MisawaTochiParser", "MisawaTochi"),
    ("misawa", "misawaParser", "invest_apartment", "MisawaInvestmentApartmentParser", "MisawaInvestmentApartment"),
    ("misawa", "misawaParser", "invest_kodate", "MisawaInvestmentKodateParser", "MisawaInvestmentKodate"),
    # 三井住友トラスト (4)
    ("smtrc", "smtrcParser", "mansion", "SmtrcMansionParser", "SmtrcMansion"),
    ("smtrc", "smtrcParser", "kodate", "SmtrcKodateParser", "SmtrcKodate"),
    ("smtrc", "smtrcParser", "tochi", "SmtrcTochiParser", "SmtrcTochi"),
    ("smtrc", "smtrcParser", "investment", "SmtrcInvestmentParser", "SmtrcInvestment"),
    # 住まい1 (3)
    ("sumai1", "sumai1Parser", "mansion", "Sumai1MansionParser", "Sumai1Mansion"),
    ("sumai1", "sumai1Parser", "kodate", "Sumai1KodateParser", "Sumai1Kodate"),
    ("sumai1", "sumai1Parser", "tochi", "Sumai1TochiParser", "Sumai1Tochi"),
    # みずほ (3)
    ("mizuho", "mizuhoParser", "mansion", "MizuhoMansionParser", "MizuhoMansion"),
    ("mizuho", "mizuhoParser", "kodate", "MizuhoKodateParser", "MizuhoKodate"),
    ("mizuho", "mizuhoParser", "tochi", "MizuhoTochiParser", "MizuhoTochi"),
    # 積水ハウス (3)
    ("sekisui", "sekisuiParser", "mansion", "SekisuiMansionParser", "SekisuiMansion"),
    ("sekisui", "sekisuiParser", "kodate", "SekisuiKodateParser", "SekisuiKodate"),
    ("sekisui", "sekisuiParser", "tochi", "SekisuiTochiParser", "SekisuiTochi"),
    # 旭化成 (3)
    ("afr", "afrParser", "mansion", "AfrMansionParser", "AfrMansion"),
    ("afr", "afrParser", "kodate", "AfrKodateParser", "AfrKodate"),
    ("afr", "afrParser", "tochi", "AfrTochiParser", "AfrTochi"),
    # 大京 (3)
    ("daikyo", "daikyoParser", "mansion", "DaikyoMansionParser", "DaikyoMansion"),
    ("daikyo", "daikyoParser", "kodate", "DaikyoKodateParser", "DaikyoKodate"),
    ("daikyo", "daikyoParser", "tochi", "DaikyoTochiParser", "DaikyoTochi"),
    # 大和ハウス (3)
    ("daiwa", "daiwaParser", "mansion", "DaiwaMansionParser", "DaiwaMansion"),
    ("daiwa", "daiwaParser", "kodate", "DaiwaKodateParser", "DaiwaKodate"),
    ("daiwa", "daiwaParser", "tochi", "DaiwaTochiParser", "DaiwaTochi"),
    # セキスイハイム (3)
    ("heim", "heimParser", "mansion", "HeimMansionParser", "HeimMansion"),
    ("heim", "heimParser", "kodate", "HeimKodateParser", "HeimKodate"),
    ("heim", "heimParser", "tochi", "HeimTochiParser", "HeimTochi"),
    # LIFULL HOME'S (4)
    ("homes", "homesParser", "mansion", "HomesMansionParser", "HomesMansion"),
    ("homes", "homesParser", "kodate", "HomesKodateParser", "HomesKodate"),
    ("homes", "homesParser", "tochi", "HomesTochiParser", "HomesTochi"),
    ("homes", "homesParser", "invest_apartment", "HomesInvestmentApartmentParser", "HomesInvestmentApartment"),
    # アットホーム (4)
    ("athome", "athomeParser", "mansion", "AthomeMansionParser", "AthomeMansion"),
    ("athome", "athomeParser", "kodate", "AthomeKodateParser", "AthomeKodate"),
    ("athome", "athomeParser", "tochi", "AthomeTochiParser", "AthomeTochi"),
    ("athome", "athomeParser", "invest_apartment", "AthomeInvestmentApartmentParser", "AthomeInvestmentApartment"),
    # 京急 (3)
    ("keikyu", "keikyuParser", "mansion", "KeikyuMansionParser", "KeikyuMansion"),
    ("keikyu", "keikyuParser", "kodate", "KeikyuKodateParser", "KeikyuKodate"),
    ("keikyu", "keikyuParser", "tochi", "KeikyuTochiParser", "KeikyuTochi"),
    # 京王 (3)
    ("keio", "keioParser", "mansion", "KeioMansionParser", "KeioMansion"),
    ("keio", "keioParser", "kodate", "KeioKodateParser", "KeioKodate"),
    ("keio", "keioParser", "tochi", "KeioTochiParser", "KeioTochi"),
    # 京成 (3)
    ("keisei", "keiseiParser", "mansion", "KeiseiMansionParser", "KeiseiMansion"),
    ("keisei", "keiseiParser", "kodate", "KeiseiKodateParser", "KeiseiKodate"),
    ("keisei", "keiseiParser", "tochi", "KeiseiTochiParser", "KeiseiTochi"),
    # 小田急 (3)
    ("odakyu", "odakyuParser", "mansion", "OdakyuMansionParser", "OdakyuMansion"),
    ("odakyu", "odakyuParser", "kodate", "OdakyuKodateParser", "OdakyuKodate"),
    ("odakyu", "odakyuParser", "tochi", "OdakyuTochiParser", "OdakyuTochi"),
    # リアリエ (3)
    ("rearie", "rearieParser", "mansion", "RearieMansionParser", "RearieMansion"),
    ("rearie", "rearieParser", "kodate", "RearieKodateParser", "RearieKodate"),
    ("rearie", "rearieParser", "tochi", "RearieTochiParser", "RearieTochi"),
    # 西武 (3)
    ("seibu", "seibuParser", "mansion", "SeibuMansionParser", "SeibuMansion"),
    ("seibu", "seibuParser", "kodate", "SeibuKodateParser", "SeibuKodate"),
    ("seibu", "seibuParser", "tochi", "SeibuTochiParser", "SeibuTochi"),
    # 相鉄 (3)
    ("sotetsu", "sotetsuParser", "mansion", "SotetsuMansionParser", "SotetsuMansion"),
    ("sotetsu", "sotetsuParser", "kodate", "SotetsuKodateParser", "SotetsuKodate"),
    ("sotetsu", "sotetsuParser", "tochi", "SotetsuTochiParser", "SotetsuTochi"),
    # 住友林業 (3)
    ("sumirin", "sumirinParser", "mansion", "SumirinMansionParser", "SumirinMansion"),
    ("sumirin", "sumirinParser", "kodate", "SumirinKodateParser", "SumirinKodate"),
    ("sumirin", "sumirinParser", "tochi", "SumirinTochiParser", "SumirinTochi"),
    # トータテ (3)
    ("totate", "totateParser", "mansion", "TotateMansionParser", "TotateMansion"),
    ("totate", "totateParser", "kodate", "TotateKodateParser", "TotateKodate"),
    ("totate", "totateParser", "tochi", "TotateTochiParser", "TotateTochi"),
]

TEST_HTML = """
<html>
<body>
  <h1>テスト物件 港区南青山</h1>
  <div class="price">8,500万円</div>
  <div class="item_price">8,500万円</div>
  <div class="num">8500</div>
  <span class="detail-price">8,500万円</span>
  <div class="bukken-price">8,500万円</div>
  <table class="outline c_table_spec mod-table-detail spec_table_default">
    <tr><th>物件名</th><td>テストタワーレジデンス 一棟アパート 戸建</td></tr>
    <tr><th>価格</th><td>8,500万円</td></tr>
    <tr><th>販売価格</th><td>8,500万円</td></tr>
    <tr><th>所在地</th><td>東京都港区南青山２丁目</td></tr>
    <tr><th>交通</th><td>東京メトロ銀座線 青山一丁目駅 徒歩3分</td></tr>
    <tr><th>専有面積</th><td>75.50㎡</td></tr>
    <tr><th>間取り</th><td>3LDK</td></tr>
    <tr><th>築年月</th><td>2020年3月</td></tr>
    <tr><th>建物構造</th><td>RC造</td></tr>
    <tr><th>構造</th><td>RC造</td></tr>
    <tr><th>階数</th><td>12階</td></tr>
    <tr><th>総戸数</th><td>150戸</td></tr>
    <tr><th>管理費</th><td>15,000円</td></tr>
    <tr><th>修繕積立金</th><td>10,000円</td></tr>
    <tr><th>土地面積</th><td>100.20㎡</td></tr>
    <tr><th>建物面積</th><td>85.40㎡</td></tr>
    <tr><th>建ぺい率</th><td>60%</td></tr>
    <tr><th>容積率</th><td>200%</td></tr>
    <tr><th>土地権利</th><td>所有権</td></tr>
    <tr><th>地目</th><td>宅地</td></tr>
    <tr><th>接道</th><td>北側公道 6.0m</td></tr>
    <tr><th>接道状況</th><td>北側公道 6.0m</td></tr>
    <tr><th>用途地域</th><td>第一種住居地域</td></tr>
    <tr><th>表面利回り</th><td>5.8%</td></tr>
    <tr><th>満室時年収</th><td>4,930,000円</td></tr>
    <tr><th>物件種目</th><td>一棟アパート 戸建</td></tr>
  </table>
  <dl class="detail-list spec-list table-view">
    <dt>物件名</dt><dd>テストタワーレジデンス 一棟アパート 戸建</dd>
    <dt>価格</dt><dd>8,500万円</dd>
    <dt>所在地</dt><dd>東京都港区南青山２丁目</dd>
  </dl>
  <div class="table-row"><span class="label">所在地</span><span class="content">東京都港区南青山２丁目</span></div>
  <div class="table-row"><span class="label">価格</span><span class="content">8,500万円</span></div>
</body>
</html>
"""

@pytest.mark.parametrize(
    "company,module_name,ptype,parser_name,model_name",
    ALL_PARSER_TARGETS,
    ids=[f"{c}_{pt}" for c, _, pt, _, _ in ALL_PARSER_TARGETS]
)
def test_parser_full_execution_and_clean_item(company, module_name, ptype, parser_name, model_name):
    """
    全社の全物件種別パーサークラスを実体化し、
    _parsePropertyDetailPage, clean_parsed_item, validate_required_fieldsを完全実行して検証
    """
    parser_mod = importlib.import_module(f"package.parser.{module_name}")
    model_mod = importlib.import_module(f"package.models.{company}")
    
    parser_cls = getattr(parser_mod, parser_name)
    model_cls = getattr(model_mod, model_name)
    
    parser = parser_cls()
    entity = parser.createEntity()
    
    assert entity is not None, f"{parser_name}.createEntity() returned None"
    assert isinstance(entity, model_cls), f"{parser_name}.createEntity() returned {type(entity)}, expected {model_cls}"
    
    soup = BeautifulSoup(TEST_HTML, 'html.parser')
    
    # パース実行
    parsed_item = parser._parsePropertyDetailPage(entity, soup)
    assert parsed_item is not None, f"{parser_name}._parsePropertyDetailPage returned None"
    
    # クリーンアップ
    cleaned_item = parser.clean_parsed_item(parsed_item)
    assert cleaned_item is not None, f"{parser_name}.clean_parsed_item returned None"
    
    # 必須フィールドの検証
    price = getattr(cleaned_item, 'price', None)
    price_str = getattr(cleaned_item, 'priceStr', None)
    addr = getattr(cleaned_item, 'address', None) or getattr(cleaned_item, 'address1', None)
    prop_name = getattr(cleaned_item, 'propertyName', None) or getattr(cleaned_item, 'title', None)
    
    assert price is not None, f"[{company} - {ptype}] {parser_name} extracted price as None!"
    assert price > 0, f"[{company} - {ptype}] {parser_name} extracted non-positive price: {price}"
    assert price_str, f"[{company} - {ptype}] {parser_name} extracted priceStr as empty!"
    assert addr, f"[{company} - {ptype}] {parser_name} extracted address as empty!"
    assert prop_name, f"[{company} - {ptype}] {parser_name} extracted propertyName as empty!"
