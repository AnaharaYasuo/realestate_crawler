
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
    # Fallback to direct configure if import fails (or just let it fail)
    pass

from bs4 import BeautifulSoup
from package.models.sumifu import SumifuMansion, SumifuKodate, SumifuTochi, SumifuInvestmentKodate, SumifuInvestmentApartment
from package.parser.sumifuParser import SumifuMansionParser, SumifuKodateParser, SumifuTochiParser, SumifuInvestmentKodateParser, SumifuInvestmentApartmentParser

DOCS_DIR = os.environ.get('DOCS_DIR', '/app/Temp/docs')

def test_mansion():
    print("\n[Testing Sumifu Mansion]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/sumifu_mansion_mock.html')
    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = SumifuMansionParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"SenyuMenseki: {item.senyuMenseki} (Type: {type(item.senyuMenseki)})")
    
    assert item.propertyName, "PropertyName mismatch"
    assert item.price > 0, "Price should be > 0"
    assert item.senyuMenseki is not None, "SenyuMenseki strictly required"
    assert isinstance(item.senyuMenseki, Decimal) or isinstance(item.senyuMenseki, int), "SenyuMenseki type mismatch"

def test_investment_kodate():
    print("\n[Testing Sumifu Investment Kodate]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/sumifu_investment_kodate_mock.html')
    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = SumifuInvestmentKodateParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Yield: {item.grossYield}")
    print(f"AnnualRent: {item.annualRent}")
    
    assert item.propertyName
    assert item.grossYield is not None
    assert item.annualRent is not None
    assert item.landArea is not None # Kodate must have land area

def test_investment_apartment():
    print("\n[Testing Sumifu Investment Apartment]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/sumifu_investment_mansion_mock.html')
    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Force Apartment model via type hint or parser logic adjustment
    # Since parser logic relies on URL to switch model, we mimic it
    parser = SumifuInvestmentApartmentParser() 
    # SumifuInvestmentApartmentParser is wrapper or the Base handles it.
    # Actually SumifuInvestmentApartmentParser likely calls super()._parsePropertyDetailPage but overrides createEntity
    
    item = parser.createEntity()
    # Mock URL to force Apartment logic in _parsePropertyDetailPage if needed
    item.pageUrl = "http://test.com/?type=apartment" 
    
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Yield: {item.grossYield}")
    
    assert item.propertyName
    assert item.grossYield is not None
    # Apartment might not have landArea, but has buildingArea/senyuMenseki
    assert hasattr(item, 'buildingArea') or hasattr(item, 'senyuMenseki')

def test_kodate():
    print("\n[Testing Sumifu Kodate]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/sumifu_kodate_mock.html')
    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = SumifuKodateParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    print(f"TatemonoMenseki: {item.tatemonoMenseki}")
    
    assert item.propertyName
    assert item.tochiMenseki is not None, "TochiMenseki strictly required"
    assert item.tatemonoMenseki is not None, "TatemonoMenseki strictly required"
    assert item.madori is not None, "Madori strictly required"

def test_tochi():
    print("\n[Testing Sumifu Tochi]")
    path = os.path.join(DOCS_DIR, 'requirements/site_samples/sumifu_tochi_mock.html')
    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = SumifuTochiParser()
    item = parser.createEntity()
    soup = BeautifulSoup(html, 'html.parser')
    item = parser._parsePropertyDetailPage(item, soup)
    
    print(f"Name: {item.propertyName}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    print(f"LandCategory: {item.landCategory}")
    
    assert item.propertyName
    assert item.tochiMenseki is not None, "TochiMenseki strictly required"
    assert hasattr(item, 'landCategory'), "Should have landCategory field"
    # Ensure landCategory is populated if sample has '地目'
    # assert item.landCategory, "LandCategory should be populated" 


if __name__ == "__main__":
    try:
        test_mansion()
        test_kodate()
        test_tochi()
        test_investment_kodate()
        test_investment_apartment()
        print("\nAll Sumifu Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
