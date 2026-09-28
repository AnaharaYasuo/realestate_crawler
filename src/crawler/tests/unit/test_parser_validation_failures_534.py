import importlib
import logging
from unittest.mock import patch

import pytest
import setup_env  # noqa: F401
from bs4 import BeautifulSoup
from package.models.tokyu import TokyuTochi
from package.parser.mitsuiParser import MitsuiInvestmentApartmentParser
from package.parser.sumifuParser import (
    SumifuInvestmentApartmentParser,
    SumifuKodateParser,
    SumifuMansionParser,
)
from package.parser.tokyuParser import TokyuKodateParser, TokyuMansionParser
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.url_router import UrlRouter

SUMIFU_UNIT_URL = "https://www.stepon.co.jp/mansion/detail_16133137/"


def _soup(text: str) -> BeautifulSoup:
    return BeautifulSoup(f"<html><body><p>{text}</p></body></html>", "html.parser")


class TestSectionalUnitSwitchGuard534:
    """Issue #534: 区分住戸ページは一棟投資・戸建てパーサーへ切り替えない。"""

    @pytest.mark.parametrize(
        ("detected", "title", "text", "specs"),
        [
            ("investment", "ライオンズプラザ町屋", "賃貸中", {"専有面積": "20.52m²", "現況": "賃貸中", "構造": "SRC"}),
            ("kodate", "テラスハウスヴィップ東長崎", "テラスハウス", {"専有面積": "65.10m²", "間取り": "3LDK"}),
        ],
    )
    def test_sectional_unit_is_not_switched(self, detected, title, text, specs, caplog):
        parser = SumifuMansionParser("")
        item = parser.createEntity()

        with patch.object(PropertyTypeDetector, "detect", return_value=detected), \
             patch.object(UrlRouter, "create_parser") as mock_create, \
             caplog.at_level(logging.INFO):
            used_parser, used_item = parser._maybe_switch_parser(
                SUMIFU_UNIT_URL, title, _soup(text), specs, item
            )

        assert used_parser is parser
        assert used_item is item
        mock_create.assert_not_called()
        assert f"detected '{detected}' skipped (sectional unit)" in caplog.text

    def test_real_detection_of_rented_unit_is_guarded(self):
        parser = SumifuMansionParser("")
        item = parser.createEntity()
        specs = {"専有面積": "20.52m²", "現況": "賃貸中", "構造": "SRC"}

        used_parser, used_item = parser._maybe_switch_parser(
            SUMIFU_UNIT_URL, "ライオンズプラザ町屋", _soup("賃貸中"), specs, item
        )

        assert used_parser is parser
        assert used_item is item

    def test_page_with_land_area_still_switches_to_kodate(self):
        parser = SumifuMansionParser("")
        item = parser.createEntity()
        specs = {"土地面積": "80.00m²", "建物面積": "95.00m²", "専有面積": "95.00m²"}

        used_parser, used_item = parser._maybe_switch_parser(
            "https://www.stepon.co.jp/mansion/detail_99999999/",
            "中古一戸建て",
            _soup("一戸建て"),
            specs,
            item,
        )

        assert isinstance(used_parser, SumifuKodateParser)
        assert used_item is not item
        assert used_item.pageUrl == "https://www.stepon.co.jp/mansion/detail_99999999/"

    def test_page_without_senyu_still_switches_to_investment(self):
        parser = SumifuMansionParser("")
        item = parser.createEntity()
        specs = {"表面利回り": "7.5%", "土地面積": "120.00m²"}

        used_parser, _ = parser._maybe_switch_parser(
            SUMIFU_UNIT_URL, "一棟アパート", _soup("表面利回り 7.5%"), specs, item
        )

        assert isinstance(used_parser, SumifuInvestmentApartmentParser)

    def test_non_mansion_parser_still_switches_on_sectional_page(self):
        parser = SumifuKodateParser("")
        item = parser.createEntity()
        specs = {"専有面積": "20.52m²", "表面利回り": "7.5%"}

        used_parser, used_item = parser._maybe_switch_parser(
            SUMIFU_UNIT_URL, "投資用区分", _soup("表面利回り 7.5%"), specs, item
        )

        assert isinstance(used_parser, SumifuInvestmentApartmentParser)
        assert used_item is not item

    def test_is_sectional_unit_page(self):
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積": "20m²"}) is True
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積": "20m²", "土地面積": "80m²"}) is False
        assert SumifuMansionParser._is_sectional_unit_page({"土地面積": "80m²"}) is False
        assert SumifuMansionParser._is_sectional_unit_page({}) is False
        assert SumifuMansionParser._is_sectional_unit_page(None) is False

    @pytest.mark.parametrize("blank", ["", "  ", "-", "－", "―", "—", None])
    def test_blank_land_area_is_treated_as_absent(self, blank):
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積": "20m²", "土地面積": blank}) is True
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積": blank}) is False

    def test_qualified_labels_are_recognized(self):
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積（壁芯）": "20m²"}) is True
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積(登記)": "20m²"}) is True
        assert SumifuMansionParser._is_sectional_unit_page(
            {"専有面積（壁芯）": "20m²", "土地面積（公簿）": "80m²"}
        ) is False
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積率": "20%"}) is False

    def test_dict_spec_values_are_inspected(self):
        assert SumifuMansionParser._is_sectional_unit_page(
            {"専有面積": {"value": "20m²"}, "土地面積": {"value": "-"}}
        ) is True
        assert SumifuMansionParser._is_sectional_unit_page(
            {"専有面積": {"value": "20m²"}, "土地面積": {"value": "80m²"}}
        ) is False
        assert SumifuMansionParser._is_sectional_unit_page({"専有面積": {"value": ""}}) is False


