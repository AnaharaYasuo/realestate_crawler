from bs4 import BeautifulSoup
import pytest

from package.models.tokyu import (
    TokyuInvestmentApartment,
    TokyuInvestmentKodate,
    TokyuKodate,
    TokyuMansion,
    TokyuTochi,
)
from package.parser.baseParser import ListingEndedException
from package.parser.tokyuParser import (
    TokyuInvestmentApartmentParser,
    TokyuInvestmentKodateParser,
    TokyuKodateParser,
    TokyuMansionParser,
    TokyuTochiParser,
    check_tokyu_listing_ended,
)

class TestTokyuParser:

    def test_create_entity(self):
        parser = TokyuMansionParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuMansion)

    def test_create_entity_kodate(self):
        parser = TokyuKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuKodate)

    def test_create_entity_tochi(self):
        parser = TokyuTochiParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuTochi)

    def test_create_entity_investment_apartment(self):
        parser = TokyuInvestmentApartmentParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuInvestmentApartment)

    def test_create_entity_investment_kodate(self):
        parser = TokyuInvestmentKodateParser(None)
        entity = parser.createEntity()
        assert isinstance(entity, TokyuInvestmentKodate)

    def test_parser_configuration(self):
        parser = TokyuMansionParser(None)
        assert parser.__class__.__name__ == "TokyuMansionParser"

    def test_check_tokyu_listing_ended_catalog_page(self):
        # 1. カタログタイトル (購入・売却・賃貸 物件情報)
        catalog_html = "<html><head><title>ライオンズマンション北綾瀬第７の購入・売却・賃貸 物件情報｜東急リバブル</title></head><body><h1>ライオンズマンション北綾瀬第７</h1></body></html>"
        soup = BeautifulSoup(catalog_html, "html.parser")
        with pytest.raises(ListingEndedException):
            check_tokyu_listing_ended(soup, "https://www.livable.co.jp/mansion/C13267Q02/")

        # 2. 売り出し部屋なし案内 (価格なし + 売り出し中の物件を見る)
        no_rooms_html = "<html><head><title>テストマンション｜東急リバブル</title></head><body><h2>売り出し中の物件を見る</h2></body></html>"
        soup_no_rooms = BeautifulSoup(no_rooms_html, "html.parser")
        with pytest.raises(ListingEndedException):
            check_tokyu_listing_ended(soup_no_rooms, "https://www.livable.co.jp/mansion/C12345/")

        # 3. 正常な販売中物件ページは例外を送出しないこと
        active_html = "<html><head><title>北千住パーク・ファミリア(C13267U96)｜マンション購入｜東急リバブル</title></head><body><div class='price'>6,199万円</div></body></html>"
        soup_active = BeautifulSoup(active_html, "html.parser")
        check_tokyu_listing_ended(soup_active, "https://www.livable.co.jp/mansion/C13267U96/")

