import setup_env  # noqa: F401
import unittest

from package.api.api import (
    API_KEY_NOMURA_INVEST_KODATE_AREA,
    API_KEY_NOMURA_INVEST_APARTMENT_AREA,
    ParseDetailPageAsyncBase,
)
from package.api.registry import ApiRegistry

# API Modules
from package.api.afr import ParseAfrMansionStartAsync, ParseAfrKodateStartAsync, ParseAfrTochiStartAsync
from package.api.athome import (
    ParseAthomeMansionStartAsync,
    ParseAthomeKodateStartAsync,
    ParseAthomeInvestApartmentStartAsync,
    ParseAthomeTochiStartAsync,
)
from package.api.daikyo import ParseDaikyoMansionStartAsync, ParseDaikyoKodateStartAsync, ParseDaikyoTochiStartAsync
from package.api.daiwa import ParseDaiwaMansionStartAsync, ParseDaiwaKodateStartAsync, ParseDaiwaTochiStartAsync
from package.api.heim import ParseHeimMansionStartAsync, ParseHeimKodateStartAsync, ParseHeimTochiStartAsync
from package.api.homes import (
    ParseHomesMansionStartAsync,
    ParseHomesKodateStartAsync,
    ParseHomesInvestApartmentStartAsync,
    ParseHomesTochiStartAsync,
)
from package.api.keikyu import ParseKeikyuMansionStartAsync, ParseKeikyuKodateStartAsync, ParseKeikyuTochiStartAsync
from package.api.keio import ParseKeioMansionStartAsync, ParseKeioKodateStartAsync, ParseKeioTochiStartAsync
from package.api.keisei import ParseKeiseiMansionStartAsync, ParseKeiseiKodateStartAsync, ParseKeiseiTochiStartAsync
from package.api.misawa import ParseMisawaMansionListFuncAsync
from package.api.misawa_investment import (
    ParseMisawaInvestmentApartmentListFuncAsync,
    ParseMisawaInvestmentKodateListFuncAsync,
)
from package.api.mitsui import (
    ParseMitsuiMansionStartAsync,
    ParseMitsuiMansionAreaFuncAsync,
    ParseMitsuiMansionDetailFuncAsync,
    ParseMitsuiTochiStartAsync,
    ParseMitsuiTochiAreaFuncAsync,
    ParseMitsuiKodateStartAsync,
    ParseMitsuiKodateAreaFuncAsync,
)
from package.api.mitsui_investment import (
    ParseMitsuiInvestApartmentStartAsync,
    ParseMitsuiInvestApartmentAreaFuncAsync,
    ParseMitsuiInvestApartmentListFuncAsync,
    ParseMitsuiInvestKodateStartAsync,
    ParseMitsuiInvestKodateAreaFuncAsync,
    ParseMitsuiInvestKodateListFuncAsync,
)
from package.api.mizuho import (
    ParseMizuhoMansionStartAsync,
    ParseMizuhoKodateStartAsync,
    ParseMizuhoTochiStartAsync,
    ParseMizuhoInvestmentStartAsync,
)
from package.api.nomura import (
    ParseNomuraMansionRegionFuncAsync,
    ParseNomuraMansionAreaFuncAsync,
    ParseNomuraKodateRegionFuncAsync,
    ParseNomuraKodateAreaFuncAsync,
    ParseNomuraTochiRegionFuncAsync,
    ParseNomuraTochiAreaFuncAsync,
)
from package.api.nomura_investment import (
    ParseNomuraInvestKodateStartAsync,
    ParseNomuraInvestKodateAreaFuncAsync,
    ParseNomuraInvestKodateListFuncAsync,
    ParseNomuraInvestApartmentStartAsync,
    ParseNomuraInvestApartmentAreaFuncAsync,
    ParseNomuraInvestApartmentListFuncAsync,
)
from package.api.odakyu import (
    ParseOdakyuMansionStartAsync,
    ParseOdakyuKodateStartAsync,
    ParseOdakyuTochiStartAsync,
    ParseOdakyuInvestmentStartAsync,
)
from package.api.rearie import ParseRearieMansionStartAsync, ParseRearieKodateStartAsync, ParseRearieTochiStartAsync
from package.api.seibu import ParseSeibuMansionStartAsync, ParseSeibuKodateStartAsync, ParseSeibuTochiStartAsync
from package.api.sekisui import ParseSekisuiMansionStartAsync, ParseSekisuiKodateStartAsync, ParseSekisuiTochiStartAsync
from package.api.smtrc import (
    ParseSmtrcMansionStartAsync,
    ParseSmtrcKodateStartAsync,
    ParseSmtrcTochiStartAsync,
    ParseSmtrcInvestmentStartAsync,
)
from package.api.sotetsu import ParseSotetsuMansionStartAsync, ParseSotetsuKodateStartAsync, ParseSotetsuTochiStartAsync
from package.api.sumai1 import (
    ParseSumai1MansionStartAsync,
    ParseSumai1KodateStartAsync,
    ParseSumai1TochiStartAsync,
    ParseSumai1InvestmentStartAsync,
)
from package.api.sumifu import (
    ParseSumifuMansionRegionFuncAsync,
    ParseSumifuMansionAreaFuncAsync,
    ParseSumifuTochiStartAsync,
    ParseSumifuTochiRegionFuncAsync,
    ParseSumifuTochiAreaFuncAsync,
    ParseSumifuKodateStartAsync,
    ParseSumifuKodateRegionFuncAsync,
    ParseSumifuKodateAreaFuncAsync,
)
from package.api.sumifu_investment import (
    ParseSumifuInvestApartmentStartAsync,
    ParseSumifuInvestApartmentListFuncAsync,
    ParseSumifuInvestKodateStartAsync,
    ParseSumifuInvestKodateListFuncAsync,
)
from package.api.sumirin import (
    ParseSumirinMansionStartAsync,
    ParseSumirinKodateStartAsync,
    ParseSumirinTochiStartAsync,
    ParseSumirinInvestmentStartAsync,
)
from package.api.tokyu import (
    ParseTokyuMansionStartAsync,
    ParseTokyuMansionAreaFuncAsync,
    ParseTokyuTochiStartAsync,
    ParseTokyuTochiAreaFuncAsync,
    ParseTokyuKodateStartAsync,
    ParseTokyuKodateAreaFuncAsync,
)
from package.api.tokyu_investment import (
    ParseTokyuInvestApartmentStartAsync,
    ParseTokyuInvestApartmentListFuncAsync,
    ParseTokyuInvestKodateStartAsync,
    ParseTokyuInvestKodateListFuncAsync,
)
from package.api.totate import ParseTotateMansionStartAsync, ParseTotateKodateStartAsync, ParseTotateTochiStartAsync