class TestTokyuFloorLabel535:
    """Issue #535: 「所在階数」ラベルから所在階・建物階数を抽出する。"""

    def setup_method(self):
        self.parser = TokyuMansionParser()

    def test_combined_floor_label(self):
        specs = {
            "建物構造": {"value": "鉄筋コンクリート造"},
            "所在階数": {"value": "4階 / 地上9階"},
        }

        assert self.parser._parseKaisu(None, specs) == "4階"
        assert self.parser._parseKaisuStr(None, specs) == "4階 / 地上9階"
        assert self.parser._parseTatemonoKaisu(None, specs) == "地上9階"

    def test_legacy_floor_label_is_kept(self):
        specs = {
            "建物構造": {"value": "鉄筋コンクリート造 地上12階建"},
            "所在階": {"value": "5階"},
        }

        assert self.parser._parseKaisu(None, specs) == "5階"
        assert self.parser._parseKaisuStr(None, specs) == "5階"
        assert self.parser._parseTatemonoKaisu(None, specs) == "地上12階"

    def test_combined_floor_label_without_slash(self):
        specs = {"所在階数": {"value": "3階"}}

        assert self.parser._parseKaisu(None, specs) == "3階"
        assert self.parser._parseTatemonoKaisu(None, specs) == ""

    def test_missing_floor_labels(self):
        specs = {"建物構造": {"value": "鉄筋コンクリート造"}}

        assert self.parser._parseKaisu(None, specs) == ""
        assert self.parser._parseKaisuStr(None, specs) == ""

    def test_floor_count_label_has_priority(self):
        specs = {"階数": {"value": "地上9階"}, "所在階": {"value": "5階"}}

        assert self.parser._parseKaisuStr(None, specs) == "地上9階"

    def test_kodate_keeps_structure_fallback(self):
        specs = {"建物構造": {"value": "木造2階建"}}

        assert TokyuKodateParser()._parseKaisuStr(None, specs) == "木造2階建"


class TestTokyuTochiOptionalFields538:
    """Issue #538: 東急土地の任意項目は空欄でもバリデーションを通過する。"""

    @pytest.mark.parametrize("field", ["chisei", "boukaChiiki", "saikenchiku", "sonotaChiiki", "kokudoHou"])
    def test_optional_field_allows_blank(self, field):
        assert TokyuTochi._meta.get_field(field).blank is True

    def test_other_required_field_still_required(self):
        assert TokyuTochi._meta.get_field("chimoku").blank is False


class TestUrlRouterRoutes539:
    """Issue #539: 全ルートの parser_cls / model_cls が実在する。"""

    @pytest.mark.parametrize("route", UrlRouter.ROUTES, ids=lambda r: f"{r['site']}-{r['property_type']}-{r['parser_cls']}")
    def test_route_classes_exist(self, route):
        parser_mod = importlib.import_module(route["parser_module"])
        model_mod = importlib.import_module(route["model_module"])
        assert hasattr(parser_mod, route["parser_cls"])
        assert hasattr(model_mod, route["model_cls"])

    def test_mitsui_investment_route_creates_parser(self):
        parser = UrlRouter.create_parser("https://www.rehouse.co.jp/buy/tohshi/abc/bkdetail/F1234567/")
        assert isinstance(parser, MitsuiInvestmentApartmentParser)
