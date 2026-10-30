import pytest
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError

from package.parser.rearieParser import RearieMansionParser
from package.parser.baseParser import ListingEndedException, ServerBusyException
from package.parser.sekisuiParser import SekisuiMansionParser
from package.parser.misawaParser import MisawaMansionParser
from package.utils.property_type_detector import PropertyTypeDetector
from package.models.sumifu import SumifuInvestmentApartment


class TestRearieStrictListingEnded:
    """パナソニック（リアリエ）の掲載終了検知が明示的文言でのみ行われることをテスト"""

    def test_rearie_raises_when_explicit_listing_ended_text_present(self):
        html = """
        <html>
            <head><title>【パナソニック ホームズ】掲載終了物件</title></head>
            <body>
                <p>大変申し訳ございません。お探しの物件は見つかりませんでした。掲載を終了しました。</p>
            </body>
        </html>
        """
        parser = RearieMansionParser()
        item = parser.createEntity()
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(ListingEndedException):
            parser._parsePropertyDetailPage(item, soup)

    def test_rearie_does_not_raise_listing_ended_when_specs_empty_without_explicit_text(self):
        """物件スペックが存在しない場合でも、掲載終了文言がなければListingEndedExceptionを出さない"""
        html = """
        <html>
            <head><title>Panasonic Homes 物件詳細</title></head>
            <body>
                <h1>テスト物件タイトル</h1>
                <div>何らかの動的ローディング中のプレースホルダー</div>
            </body>
        </html>
        """
        parser = RearieMansionParser()
        item = parser.createEntity()
        soup = BeautifulSoup(html, "html.parser")
        # 掲載終了文言がないので ListingEndedException は送出されず、パース処理が進む
        res = parser._parsePropertyDetailPage(item, soup)
        assert res.propertyName == "テスト物件タイトル"


class TestSekisuiParserUrlWithoutTrailingSlash:
    """積水ハウスの末尾スラッシュなしURLが抽出できることをテスト"""

    @pytest.mark.asyncio
    async def test_parse_root_page_matches_url_without_trailing_slash(self):
        html = """
        <html>
            <body>
                <div class="item-card">
                    <span class="price">4,500万円</span>
                    <a href="/kanto/mansion/detail/C20010064363">詳細を見る（スラッシュなし）</a>
                </div>
                <div class="item-card">
                    <span class="price">5,200万円</span>
                    <a href="/kanto/mansion/detail/C20010064364/">詳細を見る（スラッシュあり）</a>
                </div>
            </body>
        </html>
        """
        parser = SekisuiMansionParser()
        soup = BeautifulSoup(html, "html.parser")
        items = [item async for item in parser.parseRootPage(soup)]
        urls = [it.url for it in items]
        assert "https://sumusite.sekisuihouse.co.jp/kanto/mansion/detail/C20010064363" in urls
        assert "https://sumusite.sekisuihouse.co.jp/kanto/mansion/detail/C20010064364/" in urls
        assert len(items) == 2


class TestMisawaMaintenanceDetection:
    """ミサワホームがメンテナンス画面を返した場合に ServerBusyException を送出することをテスト"""

    @pytest.mark.asyncio
    async def test_parse_list_page_detects_maintenance(self):
        html = """
        <html>
            <head><title>システムメンテナンス中 | ミサワホーム不動産</title></head>
            <body>
                <h1>現在システムメンテナンスを実施しております。</h1>
                <p>ご不便をおかけいたしますが、今しばらくお待ちください。</p>
            </body>
        </html>
        """
        parser = MisawaMansionParser()
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(ServerBusyException):
            _ = [item async for item in parser.parsePropertyListPage(soup)]

    def test_parse_detail_page_detects_maintenance(self):
        html = """
        <html>
            <head><title>システムメンテナンス中</title></head>
            <body>
                <p>現在メンテナンス中です。</p>
            </body>
        </html>
        """
        parser = MisawaMansionParser()
        item = MagicMock()
        soup = BeautifulSoup(html, "html.parser")
        with pytest.raises(ServerBusyException):
            parser._parsePropertyDetailPage(item, soup)


class TestPropertyTypeDetectorAndModels:
    """東急の投資用その他物件および住友の底地権投資用物件の判定とモデル整合性テスト"""

    def test_tokyu_other_investment_with_land_and_building_not_mansion(self):
        """専有面積があっても、土地面積と建物面積が両方ある投資用物件は区分マンションにならない"""
        specs = {
            "propertyName": "投資用物件（その他）",
            "propertyType": "その他(土地・建物)",
            "senyuMenseki": 57.0,
            "tatemonMenseki": 115.7,
            "tochiMenseki": 73.95,
            "annualRent": 1200000,
            "grossYield": 6.5,
        }
        detected = PropertyTypeDetector.detect_from_object(specs)
        assert detected == "apartment"

    def test_sumifu_investment_apartment_allows_blank_chikunengetsu(self):
        """底地権など建物がない投資物件で chikunengetsuStr が空文字でも chikunengetsuStr 単体でバリデーションエラーにならない"""
        item = SumifuInvestmentApartment(
            chikunengetsuStr="",
        )
        try:
            item.clean_fields()
        except ValidationError as ve:
            # chikunengetsuStr がエラーに含まれていないことを検証
            assert "chikunengetsuStr" not in ve.message_dict
