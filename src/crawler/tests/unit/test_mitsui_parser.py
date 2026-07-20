import pytest
import os
import sys
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiKodateParser, MitsuiTochiParser, MitsuiInvestmentKodateParser, MitsuiInvestmentApartmentParser
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment

def load_mock_html(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_path = os.path.join(current_dir, '..', 'data', filename)
    with open(mock_path, 'r', encoding='utf-8') as f:
        return f.read()

class TestMitsuiParser:

    def test_create_entity(self):
        parser = MitsuiMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiMansion)

    def test_parse_property_detail_page(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_mansion_mock.html')):
            pytest.skip("Snapshot mitsui_mansion_mock.html not found")
            return
            
        parser = MitsuiMansionParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('mitsui_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Parsed Property: {result.propertyName}")
        assert result.propertyName is not None
        assert len(result.propertyName) > 0
        assert result.address is not None

    def test_create_entity_kodate(self):
        parser = MitsuiKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiKodate)

    def test_parse_kodate_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_kodate_mock.html')):
             pytest.skip("Snapshot mitsui_kodate_mock.html not found")
             return

        parser = MitsuiKodateParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('mitsui_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Kodate Name: {result.propertyName}")
        assert result.propertyName
        assert result.tochiMenseki 

    def test_create_entity_tochi(self):
        parser = MitsuiTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, MitsuiTochi)

    def test_parse_tochi_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_tochi_mock.html')):
             pytest.skip("Snapshot mitsui_tochi_mock.html not found")
             return

        parser = MitsuiTochiParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('mitsui_tochi_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Tochi Name: {result.propertyName}")
        assert result.propertyName
        assert result.tochiMenseki

    def test_parse_investment_apartment(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_investment_apartment_mock.html')):
             pytest.skip("mitsui_investment_apartment_mock.html not found")
             return

        parser = MitsuiInvestmentApartmentParser(None)
        item = parser.createEntity()
        assert isinstance(item, MitsuiInvestmentApartment)
        
        html_content = load_mock_html('mitsui_investment_apartment_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')

        result = parser._parsePropertyDetailPage(item, soup)
        print(f"Investment Apartment: {result.propertyName}")
        assert result.propertyName
        assert result.grossYield is not None

    def test_parse_investment_kodate(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_investment_kodate_mock.html')):
             pytest.skip("mitsui_investment_kodate_mock.html not found")
             return

        parser = MitsuiInvestmentKodateParser(None)
        item = parser.createEntity()
        assert isinstance(item, MitsuiInvestmentKodate)
        
        html_content = load_mock_html('mitsui_investment_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')

        result = parser._parsePropertyDetailPage(item, soup)
        print(f"Investment Kodate: {result.propertyName}")
        assert result.propertyName
        assert result.grossYield is not None

    def test_bracketless_traffic_and_luxury_name(self):
        """テスト: 括弧なしの交通情報（高級テンプレートなど）および高級物件名のパース確認"""
        parser = MitsuiMansionParser(None)
        
        html_content = """
        <html>
        <head><title>九段北の中古マンション一覧</title></head>
        <body>
            <ol class="breadcrumb-list">
                <li class="breadcrumb-list-item"><a class="link" href="/buy/mansion/tokyo/"><span>千代田区の中古マンション一覧</span></a></li>
                <li class="breadcrumb-list-item"><a class="link" href="/buy/mansion/area/"><span>九段北の中古マンション一覧</span></a></li>
                <li class="breadcrumb-list-item"><span>東京ガーデンテラス紀尾井町 紀尾井レジデンス</span></li>
            </ol>
            <h1 class="property-detail-carousel-luxury__building-name">東京ガーデンテラス紀尾井町 紀尾井レジデンス</h1>
            <table>
                <tr>
                    <th>最寄り駅</th>
                    <td>
                        <p>
                            <span class="break-line">東京メトロ半蔵門線 </span>
                            <span class="break-line"><a class="link-text" href="...">半蔵門駅</a></span>
                            <span class="break-line"> 徒歩7分</span>
                        </p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        item = parser.createEntity()
        result = parser._parsePropertyDetailPage(item, soup)
        
        assert result.propertyName == "東京ガーデンテラス紀尾井町 紀尾井レジデンス"
        assert result.railway1 == "東京メトロ半蔵門線"
        assert result.station1 == "半蔵門"
        assert result.railwayWalkMinute1 == 7
