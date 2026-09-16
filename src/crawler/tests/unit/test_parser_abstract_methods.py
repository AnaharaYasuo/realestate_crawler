# -*- coding: utf-8 -*-
"""
全DBモデル保持項目に対応する標準パース抽出メソッド群の完全定義および
ダミー空実装排除のAST解析自動検証テスト（Single Source of Truth）
"""
import pytest
import importlib
import inspect
import ast
from package.parser.baseParser import ParserBase

# 1. 各物件種別のDBテーブル保持項目に1対1完全対応するパース関数定義
MANSION_MANDATORY_METHODS = [
    "_parsePrice",          # DB: price (数値)
    "_parsePriceStr",       # DB: priceStr (文字列)
    "_parseAddress",        # DB: address (住所)
    "_parsePropertyName",   # DB: propertyName (物件名)
    "_parseTransport1",     # DB: transport1 (最寄り駅/交通)
    "_parseSenyuMenseki",   # DB: senyuMenseki (専有面積)
    "_parseMadori",         # DB: madori (間取り)
    "_parseChikunengetsu",  # DB: chikunengetsu (築年月)
    "_parseKouzou",         # DB: kouzou (建物構造)
    "_parseFloor",          # DB: floor (所在階)
    "_parseSouKosu",        # DB: souKosu (総戸数)
    "_parseManagementFee",  # DB: managementFee (管理費)
    "_parseReserveFund",    # DB: reserveFund (修繕積立金)
    "_parseKenpei",         # DB: kenpei (建ぺい率)
    "_parseYouseki",        # DB: youseki (容積率)
]

KODATE_MANDATORY_METHODS = [
    "_parsePrice",          # DB: price
    "_parsePriceStr",       # DB: priceStr
    "_parseAddress",        # DB: address
    "_parsePropertyName",   # DB: propertyName
    "_parseTransport1",     # DB: transport1
    "_parseTochiMenseki",   # DB: tochiMenseki (土地面積)
    "_parseTatemonoMenseki",# DB: tatemonoMenseki (建物面積)
    "_parseMadori",         # DB: madori
    "_parseChikunengetsu",  # DB: chikunengetsu
    "_parseKouzou",         # DB: kouzou
    "_parseKenpei",         # DB: kenpei (建ぺい率)
    "_parseYouseki",        # DB: youseki (容積率)
    "_parseRights",         # DB: rights (権利)
    "_parseYoutoChiiki",    # DB: youtoChiiki (用途地域)
]

TOCHI_MANDATORY_METHODS = [
    "_parsePrice",          # DB: price
    "_parsePriceStr",       # DB: priceStr
    "_parseAddress",        # DB: address
    "_parsePropertyName",   # DB: propertyName
    "_parseTransport1",     # DB: transport1
    "_parseTochiMenseki",   # DB: tochiMenseki
    "_parseKenpei",         # DB: kenpei (建ぺい率)
    "_parseYouseki",        # DB: youseki (容積率)
    "_parseChimoku",        # DB: chimoku (地目)
    "_parseSetsudou",       # DB: setsudou (接道)
    "_parseRights",         # DB: rights
    "_parseYoutoChiiki",    # DB: youtoChiiki
]

INVESTMENT_MANDATORY_METHODS = [
    "_parsePrice",          # DB: price
    "_parsePriceStr",       # DB: priceStr
    "_parseAddress",        # DB: address
    "_parsePropertyName",   # DB: propertyName
    "_parseTransport1",     # DB: transport1
    "_parseGrossYield",     # DB: grossYield (表面利回り)
    "_parseAnnualRent",     # DB: annualRent (満室年収)
    "_parseChikunengetsu",  # DB: chikunengetsu
    "_parseKouzou",         # DB: kouzou
    "_parseTochiMenseki",   # DB: tochiMenseki
    "_parseTatemonoMenseki",# DB: tatemonoMenseki
]

