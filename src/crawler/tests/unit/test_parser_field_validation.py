# -*- coding: utf-8 -*-
"""
パーサー抽出完全性検証 ＆ 0補完・欠損隠蔽防止エラーロギングの単体テスト (TDD)
"""
import logging
from decimal import Decimal

from package.parser.baseParser import LoadPropertyPageException
from package.parser.athomeParser import (
    AthomeMansionParser,
    AthomeKodateParser,
    AthomeTochiParser,
    AthomeInvestmentApartmentParser
)


def test_fatal_fields_missing_raises_exception():
    """致命的必須項目 (price, address) 欠損時は LoadPropertyPageException が送出されること"""
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-fatal"
    item.price = None
    item.address = ""

    try:
        parser.validate_required_fields(item)
        assert False, "Should have raised LoadPropertyPageException"
    except LoadPropertyPageException as e:
        assert "price is None" in str(e) or "address is empty" in str(e)


def test_mansion_missing_spec_fields_logs_extraction_errors(caplog):
    """マンションで専有面積や間取り、築年月、構造が欠落している場合、[PARSER_EXTRACTION_ERROR] ログが出力されること"""
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-mansion"
    item.propertyName = "テストマンション"
    item.address = "東京都新宿区西新宿1-1"
    item.price = 50000000
    item.priceStr = "5,000万円"
    item.traffic = "新宿駅 徒歩5分"

    # スペック項目をあえて未抽出 (None / 0 / "") のままにする
    item.senyuMenseki = None
    item.senyuMensekiStr = ""
    item.madori = ""
    item.kouzou = ""
    item.chikunengetsuStr = ""

    with caplog.at_level(logging.ERROR):
        errors = parser.validate_extracted_fields(item)
        assert len(errors) > 0
        error_fields = [e["field"] for e in errors]
        assert "senyuMenseki" in error_fields
        assert "madori" in error_fields
        assert "kouzou" in error_fields
        assert "chikunengetsuStr" in error_fields

        # clean_parsed_item 実行時にも自動的にエラーログが出力されること
        parser.clean_parsed_item(item)
        assert any("[PARSER_EXTRACTION_ERROR]" in record.message for record in caplog.records)
        assert any("senyuMenseki" in record.message for record in caplog.records)


def test_kodate_zero_menseki_logs_extraction_error(caplog):
    """戸建で土地面積・建物面積が 0 になっている場合、単に隠蔽されず [PARSER_EXTRACTION_ERROR] が出力されること"""
    parser = AthomeKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-kodate"
    item.propertyName = "テスト戸建"
    item.address = "東京都中野区上高田1-1"
    item.price = 40000000
    item.priceStr = "4,000万円"
    item.traffic = "新井薬師前駅 徒歩7分"
    item.madori = "3LDK"
    item.kouzou = "木造"
    item.chikunengetsuStr = "2015年3月"
    item.tochikenri = "所有権"

    # 不正な0値
    item.tochiMenseki = Decimal("0.0")
    item.tatemonoMenseki = Decimal("0.0")

    with caplog.at_level(logging.ERROR):
        errors = parser.validate_extracted_fields(item)
        error_fields = [e["field"] for e in errors]
        assert "tochiMenseki" in error_fields
        assert "tatemonoMenseki" in error_fields

        parser.clean_parsed_item(item)
        assert any("[PARSER_EXTRACTION_ERROR]" in record.message and "tochiMenseki" in record.message for record in caplog.records)


def test_investment_missing_yield_logs_error(caplog):
    """投資物件で利回りや賃料が欠落している場合、[PARSER_EXTRACTION_ERROR] が出力されること"""
    parser = AthomeInvestmentApartmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-invest"
    item.propertyName = "テストアパート"
    item.address = "東京都杉並区高円寺南1-1"
    item.price = 60000000
    item.priceStr = "6,000万円"
    item.traffic = "高円寺駅 徒歩4分"
    item.kouzou = "木造"
    item.annualRent = None
    item.grossYield = None

    with caplog.at_level(logging.ERROR):
        errors = parser.validate_extracted_fields(item)
        error_fields = [e["field"] for e in errors]
        assert "grossYield" in error_fields
        assert "annualRent" in error_fields

        parser.clean_parsed_item(item)
        assert any("[PARSER_EXTRACTION_ERROR]" in record.message and "grossYield" in record.message for record in caplog.records)


def test_fully_extracted_property_logs_no_errors(caplog):
    """全必須・重要項目が正しく抽出できている場合、エラーログが一切出力されないこと"""
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-perfect"
    item.propertyName = "グランドメゾン新宿"
    item.address = "東京都新宿区西新宿1-1"
    item.price = 50000000
    item.priceStr = "5,000万円"
    item.traffic = "新宿駅 徒歩5分"
    item.senyuMenseki = Decimal("65.50")
    item.senyuMensekiStr = "65.50㎡"
    item.madori = "2LDK"
    item.kouzou = "RC造"
    item.chikunengetsuStr = "2020年1月"
    item.kaisu = "5階"

    with caplog.at_level(logging.ERROR):
        errors = parser.validate_extracted_fields(item)
        assert len(errors) == 0

        parser.clean_parsed_item(item)
        extraction_errors = [r for r in caplog.records if "[PARSER_EXTRACTION_ERROR]" in r.message]
        assert len(extraction_errors) == 0
