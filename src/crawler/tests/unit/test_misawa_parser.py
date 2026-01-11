import pytest
import os
import sys
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.misawaParser import MisawaParser
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestment

def load_mock_html(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_path = os.path.join(current_dir, '..', 'data', filename)
    with open(mock_path, 'r', encoding='utf-8') as f:
        return f.read()

class TestMisawaParser:

    def test_create_entity_mansion(self):
        parser = MisawaParser('1')
        entity = parser.createEntity()
        assert isinstance(entity, MisawaMansion)

    def test_parse_mansion_detail(self):
        parser = MisawaParser('1')
        item = parser.createEntity()
        html_content = load_mock_html('misawa_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Parsed Property: {result.propertyName}")
        assert result.propertyName is not None
        assert len(result.propertyName) > 0
        assert result.address is not None

    def test_create_entity_kodate(self):
        parser = MisawaParser('2')
        entity = parser.createEntity()
        assert isinstance(entity, MisawaKodate)

    def test_parse_kodate_detail(self):
        parser = MisawaParser('2')
        item = parser.createEntity()
        html_content = load_mock_html('misawa_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Kodate Name: {result.propertyName}")
        assert result.propertyName

    def test_create_entity_tochi(self):
        parser = MisawaParser('3')
        entity = parser.createEntity()
        assert isinstance(entity, MisawaTochi)

    def test_parse_tochi_detail(self):
        parser = MisawaParser('3')
        item = parser.createEntity()
        html_content = load_mock_html('misawa_tochi_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Tochi Name: {result.propertyName}")
        assert result.propertyName

    def test_create_entity_investment(self):
        parser = MisawaParser('4')
        entity = parser.createEntity()
        assert isinstance(entity, MisawaInvestment)

    def test_parse_investment_detail(self):
        parser = MisawaParser('4')
        item = parser.createEntity()
        html_content = load_mock_html('misawa_investment_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Investment Name: {result.propertyName}")
        assert result.propertyName
