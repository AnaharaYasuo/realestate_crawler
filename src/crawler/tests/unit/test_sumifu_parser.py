import pytest
import os
import sys
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.sumifuParser import SumifuMansionParser, SumifuTochiParser, SumifuKodateParser, SumifuInvestmentKodateParser, SumifuInvestmentApartmentParser
from package.models.sumifu import SumifuMansion, SumifuTochi, SumifuKodate, SumifuInvestmentKodate, SumifuInvestmentApartment

def load_mock_html(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_path = os.path.join(current_dir, '..', 'data', filename)
    with open(mock_path, 'r', encoding='utf-8') as f:
        return f.read()

class TestSumifuParser:

    def test_create_entity(self):
        parser = SumifuMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuMansion)

    def test_parse_property_detail_page(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'sumifu_mansion_mock.html')):
             pytest.skip("Snapshot sumifu_mansion_mock.html not found")
             return

        parser = SumifuMansionParser(None)
        item = parser.createEntity()
        
        html_content = load_mock_html('sumifu_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Parsed Property: {result.propertyName}")
        assert result.propertyName is not None
        assert len(result.propertyName) > 0
        assert result.address is not None
        assert result.senyuMenseki > 0

    def test_create_entity_kodate(self):
        parser = SumifuKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuKodate)

    def test_parse_kodate_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'sumifu_kodate_mock.html')):
             pytest.skip("Snapshot sumifu_kodate_mock.html not found")
             return

        parser = SumifuKodateParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('sumifu_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Kodate Name: {result.propertyName}")
        assert result.propertyName
        
    def test_create_entity_tochi(self):
        parser = SumifuTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, SumifuTochi)

    def test_parse_tochi_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'sumifu_tochi_mock.html')):
             pytest.skip("Snapshot sumifu_tochi_mock.html not found")
             return

        parser = SumifuTochiParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('sumifu_tochi_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Tochi Name: {result.propertyName}")
        assert result.propertyName

    def test_parse_investment_apartment(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'sumifu_investment_apartment_mock.html')):
             pytest.skip("sumifu_investment_apartment_mock.html not found")
             return
             
        parser = SumifuInvestmentApartmentParser()
        item = parser.createEntity()
        assert isinstance(item, SumifuInvestmentApartment)
        
        html_content = load_mock_html('sumifu_investment_apartment_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Apartment: {result.propertyName}")
        assert result.propertyName

    def test_parse_investment_kodate(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'sumifu_investment_kodate_mock.html')):
             pytest.skip("sumifu_investment_kodate_mock.html not found")
             return
             
        parser = SumifuInvestmentKodateParser()
        item = parser.createEntity()
        assert isinstance(item, SumifuInvestmentKodate)

        html_content = load_mock_html('sumifu_investment_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Kodate: {result.propertyName}")
        assert result.propertyName
