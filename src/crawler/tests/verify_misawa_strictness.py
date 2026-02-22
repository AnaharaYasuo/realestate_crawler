
import os
import sys
import django
from decimal import Decimal
import datetime

# Setup Django
sys.path.append('/app/src')
sys.path.append('/app/src/crawler')

try:
    from crawler import realestateSettings
    realestateSettings.configure()
except Exception:
    pass

from bs4 import BeautifulSoup
from package.models.misawa import MisawaMansion, MisawaKodate, MisawaTochi, MisawaInvestmentApartment
from package.parser.misawaParser import MisawaParser, MisawaInvestmentApartmentParser

DOCS_DIR = os.environ.get('DOCS_DIR', '/app/Temp/docs')

def read_mock(filename):
    path = os.path.join(DOCS_DIR, 'requirements/site_samples', filename)
    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def test_mansion():
    print("\n[Testing Misawa Mansion]")
    html = read_mock('misawa_tochi_mock.html') # Content is Mansion
    parser = MisawaParser('1') # 1=Mansion
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"SenyuMenseki: {item.senyuMenseki}")
    
    assert item.propertyName
    assert item.price > 0
    assert item.senyuMenseki > 0

def test_kodate():
    print("\n[Testing Misawa Kodate]")
    html = read_mock('misawa_kodate_mock.html')
    parser = MisawaParser('2') # 2=Kodate
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    
    assert item.propertyName
    assert item.price > 0
    assert item.tochiMenseki > 0

def test_tochi():
    print("\n[Testing Misawa Tochi]")
    html = read_mock('misawa_mansion_mock.html') # Content is Land
    parser = MisawaParser('3') # 3=Tochi
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    print(f"LandCategory: {item.landCategory}")
    
    assert item.propertyName
    assert item.tochiMenseki > 0

def test_investment_apartment():
    print("\n[Testing Misawa Investment Apartment]")
    html = read_mock('misawa_investment_mock.html')
    parser = MisawaInvestmentApartmentParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Yield: {item.grossYield}")
    print(f"AnnualRent: {item.annualRent}")
    
    assert item.propertyName
    assert item.grossYield is not None
    assert item.annualRent > 0

if __name__ == "__main__":
    try:
        test_mansion()
        test_kodate()
        test_tochi()
        test_investment_apartment()
        print("\nAll Misawa Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