# 全24社の代表パーサークラス群
MANSION_PARSERS = [
    ("mitsui", "package.parser.mitsuiParser", "MitsuiMansionParser"),
    ("sumifu", "package.parser.sumifuParser", "SumifuMansionParser"),
    ("tokyu", "package.parser.tokyuParser", "TokyuMansionParser"),
    ("nomura", "package.parser.nomuraParser", "NomuraMansionParser"),
    ("misawa", "package.parser.misawaParser", "MisawaMansionParser"),
    ("sekisui", "package.parser.sekisuiParser", "SekisuiMansionParser"),
    ("smtrc", "package.parser.smtrcParser", "SmtrcMansionParser"),
    ("sumai1", "package.parser.sumai1Parser", "Sumai1MansionParser"),
    ("mizuho", "package.parser.mizuhoParser", "MizuhoMansionParser"),
    ("afr", "package.parser.afrParser", "AfrMansionParser"),
    ("daikyo", "package.parser.daikyoParser", "DaikyoMansionParser"),
    ("daiwa", "package.parser.daiwaParser", "DaiwaMansionParser"),
    ("heim", "package.parser.heimParser", "HeimMansionParser"),
    ("homes", "package.parser.homesParser", "HomesMansionParser"),
    ("athome", "package.parser.athomeParser", "AthomeMansionParser"),
    ("keikyu", "package.parser.keikyuParser", "KeikyuMansionParser"),
    ("keio", "package.parser.keioParser", "KeioMansionParser"),
    ("keisei", "package.parser.keiseiParser", "KeiseiMansionParser"),
    ("odakyu", "package.parser.odakyuParser", "OdakyuMansionParser"),
    ("rearie", "package.parser.rearieParser", "RearieMansionParser"),
    ("seibu", "package.parser.seibuParser", "SeibuMansionParser"),
    ("sotetsu", "package.parser.sotetsuParser", "SotetsuMansionParser"),
    ("sumirin", "package.parser.sumirinParser", "SumirinMansionParser"),
    ("totate", "package.parser.totateParser", "TotateMansionParser"),
]

KODATE_PARSERS = [
    ("mitsui", "package.parser.mitsuiParser", "MitsuiKodateParser"),
    ("sumifu", "package.parser.sumifuParser", "SumifuKodateParser"),
    ("tokyu", "package.parser.tokyuParser", "TokyuKodateParser"),
    ("nomura", "package.parser.nomuraParser", "NomuraKodateParser"),
    ("misawa", "package.parser.misawaParser", "MisawaKodateParser"),
    ("sekisui", "package.parser.sekisuiParser", "SekisuiKodateParser"),
    ("smtrc", "package.parser.smtrcParser", "SmtrcKodateParser"),
    ("sumai1", "package.parser.sumai1Parser", "Sumai1KodateParser"),
    ("mizuho", "package.parser.mizuhoParser", "MizuhoKodateParser"),
    ("afr", "package.parser.afrParser", "AfrKodateParser"),
    ("daikyo", "package.parser.daikyoParser", "DaikyoKodateParser"),
    ("daiwa", "package.parser.daiwaParser", "DaiwaKodateParser"),
    ("heim", "package.parser.heimParser", "HeimKodateParser"),
    ("homes", "package.parser.homesParser", "HomesKodateParser"),
    ("athome", "package.parser.athomeParser", "AthomeKodateParser"),
    ("keikyu", "package.parser.keikyuParser", "KeikyuKodateParser"),
    ("keio", "package.parser.keioParser", "KeioKodateParser"),
    ("keisei", "package.parser.keiseiParser", "KeiseiKodateParser"),
    ("odakyu", "package.parser.odakyuParser", "OdakyuKodateParser"),
    ("rearie", "package.parser.rearieParser", "RearieKodateParser"),
    ("seibu", "package.parser.seibuParser", "SeibuKodateParser"),
    ("sotetsu", "package.parser.sotetsuParser", "SotetsuKodateParser"),
    ("sumirin", "package.parser.sumirinParser", "SumirinKodateParser"),
    ("totate", "package.parser.totateParser", "TotateKodateParser"),
]

