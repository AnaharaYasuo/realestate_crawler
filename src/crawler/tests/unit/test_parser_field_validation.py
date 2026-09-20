# -*- coding: utf-8 -*-
"""
パーサー抽出完全性検証 ＆ 0補完・欠損隠蔽防止エラーロギングの単体テスト (TDD)
"""
import json
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


def test_single_structured_log_per_property_with_selectors(caplog):
    """複数項目の不備があっても物件単位で1件の構造化ログが集約出力され、URLやセレクタ情報が含まれること"""
    parser = AthomeMansionParser()
    parser.selectors = {"senyuMenseki": ".menseki-val", "price": ".price-num"}
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-single-log"
    item.propertyName = "テスト集約マンション"
    item.address = "東京都港区六本木1-1"
    item.price = 70000000

    # 4項目欠損
    item.senyuMenseki = None
    item.madori = ""
    item.kouzou = ""
    item.chikunengetsuStr = ""

    with caplog.at_level(logging.ERROR):
        parser.clean_parsed_item(item)

        extraction_logs = [r for r in caplog.records if "[PARSER_EXTRACTION_ERROR]" in r.message]
        # 複数項目不備があっても物件単位で1件のみ出力されること
        assert len(extraction_logs) == 1

        # 構造化ログ（JSON）の検証
        log_msg = extraction_logs[0].message
        assert "Payload: " in log_msg
        payload_str = log_msg.split("Payload: ", 1)[1]
        payload = json.loads(payload_str)

        assert payload["event"] == "PARSER_EXTRACTION_ERROR"
        assert payload["url"] == "https://example.com/test-single-log"
        assert payload["failed_count"] == 4
        assert set(payload["failed_fields"]) == {"senyuMenseki", "madori", "kouzou", "chikunengetsuStr"}
        assert "selectors" in payload
        assert payload["selectors"].get("senyuMenseki") == ".menseki-val"

        # details 内の各項目にもセレクタや理由が含まれること
        senyu_detail = next(d for d in payload["details"] if d["field"] == "senyuMenseki")
        assert senyu_detail["selector"] == ".menseki-val"
        assert senyu_detail["reason"] == "value is None"


def test_model_fields_classification_coverage():
    """モデルスキーマ動的照合: 全モデルの全フィールドが検証対象または任意・メタ項目に100%分類されていること (未分類漏れ防止)"""
    import importlib
    import pkgutil
    import package.models
    from package.parser.baseParser import ParserBase
    from package.models.base import PropertyBaseModel

    # 全モデルモジュールを動的インポート
    for _, modname, _ in pkgutil.walk_packages(package.models.__path__, package.models.__name__ + "."):
        importlib.import_module(modname)

    def get_all_subclasses(cls):
        subclasses = set(cls.__subclasses__())
        for s in list(subclasses):
            subclasses.update(get_all_subclasses(s))
        return subclasses

    all_property_models = [m for m in get_all_subclasses(PropertyBaseModel) if not m._meta.abstract]
    assert len(all_property_models) > 20, f"Expected >20 property models, found {len(all_property_models)}"

    classified_fields = ParserBase.get_classified_fields()
    unclassified_report = {}

    for model_cls in all_property_models:
        model_fields = set(f.name for f in model_cls._meta.fields)
        unclassified = model_fields - classified_fields
        if unclassified:
            unclassified_report[model_cls.__name__] = unclassified

    # 未分類フィールドが1つでもあればテストFAIL（完全性担保）
    assert len(unclassified_report) == 0, f"Unclassified fields found in models: {unclassified_report}"


