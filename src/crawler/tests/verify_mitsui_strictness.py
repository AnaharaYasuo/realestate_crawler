
import os
import sys
import django
from decimal import Decimal
import datetime

# Setup Django
sys.path.append('/app/src')
sys.path.append('/app/src/crawler')

# Configure settings manually using realestateSettings
try:
    from crawler import realestateSettings
    realestateSettings.configure()
except Exception as e:
    print(f"Settings config error: {e}")
    pass

from bs4 import BeautifulSoup
from package.models.mitsui import MitsuiMansion, MitsuiKodate, MitsuiTochi, MitsuiInvestmentKodate, MitsuiInvestmentApartment
from package.parser.mitsuiParser import MitsuiMansionParser, MitsuiKodateParser, MitsuiTochiParser, MitsuiInvestmentKodateParser, MitsuiInvestmentApartmentParser

DOCS_DIR = os.environ.get('DOCS_DIR', '/app/Temp/docs')

def test_mansion():
    print("\n[Testing Mitsui Mansion]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/mitsui_mansion_mock.html')
    print(f"Reading {path}")
    if not os.path.exists(path):
        print("Skipping: File not found")
        return

    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = MitsuiMansionParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"SenyuMenseki: {item.senyuMenseki}")
    
    assert item.propertyName, "PropertyName mismatch"
    assert item.price > 0, "Price should be > 0"
    assert item.senyuMenseki is not None, "SenyuMenseki strictly required"
    assert isinstance(item.senyuMenseki, Decimal) or isinstance(item.senyuMenseki, int), "SenyuMenseki type mismatch"

def test_kodate():
    print("\n[Testing Mitsui Kodate]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/mitsui_kodate_mock.html')
    print(f"Reading {path}")
    if not os.path.exists(path):
        print("Skipping: File not found")
        return

    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = MitsuiKodateParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    print(f"TatemonoMenseki: {item.tatemonoMenseki}")
    
    assert item.propertyName
    assert item.tochiMenseki is not None, "TochiMenseki strictly required"
    assert item.tatemonoMenseki is not None, "TatemonoMenseki strictly required"

def test_tochi():
    print("\n[Testing Mitsui Tochi]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/mitsui_tochi_mock.html')
    print(f"Reading {path}")
    if not os.path.exists(path):
        print("Skipping: File not found")
        return

    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = MitsuiTochiParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    print(f"Chimoku: {item.chimoku}")
    
    assert item.propertyName
    assert item.tochiMenseki is not None, "TochiMenseki strictly required"
    assert hasattr(item, 'chimoku'), "Should have chimoku field"

def test_investment_kodate():
    print("\n[Testing Mitsui Investment Kodate]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/mitsui_investment_kodate_mock.html')
    print(f"Reading {path}")
    if not os.path.exists(path):
        print("Skipping: File not found")
        return

    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = MitsuiInvestmentKodateParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Yield: {item.grossYield}")
    print(f"AnnualRent: {item.annualRent}")
    
    assert item.propertyName
    assert item.grossYield is not None
    assert item.annualRent is not None
    assert item.landArea is not None

def test_investment_apartment():
    print("\n[Testing Mitsui Investment Apartment]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/mitsui_investment_apartment_mock.html')
    print(f"Reading {path}")
    if not os.path.exists(path):
        print("Skipping: File not found")
        return

    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # MitsuiInvestmentApartmentParser
    parser = MitsuiInvestmentApartmentParser() 
    item = parser.createEntity()
    
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Yield: {item.grossYield}")
    print(f"TotalUnits: {item.totalUnits}")
    
    assert item.propertyName
    assert item.grossYield is not None
    assert getattr(item, 'totalUnits', None) is not None or getattr(item, 'kanrihi', None) is not None

if __name__ == "__main__":
    try:
        test_mansion()
        test_kodate()
        test_tochi()
        test_investment_kodate()
        test_investment_apartment()
        print("\nAll Mitsui Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