TOCHI_PARSERS = [
    ("mitsui", "package.parser.mitsuiParser", "MitsuiTochiParser"),
    ("sumifu", "package.parser.sumifuParser", "SumifuTochiParser"),
    ("tokyu", "package.parser.tokyuParser", "TokyuTochiParser"),
    ("nomura", "package.parser.nomuraParser", "NomuraTochiParser"),
    ("misawa", "package.parser.misawaParser", "MisawaTochiParser"),
    ("sekisui", "package.parser.sekisuiParser", "SekisuiTochiParser"),
    ("smtrc", "package.parser.smtrcParser", "SmtrcTochiParser"),
    ("sumai1", "package.parser.sumai1Parser", "Sumai1TochiParser"),
    ("mizuho", "package.parser.mizuhoParser", "MizuhoTochiParser"),
    ("afr", "package.parser.afrParser", "AfrTochiParser"),
    ("daikyo", "package.parser.daikyoParser", "DaikyoTochiParser"),
    ("daiwa", "package.parser.daiwaParser", "DaiwaTochiParser"),
    ("heim", "package.parser.heimParser", "HeimTochiParser"),
    ("homes", "package.parser.homesParser", "HomesTochiParser"),
    ("athome", "package.parser.athomeParser", "AthomeTochiParser"),
    ("keikyu", "package.parser.keikyuParser", "KeikyuTochiParser"),
    ("keio", "package.parser.keioParser", "KeioTochiParser"),
    ("keisei", "package.parser.keiseiParser", "KeiseiTochiParser"),
    ("odakyu", "package.parser.odakyuParser", "OdakyuTochiParser"),
    ("rearie", "package.parser.rearieParser", "RearieTochiParser"),
    ("seibu", "package.parser.seibuParser", "SeibuTochiParser"),
    ("sotetsu", "package.parser.sotetsuParser", "SotetsuTochiParser"),
    ("sumirin", "package.parser.sumirinParser", "SumirinTochiParser"),
    ("totate", "package.parser.totateParser", "TotateTochiParser"),
]

INVESTMENT_PARSERS = [
    ("mitsui", "package.parser.mitsuiParser", "MitsuiInvestmentApartmentParser"),
    ("sumifu", "package.parser.sumifuParser", "SumifuInvestmentApartmentParser"),
    ("tokyu", "package.parser.tokyuParser", "TokyuInvestmentApartmentParser"),
    ("nomura", "package.parser.nomuraParser", "NomuraInvestmentApartmentParser"),
    ("smtrc", "package.parser.smtrcParser", "SmtrcInvestmentParser"),
    ("athome", "package.parser.athomeParser", "AthomeInvestmentApartmentParser"),
    ("homes", "package.parser.homesParser", "HomesInvestmentApartmentParser"),
]


def is_dummy_method(method) -> bool:
    """
    ソースコードの AST 解析を行い、本体が単なる pass / return 固定値 / Exception のみの
    形骸化したダミー空メソッドであるかを高精度に検出する。
    """
    try:
        source = inspect.getsource(method)
        dedented = inspect.cleandoc(source)
        tree = ast.parse(dedented)
        func_def = tree.body[0]
        if not isinstance(func_def, ast.FunctionDef):
            return False

        # docstring 以外の文
        body = [stmt for stmt in func_def.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))]
        if len(body) == 0:
            return True
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                return True
            if isinstance(stmt, ast.Raise):
                return True
            if isinstance(stmt, ast.Return):
                if stmt.value is None or isinstance(stmt.value, ast.Constant):
                    return True
        return False
    except Exception:
        return False


@pytest.mark.parametrize("company, module_path, class_name", MANSION_PARSERS)
def test_mansion_parsers_implement_mandatory_methods(company, module_path, class_name):
    """
    【マンション専用テスト】全マンションパーサーがDB保持項目対応の全パース関数を完備し、
    ダミー空実装を含まないことを高精度アサーション。
    """
    mod = importlib.import_module(module_path)
    parser_cls = getattr(mod, class_name)
    instance = parser_cls()

    for method_name in MANSION_MANDATORY_METHODS:
        assert hasattr(instance, method_name), f"{class_name} missing DB-field corresponding method '{method_name}'"
        method = getattr(instance, method_name)
        if method.__qualname__.split(".")[0] == class_name:
            assert not is_dummy_method(method), f"{class_name}.{method_name} is a dummy empty method!"