class TestAllCrawlersMiddlePageParallel(unittest.TestCase):
    """
    全対象サイトの中間ページ並行度（MIDDLE_PARARELL_LIMIT = 3）および多階層化の検証
    Issue #870 AC-1, AC-2, AC-3, AC-4, AC-5
    """

    def test_mizuho_middle_parallel_limit(self):
        """Mizuho全種別のStart並行度が3であることを検証"""
        classes = [
            ParseMizuhoMansionStartAsync,
            ParseMizuhoKodateStartAsync,
            ParseMizuhoTochiStartAsync,
            ParseMizuhoInvestmentStartAsync,
        ]
        for cls in classes:
            inst = cls()
            self.assertEqual(inst._getLocalPararellLimit(), 3, f"{cls.__name__} local limit != 3")
            self.assertEqual(inst._getCloudPararellLimit(), 3, f"{cls.__name__} cloud limit != 3")

    def test_homes_middle_parallel_limit(self):
        """Homes全種別のStart並行度が3であることを検証"""
        classes = [
            ParseHomesMansionStartAsync,
            ParseHomesKodateStartAsync,
            ParseHomesInvestApartmentStartAsync,
            ParseHomesTochiStartAsync,
        ]
        for cls in classes:
            inst = cls()
            self.assertEqual(inst._getLocalPararellLimit(), 3, f"{cls.__name__} local limit != 3")
            self.assertEqual(inst._getCloudPararellLimit(), 3, f"{cls.__name__} cloud limit != 3")

    def test_athome_middle_parallel_limit(self):
        """Athome全種別のStart並行度が3であることを検証"""
        classes = [
            ParseAthomeMansionStartAsync,
            ParseAthomeKodateStartAsync,
            ParseAthomeInvestApartmentStartAsync,
            ParseAthomeTochiStartAsync,
        ]
        for cls in classes:
            inst = cls()
            self.assertEqual(inst._getLocalPararellLimit(), 3, f"{cls.__name__} local limit != 3")
            self.assertEqual(inst._getCloudPararellLimit(), 3, f"{cls.__name__} cloud limit != 3")

    def test_investment_sites_middle_parallel_limit(self):
        """投資系サイト（Mitsui, Sumifu, Tokyu, Misawa）の中間並行度が3であることを検証"""
        classes = [
            ParseMitsuiInvestApartmentStartAsync,
            ParseMitsuiInvestApartmentAreaFuncAsync,
            ParseMitsuiInvestApartmentListFuncAsync,
            ParseMitsuiInvestKodateStartAsync,
            ParseMitsuiInvestKodateAreaFuncAsync,
            ParseMitsuiInvestKodateListFuncAsync,
            ParseSumifuInvestApartmentStartAsync,
            ParseSumifuInvestApartmentListFuncAsync,
            ParseSumifuInvestKodateStartAsync,
            ParseSumifuInvestKodateListFuncAsync,
            ParseTokyuInvestApartmentStartAsync,
            ParseTokyuInvestApartmentListFuncAsync,
            ParseTokyuInvestKodateStartAsync,
            ParseTokyuInvestKodateListFuncAsync,
            ParseMisawaInvestmentApartmentListFuncAsync,
            ParseMisawaInvestmentKodateListFuncAsync,
            ParseMisawaMansionListFuncAsync,
        ]
        for cls in classes:
            inst = cls()
            self.assertEqual(inst._getLocalPararellLimit(), 3, f"{cls.__name__} local limit != 3")
            self.assertEqual(inst._getCloudPararellLimit(), 3, f"{cls.__name__} cloud limit != 3")

    def test_major_sites_area_and_region_limits(self):
        """大手サイト（Mitsui, Sumifu, Tokyu, Nomura）の全種別Area/Region並行度が3であることを検証"""
        classes = [
            ParseMitsuiMansionStartAsync,
            ParseMitsuiMansionAreaFuncAsync,
            ParseMitsuiTochiStartAsync,
            ParseMitsuiTochiAreaFuncAsync,
            ParseMitsuiKodateStartAsync,
            ParseMitsuiKodateAreaFuncAsync,
            ParseSumifuMansionRegionFuncAsync,
            ParseSumifuMansionAreaFuncAsync,
            ParseSumifuTochiStartAsync,
            ParseSumifuTochiRegionFuncAsync,
            ParseSumifuTochiAreaFuncAsync,
            ParseSumifuKodateStartAsync,
            ParseSumifuKodateRegionFuncAsync,
            ParseSumifuKodateAreaFuncAsync,
            ParseTokyuMansionStartAsync,
            ParseTokyuMansionAreaFuncAsync,
            ParseTokyuTochiStartAsync,
            ParseTokyuTochiAreaFuncAsync,
            ParseTokyuKodateStartAsync,
            ParseTokyuKodateAreaFuncAsync,
            ParseNomuraMansionRegionFuncAsync,
            ParseNomuraMansionAreaFuncAsync,
            ParseNomuraKodateRegionFuncAsync,
            ParseNomuraKodateAreaFuncAsync,
            ParseNomuraTochiRegionFuncAsync,
            ParseNomuraTochiAreaFuncAsync,
        ]
        for cls in classes:
            inst = cls()
            self.assertEqual(inst._getLocalPararellLimit(), 3, f"{cls.__name__} local limit != 3")
            self.assertEqual(inst._getCloudPararellLimit(), 3, f"{cls.__name__} cloud limit != 3")

    def test_mid_tier_and_railway_sites_start_limits(self):
        """電鉄系・ハウスメーカー系・信託系サイトのStart並行度が3であることを検証"""
        classes = [
            ParseAfrMansionStartAsync, ParseAfrKodateStartAsync, ParseAfrTochiStartAsync,
            ParseDaikyoMansionStartAsync, ParseDaikyoKodateStartAsync, ParseDaikyoTochiStartAsync,
            ParseDaiwaMansionStartAsync, ParseDaiwaKodateStartAsync, ParseDaiwaTochiStartAsync,
            ParseHeimMansionStartAsync, ParseHeimKodateStartAsync, ParseHeimTochiStartAsync,
            ParseKeikyuMansionStartAsync, ParseKeikyuKodateStartAsync, ParseKeikyuTochiStartAsync,
            ParseKeioMansionStartAsync, ParseKeioKodateStartAsync, ParseKeioTochiStartAsync,
            ParseKeiseiMansionStartAsync, ParseKeiseiKodateStartAsync, ParseKeiseiTochiStartAsync,
            ParseOdakyuMansionStartAsync, ParseOdakyuKodateStartAsync, ParseOdakyuTochiStartAsync, ParseOdakyuInvestmentStartAsync,
            ParseRearieMansionStartAsync, ParseRearieKodateStartAsync, ParseRearieTochiStartAsync,
            ParseSeibuMansionStartAsync, ParseSeibuKodateStartAsync, ParseSeibuTochiStartAsync,
            ParseSekisuiMansionStartAsync, ParseSekisuiKodateStartAsync, ParseSekisuiTochiStartAsync,
            ParseSmtrcMansionStartAsync, ParseSmtrcKodateStartAsync, ParseSmtrcTochiStartAsync, ParseSmtrcInvestmentStartAsync,
            ParseSotetsuMansionStartAsync, ParseSotetsuKodateStartAsync, ParseSotetsuTochiStartAsync,
            ParseSumai1MansionStartAsync, ParseSumai1KodateStartAsync, ParseSumai1TochiStartAsync, ParseSumai1InvestmentStartAsync,
            ParseSumirinMansionStartAsync, ParseSumirinKodateStartAsync, ParseSumirinTochiStartAsync, ParseSumirinInvestmentStartAsync,
            ParseTotateMansionStartAsync, ParseTotateKodateStartAsync, ParseTotateTochiStartAsync,
        ]
        for cls in classes:
            inst = cls()
            self.assertEqual(inst._getLocalPararellLimit(), 3, f"{cls.__name__} local limit != 3")
            self.assertEqual(inst._getCloudPararellLimit(), 3, f"{cls.__name__} cloud limit != 3")

    def test_nomura_investment_hierarchy_and_parallel(self):
        """野村投資（アパート・戸建て賃貸）の多階層化と並行探索を検証"""
        # 1. StartクラスのシードURLが主要エリアに展開されていること
        kodate_start = ParseNomuraInvestKodateStartAsync()
        self.assertGreaterEqual(len(kodate_start.urlList), 8)
        self.assertTrue(any("131" in url for url in kodate_start.urlList))
        self.assertEqual(kodate_start._getLocalPararellLimit(), 3)

        apt_start = ParseNomuraInvestApartmentStartAsync()
        self.assertGreaterEqual(len(apt_start.urlList), 8)
        self.assertTrue(any("131" in url for url in apt_start.urlList))
        self.assertEqual(apt_start._getLocalPararellLimit(), 3)

        # 2. Area中間クラスが存在し並行度が3であること
        kodate_area = ParseNomuraInvestKodateAreaFuncAsync()
        self.assertEqual(kodate_area._getLocalPararellLimit(), 3)
        self.assertEqual(kodate_area._getCloudPararellLimit(), 3)

        apt_area = ParseNomuraInvestApartmentAreaFuncAsync()
        self.assertEqual(apt_area._getLocalPararellLimit(), 3)
        self.assertEqual(apt_area._getCloudPararellLimit(), 3)

        # 3. List中間クラスの並行度が3であること
        kodate_list = ParseNomuraInvestKodateListFuncAsync()
        self.assertEqual(kodate_list._getLocalPararellLimit(), 3)

        apt_list = ParseNomuraInvestApartmentListFuncAsync()
        self.assertEqual(apt_list._getLocalPararellLimit(), 3)

        # 4. ApiRegistryにAreaキーが登録されていること
        self.assertIsNotNone(ApiRegistry.get(API_KEY_NOMURA_INVEST_KODATE_AREA))
        self.assertIsNotNone(ApiRegistry.get(API_KEY_NOMURA_INVEST_APARTMENT_AREA))

    def test_get_parallel_limit_waf_isolation(self):
        """ApiAsyncProcBase._getPararellLimit()において、WAFキャップが詳細ページ限定で適用されることを検証"""
        # 中間ページクラス（例: ParseMitsuiMansionAreaFuncAsync）はWAFキャップに左右されず自身の設定並行度(3)を返す
        area_inst = ParseMitsuiMansionAreaFuncAsync()
        self.assertEqual(area_inst._getPararellLimit(), 3)

        # 詳細ページクラス（ParseDetailPageAsyncBase）はWAFキャップ（mitsui=3）が適用される
        detail_inst = ParseMitsuiMansionDetailFuncAsync()
        self.assertIsInstance(detail_inst, ParseDetailPageAsyncBase)
        self.assertEqual(detail_inst._getPararellLimit(), 3)


if __name__ == "__main__":
    unittest.main()
