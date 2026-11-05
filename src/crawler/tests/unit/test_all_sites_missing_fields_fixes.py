# -*- coding: utf-8 -*-
"""
Tests for comprehensive fixes across all site parsers:
- AtHome & Homes: hikiwatashi, genkyo, kanrihi, syuzenTsumitate
- Keikyu: kanrihi/syuzenTsumitate from combined, kaisu, kenpei/youseki
- Keio: tochikenri, genkyo, kanrihi/syuzenTsumitate from combined, kenpei/youseki
- Keisei: kanrihi/syuzenTsumitate from combined, kaisu, kenpei/youseki
- Sotetsu & Sumai1: tochikenri, kaisu
- AdCast: kenpei/youseki from slash string
- Totate: kanrihi/syuzenTsumitate, kaisu, douro
- Daiwa, SMTRC, Sekisui, Mizuho, Odakyu, Afr, Sumirin: road details (douroHaba, douroMuki, douroKubun, setsumen)
"""
import pytest
from decimal import Decimal
from bs4 import BeautifulSoup

from package.parser.athomeParser import AthomeMansionParser, AthomeKodateParser
from package.parser.homesParser import HomesMansionParser, HomesKodateParser
from package.parser.keikyuParser import KeikyuMansionParser, KeikyuKodateParser
from package.parser.keioParser import KeioMansionParser, KeioKodateParser
from package.parser.keiseiParser import KeiseiMansionParser, KeiseiKodateParser
from package.parser.sotetsuParser import SotetsuKodateParser, SotetsuMansionParser
from package.parser.sumai1Parser import Sumai1KodateParser, Sumai1MansionParser
from package.parser.adcastParser import AdCastKodateParser, AdCastTochiParser
from package.parser.totateParser import TotateMansionParser, TotateKodateParser
from package.parser.daiwaParser import DaiwaKodateParser, DaiwaTochiParser
from package.parser.smtrcParser import SmtrcKodateParser, SmtrcTochiParser
from package.parser.sekisuiParser import SekisuiKodateParser
from package.parser.mizuhoParser import MizuhoKodateParser
from package.parser.odakyuParser import OdakyuKodateParser
from package.parser.afrParser import AfrKodateParser
from package.parser.sumirinParser import SumirinKodateParser


def test_sotetsu_and_sumai1_tochikenri_and_kaisu():
    # Sotetsu
    sotetsu_p = SotetsuKodateParser()
    item = sotetsu_p.createEntity()
    html_sotetsu = """<div class="outlineTable">
    <div class="tr"><div class="th">物件名</div><div class="td">相鉄戸建</div></div>
    <div class="tr"><div class="th">価格</div><div class="td">4,500万円</div></div>
    <div class="tr"><div class="th">所在地</div><div class="td">神奈川県横浜市</div></div>
    <div class="tr"><div class="th">交通</div><div class="td">相鉄本線 横浜駅 徒歩10分</div></div>
    <div class="tr"><div class="th">土地権利</div><div class="td">所有権</div></div>
    <div class="tr"><div class="th">構造・工法</div><div class="td">木造2階建</div></div>
    </div>"""
    soup_sotetsu = BeautifulSoup(html_sotetsu, "html.parser")
    sotetsu_p._parsePropertyDetailPage(item, soup_sotetsu)
    assert item.tochikenri == "所有権"
    assert item.kaisu == 2

    # Sumai1
    sumai1_p = Sumai1KodateParser()
    item_s = sumai1_p.createEntity()
    specs_s = {
        "土地権利": "所有権",
        "構造": "木造2階建",
        "所在地": "東京都世田谷区",
        "価格": "5,000万円",
        "交通": "東急東横線 自由が丘駅 徒歩8分"
    }
    html_s = """<table>
    <tr><th>物件名</th><td>テスト戸建</td></tr>
    <tr><th>価格</th><td>5,000万円</td></tr>
    <tr><th>所在地</th><td>東京都世田谷区</td></tr>
    <tr><th>交通</th><td>東急東横線 自由が丘駅 徒歩8分</td></tr>
    <tr><th>土地権利</th><td>所有権</td></tr>
    <tr><th>構造</th><td>木造2階建</td></tr>
    </table>"""
    soup_s = BeautifulSoup(html_s, "html.parser")
    sumai1_p._parsePropertyDetailPage(item_s, soup_s)
    assert item_s.tochikenri == "所有権"
    assert item_s.kaisu == 2


