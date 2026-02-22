import pytest
import os
import sys
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.tokyuParser import TokyuMansionParser, TokyuKodateParser, TokyuTochiParser, TokyuInvestmentKodateParser, TokyuInvestmentApartmentParser
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestmentKodate, TokyuInvestmentApartment

def load_mock_html(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_path = os.path.join(current_dir, '..', 'data', filename)
    with open(mock_path, 'r', encoding='utf-8') as f:
        return f.read()

class TestTokyuParser:

    def test_create_entity_mansion(self):
        parser = TokyuMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuMansion)

    def test_parse_mansion_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyu_mansion_mock.html')):
            pytest.skip("Snapshot tokyu_mansion_mock.html not found")
            return
            
        parser = TokyuMansionParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('tokyu_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
    
        result = parser._parsePropertyDetailPage(item, soup)
    
        print(f"Mansion Name: {result.propertyName}")
        assert result.propertyName

    def test_create_entity_kodate(self):
        parser = TokyuKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuKodate)

    def test_parse_kodate_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyu_kodate_mock.html')):
             pytest.skip("Snapshot tokyu_kodate_mock.html not found")
             return

        parser = TokyuKodateParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('tokyu_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Kodate Name: {result.propertyName}")
        assert result.propertyName
        
    def test_create_entity_tochi(self):
        parser = TokyuTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuTochi)

    def test_parse_tochi_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyu_tochi_mock.html')):
             pytest.skip("Snapshot tokyu_tochi_mock.html not found")
             return

        parser = TokyuTochiParser(None)
        item = parser.createEntity()
        html_content = load_mock_html('tokyu_tochi_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Tochi Name: {result.propertyName}")
        assert result.propertyName

    def test_parse_investment_apartment(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyu_investment_apartment_mock.html')):
             pytest.skip("tokyu_investment_apartment_mock.html not found")
             return
             
        parser = TokyuInvestmentApartmentParser()
        item = parser.createEntity()
        assert isinstance(item, TokyuInvestmentApartment)

        html_content = load_mock_html('tokyu_investment_apartment_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Apartment: {result.propertyName}")
        assert result.propertyName

    def test_parse_investment_kodate(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'tokyu_investment_kodate_mock.html')):
             pytest.skip("tokyu_investment_kodate_mock.html not found")
             return
             
        parser = TokyuInvestmentKodateParser()
        item = parser.createEntity()
        assert isinstance(item, TokyuInvestmentKodate)

        html_content = load_mock_html('tokyu_investment_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Kodate: {result.propertyName}")
        assert result.propertyName