def test_mutation_testing_detection_rate():
    """故意破損注入テスト (Mutation Testing): 各種別の全必須・重要項目を1つずつ故意に破損させ、100%検知できること"""
    from package.parser.baseParser import ParserBase

    test_cases = [
        (
            AthomeMansionParser(),
            {
                "pageUrl": "https://example.com/test",
                "propertyName": "正常マンション",
                "price": 50000000,
                "priceStr": "5,000万円",
                "address": "東京都千代田区1-1",
                "senyuMenseki": Decimal("70.00"),
                "madori": "3LDK",
                "chikunengetsuStr": "2018年5月",
                "kouzou": "RC",
            },
            "mansion",
        ),
        (
            AthomeKodateParser(),
            {
                "pageUrl": "https://example.com/test",
                "propertyName": "正常戸建",
                "price": 45000000,
                "priceStr": "4,500万円",
                "address": "東京都世田谷区1-1",
                "tochiMenseki": Decimal("100.00"),
                "tatemonoMenseki": Decimal("90.00"),
                "madori": "4LDK",
                "chikunengetsuStr": "2015年10月",
                "kouzou": "木造",
            },
            "kodate",
        ),
        (
            AthomeTochiParser(),
            {
                "pageUrl": "https://example.com/test",
                "propertyName": "正常土地",
                "price": 30000000,
                "priceStr": "3,000万円",
                "address": "東京都杉並区1-1",
                "tochiMenseki": Decimal("120.00"),
            },
            "tochi",
        ),
        (
            AthomeInvestmentApartmentParser(),
            {
                "pageUrl": "https://example.com/test",
                "propertyName": "正常投資アパート",
                "price": 80000000,
                "priceStr": "8,000万円",
                "address": "東京都中野区1-1",
                "grossYield": Decimal("7.50"),
                "annualRent": 6000000,
                "kouzou": "軽量鉄骨",
            },
            "investment",
        ),
    ]

    for parser, valid_kwargs, prop_type in test_cases:
        expected_fields = ParserBase.EXPECTED_SPEC_FIELDS_BY_TYPE[prop_type]

        for target_field in expected_fields:
            # 正常ベースオブジェクト生成
            item = parser.createEntity()
            for k, v in valid_kwargs.items():
                setattr(item, k, v)

            # 正常状態ではエラーゼロであることを確認
            base_errors = parser.validate_extracted_fields(item)
            assert len(base_errors) == 0, f"Baseline should be valid for {prop_type}, but got: {base_errors}"

            # 1項目だけ故意に破損 (Mutation Injection)
            item_mutated = parser.createEntity()
            for k, v in valid_kwargs.items():
                setattr(item_mutated, k, v)

            # None破損
            setattr(item_mutated, target_field, None)
            if target_field == "annualRent":
                setattr(item_mutated, "monthlyRent", None)
            mutated_errors = parser.validate_extracted_fields(item_mutated)
            caught_fields = [e["field"] for e in mutated_errors]
            assert target_field in caught_fields, f"Mutation (None) of '{target_field}' not caught in {prop_type}!"

            # 0値または空文字破損
            item_zero = parser.createEntity()
            for k, v in valid_kwargs.items():
                setattr(item_zero, k, v)
            if target_field in ['price', 'senyuMenseki', 'tochiMenseki', 'tatemonoMenseki', 'grossYield']:
                setattr(item_zero, target_field, Decimal("0.0"))
            elif target_field == "annualRent":
                setattr(item_zero, "annualRent", 0)
                setattr(item_zero, "monthlyRent", 0)
            else:
                setattr(item_zero, target_field, "")
            zero_errors = parser.validate_extracted_fields(item_zero)
            caught_zero_fields = [e["field"] for e in zero_errors]
            assert target_field in caught_zero_fields, f"Mutation (Zero/Empty) of '{target_field}' not caught in {prop_type}!"


def test_validate_required_fields_rejects_non_positive_price():
    """価格が0または負値の場合に validate_required_fields で LoadPropertyPageException が送出されること"""
    parser = AthomeMansionParser()
    item = parser.createEntity()
    item.address = "東京都港区1-1"
    item.price = 0

    try:
        parser.validate_required_fields(item)
        assert False, "Should raise LoadPropertyPageException for price 0"
    except LoadPropertyPageException as e:
        assert "price is invalid or non-positive" in str(e)


def test_validate_extracted_fields_string_and_rent_branches():
    """文字列フィールドやmonthlyRentフォールバック、一般モデルフォールバックの分岐網羅"""
    parser = AthomeInvestmentApartmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://example.com/test-invest-rent"
    item.propertyName = "テストアパート"
    item.address = "東京都中野区1-1"
    item.grossYield = Decimal("6.5")
    item.annualRent = None
    item.monthlyRent = 500000  # annualRentがNoneでもmonthlyRentがあればOK
    item.kouzou = "木造"

    errors = parser.validate_extracted_fields(item)
    error_fields = [e["field"] for e in errors]
    assert "annualRent" not in error_fields

    # 文字列での不正値
    item.price = "-100"
    errors2 = parser.validate_extracted_fields(item)
    error_fields2 = [e["field"] for e in errors2]
    assert "price" in error_fields2



