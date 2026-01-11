import pytest
import os
import sys
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiKodateParser, MitsuiTochiParser, MitsuiInvestmentParser
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestment

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
        # We prefer real snapshots. If not present, skip
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_mansion_mock.html')):
            pytest.skip("Snapshot mitsui_mansion_mock.html not found")
            return
            
        parser = MitsuiMansionParser(None)
        item = parser.createEntity()
        
        # Check if file exists to avoid error if snapshot missing
        html_content = load_mock_html('mitsui_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Parse
        result = parser._parsePropertyDetailPage(item, soup)
        
        # Verify Generic
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
        assert result.tochiMenseki # Should have land area

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

    def test_parse_investment_mansion(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_investment_mansion_mock.html')):
             pytest.skip("mitsui_investment_mansion_mock.html not found")
             return

        parser = MitsuiInvestmentParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('mitsui_investment_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')

        result = parser._parsePropertyDetailPage(item, soup)
        print(f"Investment Mansion: {result.propertyName}")
        assert result.propertyName
        assert result.grossYield is not None

    def test_parse_investment_apartment(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitsui_investment_apartment_mock.html')):
             pytest.skip("mitsui_investment_apartment_mock.html not found")
             return

        parser = MitsuiInvestmentParser(None)
        item = parser.createEntity()
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

        parser = MitsuiInvestmentParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('mitsui_investment_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')

        result = parser._parsePropertyDetailPage(item, soup)
        print(f"Investment Kodate: {result.propertyName}")
        assert result.propertyName
        assert result.grossYield is not None