@pytest.mark.parametrize("company, module_path, class_name", KODATE_PARSERS)
def test_kodate_parsers_implement_mandatory_methods(company, module_path, class_name):
    """
    【戸建専用テスト】全戸建パーサーがDB保持項目対応の全パース関数を完備していることを検証。
    """
    mod = importlib.import_module(module_path)
    parser_cls = getattr(mod, class_name)
    instance = parser_cls()

    for method_name in KODATE_MANDATORY_METHODS:
        assert hasattr(instance, method_name), f"{class_name} missing DB-field corresponding method '{method_name}'"
        method = getattr(instance, method_name)
        if method.__qualname__.split(".")[0] == class_name:
            assert not is_dummy_method(method), f"{class_name}.{method_name} is a dummy empty method!"


@pytest.mark.parametrize("company, module_path, class_name", TOCHI_PARSERS)
def test_tochi_parsers_implement_mandatory_methods(company, module_path, class_name):
    """
    【土地専用テスト】全土地パーサーがDB保持項目対応の全パース関数を完備していることを検証。
    """
    mod = importlib.import_module(module_path)
    parser_cls = getattr(mod, class_name)
    instance = parser_cls()

    for method_name in TOCHI_MANDATORY_METHODS:
        assert hasattr(instance, method_name), f"{class_name} missing DB-field corresponding method '{method_name}'"
        method = getattr(instance, method_name)
        if method.__qualname__.split(".")[0] == class_name:
            assert not is_dummy_method(method), f"{class_name}.{method_name} is a dummy empty method!"


@pytest.mark.parametrize("company, module_path, class_name", INVESTMENT_PARSERS)
def test_investment_parsers_implement_mandatory_methods(company, module_path, class_name):
    """
    【投資用物件専用テスト】全投資用パーサーがDB保持項目対応の全パース関数を完備していることを検証。
    """
    mod = importlib.import_module(module_path)
    parser_cls = getattr(mod, class_name)
    instance = parser_cls()

    for method_name in INVESTMENT_MANDATORY_METHODS:
        assert hasattr(instance, method_name), f"{class_name} missing DB-field corresponding method '{method_name}'"
        method = getattr(instance, method_name)
        if method.__qualname__.split(".")[0] == class_name:
            assert not is_dummy_method(method), f"{class_name}.{method_name} is a dummy empty method!"


def test_all_parsers_inherit_from_parser_base():
    """
    【普遍アーキテクチャ検証】package/parser/ 配下のすべてのパーサークラスが
    例外なく ParserBase および物件種別毎の Base パーサー (MansionParserBase, KodateParserBase, TochiParserBase, InvestmentParserBase)
    を正しく継承しているかを全件動的検出して自動アサーション。
    """
    import os
    import pkgutil
    import package.parser as parser_pkg
    from package.parser.baseParser import MansionParserBase, KodateParserBase, TochiParserBase, InvestmentParserBase

    parser_dir = os.path.dirname(parser_pkg.__file__)
    non_inheriting_classes = []

    for _, module_name, _ in pkgutil.iter_modules([parser_dir]):
        if module_name in ["baseParser"]:
            continue
        mod = importlib.import_module(f"package.parser.{module_name}")
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            # クラスであり、かつ該当モジュール内で定義された Parser クラスを対象
            if inspect.isclass(attr) and attr.__module__ == mod.__name__ and attr_name.endswith("Parser"):
                if not issubclass(attr, ParserBase):
                    non_inheriting_classes.append((module_name, attr_name, "ParserBase"))

                # 物件種別ごとの Base パーサー継承チェック
                if "MansionParser" in attr_name:
                    if not issubclass(attr, MansionParserBase):
                        non_inheriting_classes.append((module_name, attr_name, "MansionParserBase"))
                elif "KodateParser" in attr_name:
                    if not issubclass(attr, KodateParserBase):
                        non_inheriting_classes.append((module_name, attr_name, "KodateParserBase"))
                elif "TochiParser" in attr_name:
                    if not issubclass(attr, TochiParserBase):
                        non_inheriting_classes.append((module_name, attr_name, "TochiParserBase"))
                elif "Investment" in attr_name or attr_name == "InvestmentParser":
                    if not (issubclass(attr, InvestmentParserBase) or issubclass(attr, KodateParserBase)):
                        non_inheriting_classes.append((module_name, attr_name, "InvestmentParserBase"))

    assert len(non_inheriting_classes) == 0, f"Found parser classes not inheriting from required Base parser: {non_inheriting_classes}"



