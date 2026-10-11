import setup_env  # noqa: F401
import unittest
from bs4 import BeautifulSoup

from package.api.adaptive_concurrency import AdaptiveConcurrencyController
from package.api.api import ParseDetailPageAsyncBase
from package.api.mitsui import ParseMitsuiMansionAreaFuncAsync, ParseMitsuiMansionStartAsync
from package.api.nomura import ParseNomuraMansionAreaFuncAsync, ParseNomuraMansionRegionFuncAsync
from package.api.sumifu import ParseSumifuMansionAreaFuncAsync, ParseSumifuMansionRegionFuncAsync
from package.api.tokyu import ParseTokyuMansionAreaFuncAsync, ParseTokyuMansionStartAsync
from package.parser.nomuraParser import NomuraMansionParser


class TestMansionCrawlerSpeedup(unittest.TestCase):
    def test_middle_page_parallel_limits(self):
        """中間ページの並行度が3に設定されていることを検証"""
        self.assertEqual(ParseMitsuiMansionAreaFuncAsync()._getLocalPararellLimit(), 3)
        self.assertEqual(ParseMitsuiMansionStartAsync()._getLocalPararellLimit(), 3)

        self.assertEqual(ParseNomuraMansionAreaFuncAsync()._getLocalPararellLimit(), 3)
        self.assertEqual(ParseNomuraMansionRegionFuncAsync()._getLocalPararellLimit(), 3)

        self.assertEqual(ParseSumifuMansionAreaFuncAsync()._getLocalPararellLimit(), 3)
        self.assertEqual(ParseSumifuMansionRegionFuncAsync()._getLocalPararellLimit(), 3)

        self.assertEqual(ParseTokyuMansionAreaFuncAsync()._getLocalPararellLimit(), 3)
        self.assertEqual(ParseTokyuMansionStartAsync()._getLocalPararellLimit(), 3)

    def test_waf_concurrency_caps_and_delays(self):
        """三井および野村のWAFキャップ（3）とダウンロードディレイ（0.5s）を検証"""
        self.assertEqual(AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS.get("mitsui"), 3)
        self.assertEqual(AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS.get("nomura"), 3)
        self.assertEqual(AdaptiveConcurrencyController.SITE_CONCURRENCY_CAPS.get("smtrc"), 2)

        self.assertEqual(ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS.get("mitsui"), 0.5)
        self.assertEqual(ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS.get("nomura"), 0.5)
        self.assertEqual(ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS.get("smtrc"), 1.0)

    def test_nomura_card_price_extraction(self):
        """野村の一覧カードからdiv.item_titleに阻まれず価格が正常抽出されることを検証"""
        html = """
        <div class="item_resultsmall click_R">
            <div class="item_resultsmall_upper">
                <div class="item_title_wrapper">
                    <div class="item_title">
                        <h2><a href="/mansion/id/FF4C1050/">ルモンド代官山</a></h2>
                    </div>
                </div>
                <div class="item_info">
                    <p class="price"><strong>2億4,500</strong>万円</p>
                </div>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        link = soup.select_one("a")
        parser = NomuraMansionParser()
        price = parser._extract_card_price(link)
        self.assertEqual(price, 245000000)


if __name__ == "__main__":
    unittest.main()
