from pathlib import Path


def test_athome_investment_parser_does_not_skip_missing_yield_or_rent():
    src = (
        Path(__file__).resolve().parents[2]
        / "package"
        / "parser"
        / "athomeParser.py"
    ).read_text(encoding="utf-8")
    assert "Athome investment listing missing yield/rent" not in src


def test_hook_guard_has_single_pr_guard():
    guard_src = (
        Path(__file__).resolve().parents[4]
        / ".agents"
        / "scripts"
        / "hook_guard.py"
    ).read_text(encoding="utf-8")
    assert "Single-PR guard" in guard_src


def test_nomura_investment_parser_does_not_skip_missing_yield_or_rent():
    nomura_src = (
        Path(__file__).resolve().parents[2]
        / "package"
        / "parser"
        / "nomuraParser.py"
    ).read_text(encoding="utf-8")
    assert "Nomura invest listing missing published yield/rent" not in nomura_src


def test_url_router_resolves_athome_buy_other_and_kodate_cross_types():
    from package.parser.athomeParser import (
        AthomeInvestmentApartmentParser,
        AthomeKodateParser,
        AthomeMansionParser,
    )
    from package.utils.url_router import UrlRouter

    assert isinstance(
        UrlRouter.create_parser(url="https://www.athome.co.jp/buy_other/1152805314/", property_type="mansion"),
        AthomeMansionParser,
    )
    assert isinstance(
        UrlRouter.create_parser(url="https://www.athome.co.jp/buy_other/1152805314/", property_type="kodate"),
        AthomeKodateParser,
    )
    assert isinstance(
        UrlRouter.create_parser(url="https://www.athome.co.jp/kodate/123456/", property_type="apartment"),
        AthomeInvestmentApartmentParser,
    )
