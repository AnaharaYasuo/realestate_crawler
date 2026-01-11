import pytest
import os
import sys
import datetime
from decimal import Decimal
from bs4 import BeautifulSoup

# Ensure package is in path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from package.parser.nomuraParser import NomuraMansionParser, NomuraKodateParser, NomuraTochiParser
from package.models.nomura import NomuraMansion, NomuraKodate, NomuraTochi

def load_mock_html(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mock_path = os.path.join(current_dir, '..', 'data', filename)
    with open(mock_path, 'r', encoding='utf-8') as f:
        return f.read()

class TestNomuraParser:

    def test_create_entity(self):
        parser = NomuraMansionParser()
        entity = parser.createEntity()
        assert isinstance(entity, NomuraMansion)

    def test_parse_property_detail_page(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'nomura_mansion_mock.html')):
             pytest.skip("Snapshot nomura_mansion_mock.html not found")
             return

        parser = NomuraMansionParser()
        item = parser.createEntity()
        
        html_content = load_mock_html('nomura_mansion_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Parse
        result = parser._parsePropertyDetailPage(item, soup)
        
        # Verify Generic
        print(f"Parsed Property: {result.propertyName}")
        assert result.propertyName is not None
        
        # assert result.price > 0
        assert result.address is not None

    def test_create_entity_kodate(self):
        parser = NomuraKodateParser()
        entity = parser.createEntity()
        assert isinstance(entity, NomuraKodate)

    def test_parse_kodate_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'nomura_kodate_mock.html')):
             pytest.skip("Snapshot nomura_kodate_mock.html not found")
             return

        parser = NomuraKodateParser()

        item = parser.createEntity()
        html_content = load_mock_html('nomura_kodate_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Kodate Name: {result.propertyName}")
        assert result.propertyName
        
    def test_create_entity_tochi(self):
        parser = NomuraTochiParser()
        entity = parser.createEntity()
        assert isinstance(entity, NomuraTochi)

    def test_parse_tochi_detail(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'data', 'nomura_tochi_mock.html')):
             pytest.skip("Snapshot nomura_tochi_mock.html not found")
             return

        parser = NomuraTochiParser()
        item = parser.createEntity()
        html_content = load_mock_html('nomura_tochi_mock.html')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = parser._parsePropertyDetailPage(item, soup)
        
        print(f"Tochi Name: {result.propertyName}")
        assert result.propertyName
