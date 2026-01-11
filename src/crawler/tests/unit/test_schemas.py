import pytest
from package.schemas.property import MansionDataSchema, PropertyDataSchema
from decimal import Decimal
from datetime import date
from pydantic import ValidationError

def test_property_schema_valid():
    data = {
        "propertyName": "テスト物件",
        "pageUrl": "http://example.com",
        "priceStr": "5,000万円",
        "price": 50000000,
        "address": "東京都港区"
    }
    schema = PropertyDataSchema(**data)
    assert schema.propertyName == "テスト物件"
    assert schema.price == 50000000

def test_property_schema_invalid_price():
    data = {
        "propertyName": "テスト物件",
        "pageUrl": "http://example.com",
        "priceStr": "価格未定",
        "price": -100, # 負の値はNG
        "address": "東京都港区"
    }
    with pytest.raises(ValidationError):
        PropertyDataSchema(**data)

def test_mansion_schema_valid():
    data = {
        "propertyName": "テストマンション",
        "pageUrl": "http://example.com/mansion",
        "priceStr": "8,000万円",
        "price": 80000000,
        "address": "東京都中央区",
        "senyuMensekiStr": "70.5㎡",
        "senyuMenseki": Decimal("70.5"),
        "chikunengetsuStr": "2020年1月",
        "chikunengetsu": date(2020, 1, 1)
    }
    schema = MansionDataSchema(**data)
    assert schema.senyuMenseki == Decimal("70.5")
    assert schema.chikunengetsu == date(2020, 1, 1)

def test_mansion_schema_invalid_menseki():
    data = {
        "propertyName": "テストマンション",
        "pageUrl": "http://example.com/mansion",
        "priceStr": "8,000万円",
        "price": 80000000,
        "address": "東京都中央区",
        "senyuMenseki": Decimal("10001") # 大きすぎ
    }
    with pytest.raises(ValidationError):
        MansionDataSchema(**data)
