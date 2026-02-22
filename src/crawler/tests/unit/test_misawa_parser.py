import pytest
import os
import sys
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.misawaParser import MisawaMansionParser, MisawaKodateParser, MisawaTochiParser, MisawaInvestmentKodateParser, MisawaInvestmentApartmentParser
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentKodate, MisawaInvestmentApartment

def load_mock_html(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_path = os.path.join(current_dir, '..', 'data', filename)
    with open(mock_path, 'r', encoding='utf-8') as f:
        return f.read()

class TestMisawaParser:

    def test_create_entity_mansion(self):
        parser = MisawaMansionParser()
        entity = parser.createEntity()
        assert isinstance(entity, MisawaMansion)

    def test_parse_mansion_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'misawa_mansion_mock.html')):
             pytest.skip("Snapshot misawa_mansion_mock.html not found")
             return

        parser = MisawaMansionParser()
        item = parser.createEntity()
        html_content = load_mock_html('misawa_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Parsed Property: {result.propertyName}")
        assert result.propertyName is not None
        assert len(result.propertyName) > 0
        assert result.address is not None

    def test_create_entity_kodate(self):
        parser = MisawaKodateParser()
        entity = parser.createEntity()
        assert isinstance(entity, MisawaKodate)

    def test_parse_kodate_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'misawa_kodate_mock.html')):
             pytest.skip("Snapshot misawa_kodate_mock.html not found")
             return

        parser = MisawaKodateParser()
        item = parser.createEntity()
        html_content = load_mock_html('misawa_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Kodate Name: {result.propertyName}")
        assert result.propertyName

    def test_create_entity_tochi(self):
        parser = MisawaTochiParser()
        entity = parser.createEntity()
        assert isinstance(entity, MisawaTochi)

    def test_parse_tochi_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'misawa_tochi_mock.html')):
             pytest.skip("Snapshot misawa_tochi_mock.html not found")
             return

        parser = MisawaTochiParser()
        item = parser.createEntity()
        html_content = load_mock_html('misawa_tochi_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Tochi Name: {result.propertyName}")
        assert result.propertyName

    def test_create_entity_investment_kodate(self):
        parser = MisawaInvestmentKodateParser()
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestmentKodate)

    def test_parse_investment_kodate_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'misawa_investment_mock.html')):
             pytest.skip("Snapshot misawa_investment_mock.html not found")
             return

        parser = MisawaInvestmentKodateParser()
        item = parser.createEntity()
        html_content = load_mock_html('misawa_investment_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Kodate Name: {result.propertyName}")
        assert result.propertyName

    def test_create_entity_investment_apartment(self):
        parser = MisawaInvestmentApartmentParser()
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestmentApartment)

    def test_parse_investment_apartment_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'misawa_investment_mock.html')):
             pytest.skip("Snapshot misawa_investment_mock.html not found")
             return
             
        parser = MisawaInvestmentApartmentParser()
        item = parser.createEntity()
        html_content = load_mock_html('misawa_investment_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Apartment Name: {result.propertyName}")
        assert result.propertyName