def test_keio_and_keisei_combined_slash_specs():
    # Keio Mansion
    keio_p = KeioMansionParser()
    item_k = keio_p.createEntity()
    html_k = """<table>
    <tr><th>物件名</th><td>京王マンション</td></tr>
    <tr><th>価格</th><td>3,000万円</td></tr>
    <tr><th>交通</th><td>京王線 調布駅 徒歩5分</td></tr>
    <tr><th>管理費等（月額）</th><td>管理費: 12,000円 / 修繕積立金: 8,000円</td></tr>
    <tr><th>権利</th><td>所有権</td></tr>
    <tr><th>現況</th><td>空室</td></tr>
    </table>"""
    soup_k = BeautifulSoup(html_k, "html.parser")
    keio_p._parsePropertyDetailPage(item_k, soup_k)
    assert item_k.kanrihi == 12000
    assert item_k.syuzenTsumitate == 8000
    assert item_k.tochikenri == "所有権"
    assert item_k.genkyo == "空室"

    # Keisei Kodate
    keisei_p = KeiseiKodateParser()
    item_ks = keisei_p.createEntity()
    html_ks = """<table>
    <tr><th>物件種目</th><td>一戸建て</td></tr>
    <tr><th>価格</th><td>2,800万円</td></tr>
    <tr><th>交通</th><td>京成本線 八千代台駅 徒歩12分</td></tr>
    <tr><th>建ぺい率/容積率</th><td>60% / 200%</td></tr>
    <tr><th>構造</th><td>木造2階建</td></tr>
    <tr><th>引渡時期</th><td>相談</td></tr>
    </table>"""
    soup_ks = BeautifulSoup(html_ks, "html.parser")
    keisei_p._parsePropertyDetailPage(item_ks, soup_ks)
    assert item_ks.kenpei == Decimal("60.00")
    assert item_ks.youseki == Decimal("200.00")
    assert item_ks.kaisu == 2
    assert item_ks.hikiwatashi == "相談"


def test_adcast_slash_kenpei_youseki():
    p = AdCastKodateParser()
    item = p.createEntity()
    html = """<table>
    <tr><th>物件種目</th><td>新築一戸建て</td></tr>
    <tr><th>販売価格</th><td>6,580万円</td></tr>
    <tr><th>所在地</th><td>東京都杉並区</td></tr>
    <tr><th>交通</th><td>中央線 荻窪駅 徒歩10分</td></tr>
    <tr><th>建ぺい率／容積率</th><td>50%／100%</td></tr>
    </table>"""
    soup = BeautifulSoup(html, "html.parser")
    p._parsePropertyDetailPage(item, soup)
    assert item.kenpei == "50%"
    assert item.youseki == "100%"


def test_road_details_across_broker_parsers():
    # Daiwa Kodate
    daiwa_p = DaiwaKodateParser()
    item_d = daiwa_p.createEntity()
    html_d = """<table>
    <tr><th>物件名</th><td>ダイワ戸建</td></tr>
    <tr><th>価格</th><td>4,500万円</td></tr>
    <tr><th>所在地</th><td>東京都練馬区</td></tr>
    <tr><th>交通</th><td>西武池袋線 練馬駅 徒歩7分</td></tr>
    <tr><th>接道状況</th><td>北東側 6.0m 公道 接面8.5m</td></tr>
    </table>"""
    soup_d = BeautifulSoup(html_d, "html.parser")
    daiwa_p._parsePropertyDetailPage(item_d, soup_d)
    assert item_d.douroMuki == "北東"
    assert item_d.douroHaba == Decimal("6.0")
    assert item_d.douroKubun == "公道"
    assert item_d.setsumen == Decimal("8.5")

    # SMTRC Kodate
    smtrc_p = SmtrcKodateParser()
    item_s = smtrc_p.createEntity()
    html_s = """<table>
    <tr><th>物件名</th><td>三井住友トラスト戸建</td></tr>
    <tr><th>販売価格</th><td>5,200万円</td></tr>
    <tr><th>所在地</th><td>東京都目黒区</td></tr>
    <tr><th>交通</th><td>東急東横線 自由が丘駅 徒歩9分</td></tr>
    <tr><th>接道状況</th><td>南側 4.0m 私道 間口6.0m</td></tr>
    <tr><th>引渡し可能年月</th><td>即時</td></tr>
    </table>"""
    soup_s = BeautifulSoup(html_s, "html.parser")
    smtrc_p._parsePropertyDetailPage(item_s, soup_s)
    assert item_s.douroMuki == "南"
    assert item_s.douroHaba == Decimal("4.0")
    assert item_s.douroKubun == "私道"
    assert item_s.setsumen == Decimal("6.0")
    assert item_s.hikiwatashi == "即時"

    # Sekisui Kodate
    sekisui_p = SekisuiKodateParser()
    item_sk = sekisui_p.createEntity()
    html_sk = """<table>
    <tr><th>物件名</th><td>セキスイ戸建</td></tr>
    <tr><th>価格</th><td>3,800万円</td></tr>
    <tr><th>所在地</th><td>埼玉県さいたま市</td></tr>
    <tr><th>交通</th><td>JR京浜東北線 大宮駅 徒歩15分</td></tr>
    <tr><th>接道</th><td>東側 5.5m 公道 接面7.0m</td></tr>
    </table>"""
    soup_sk = BeautifulSoup(html_sk, "html.parser")
    sekisui_p._parsePropertyDetailPage(item_sk, soup_sk)
    assert item_sk.douroMuki == "東"
    assert item_sk.douroHaba == Decimal("5.5")
    assert item_sk.douroKubun == "公道"
    assert item_sk.setsumen == Decimal("7.0")
