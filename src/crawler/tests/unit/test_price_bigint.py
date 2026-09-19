# -*- coding: utf-8 -*-
"""
価格フィールドの 64-bit BigInteger 拡張および 20億円超高額物件対応テスト
"""
from django.db import models
from package.utils.converter import parse_price
from package.models.base import PropertyBaseModel
from package.models.homes import HomesInvestmentApartment


class TestPriceBigInteger:

    def test_parse_price_high_value(self):
        """20億円以上の高額物件価格が正しく円単位の整数にパースされること"""
        assert parse_price("24億円") == 2400000000
        assert parse_price("50億円") == 5000000000
        assert parse_price("100億円") == 10000000000
        assert parse_price("21億4748万円") == 2147480000
        assert parse_price("25億5000万円") == 2550000000

    def test_price_field_type_is_bigint(self):
        """PropertyBaseModel の price フィールドが BigIntegerField であること"""
        price_field = PropertyBaseModel._meta.get_field("price")
        assert isinstance(price_field, models.BigIntegerField), (
            f"price field should be BigIntegerField, but is {type(price_field)}"
        )

    def test_entity_accepts_high_price(self):
        """24億円などの高額物件がモデルインスタンスの price に格納できること"""
        entity = HomesInvestmentApartment()
        entity.priceStr = "24億円"
        entity.price = parse_price(entity.priceStr)
        assert entity.price == 2400000000
        assert entity.price > 2147483647  # Exceeds 32-bit signed INT max
