
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

django.setup()

from bs4 import BeautifulSoup
from package.models.tokyu import TokyuMansion, TokyuKodate, TokyuTochi, TokyuInvestmentApartment
from package.parser.tokyuParser import TokyuMansionParser, TokyuKodateParser, TokyuTochiParser, TokyuInvestmentApartmentParser

def read_mock_html(filename):
    docs_dir = os.environ.get('DOCS_DIR', '/app/Temp/docs')
    path = os.path.join(docs_dir, 'requirements/site_samples', filename)
    
    if not os.path.exists(path):
         # Fallback for local execution if DOCS_DIR isn't set perfectly
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        path = os.path.join(base_dir, 'docs', 'requirements', 'site_samples', filename)

    print(f"Reading {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def test_mansion():
    print("\n[Testing Tokyu Mansion]")
    html = read_mock_html('tokyu_mansion_mock.html')
    soup = BeautifulSoup(html, 'lxml')
    parser = TokyuMansionParser()
    item = parser._parsePropertyDetailPage(TokyuMansion(), soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"SenyuMenseki: {item.senyuMenseki}")
    
    assert item.price > 0, "Price should be > 0"
    assert item.senyuMenseki > 0, "SenyuMenseki should be > 0"
    assert item.inputDate is not None
    assert item.inputDateTime is not None

def test_kodate():
    print("\n[Testing Tokyu Kodate]")
    html = read_mock_html('tokyu_kodate_mock.html')
    soup = BeautifulSoup(html, 'lxml')
    parser = TokyuKodateParser()
    item = parser._parsePropertyDetailPage(TokyuKodate(), soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"TatemonoMenseki: {item.tatemonoMenseki}")
    
    assert item.price > 0, "Price should be > 0"
    assert item.tochiMenseki > 0 or item.tatemonoMenseki > 0, "Area should be > 0"
    assert item.inputDate is not None

def test_tochi():
    print("\n[Testing Tokyu Tochi]")
    html = read_mock_html('tokyu_tochi_mock.html')
    soup = BeautifulSoup(html, 'lxml')
    parser = TokyuTochiParser()
    item = parser._parsePropertyDetailPage(TokyuTochi(), soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Price: {item.price}")
    print(f"TochiMenseki: {item.tochiMenseki}")
    
    assert item.price > 0, "Price should be > 0"
    assert item.tochiMenseki > 0, "TochiMenseki should be > 0"
    assert item.inputDate is not None

def test_investment_apartment():
    print("\n[Testing Tokyu Investment Apartment]")
    html = read_mock_html('tokyu_investment_apartment_mock.html')
    soup = BeautifulSoup(html, 'lxml')
    parser = TokyuInvestmentApartmentParser()
    item = parser._parsePropertyDetailPage(TokyuInvestmentApartment(), soup)
    
    print(f"Name: {item.propertyName}")
    print(f"Yield: {item.grossYield}")
    print(f"AnnualRent: {item.annualRent}")
    print(f"BuildingArea: {item.buildingArea}")
    
    # Strictness Checks
    assert item.grossYield is not None, "grossYield cannot be None"
    assert item.annualRent is not None, "annualRent cannot be None"
    assert item.monthlyRent is not None, "monthlyRent cannot be None"
    assert item.inputDate is not None
    assert item.landArea is not None
    assert item.buildingArea is not None
    assert item.grossYield > 0 or item.annualRent > 0, "Should have yield or rent"

if __name__ == '__main__':
    try:
        test_mansion()
        test_kodate()
        test_tochi()
        test_investment_apartment()
        print("\nAll Tokyu Tests Passed!")
    except Exception as e:
        print(f"\nFAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
