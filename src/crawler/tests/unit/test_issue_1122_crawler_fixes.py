import os
import django
import pytest
from decimal import Decimal
from bs4 import BeautifulSoup
from pathlib import Path

from package.parser.sumifuParser import SumifuInvestmentApartmentParser, SumifuKodateParser, SumifuTochiParser
from package.parser.mitsuiParser import MitsuiTochiParser
from package.parser.nomuraParser import NomuraInvestmentApartmentParser
from package.parser.sumai1Parser import Sumai1InvestmentParser
from package.parser.tokyuParser import TokyuKodateParser
from package.parser.totateParser import TotateMansionParser, TotateKodateParser, TotateTochiParser
from package.models.nomura import NomuraInvestmentApartment
from package.models.sumifu import SumifuInvestmentApartment, SumifuKodate, SumifuTochi
from package.models.tokyu import TokyuKodate
from package.models.totate import TotateMansion, TotateKodate, TotateTochi
from package.utils.url_router import UrlRouter

def get_root_repo_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "logs/runs/20261026/error_pages").exists():
            return parent
    return Path("C:/Users/weare/.gemini/antigravity/scratch/realestate_crawler")

ROOT_DIR = get_root_repo_dir()

@pytest.mark.django_db
def test_mitsui_tochi_school_distance_not_parsed_as_road_width():
    # 小学校まで約11300m が roadWidth に入らず、DecimalField 上限違反にならないこと
    html_path = ROOT_DIR / "logs/runs/20261026/error_pages/mitsui_tochi/4b14092c953262f8.html"
    assert html_path.exists(), f"{html_path} must exist"

    with open(html_path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")

    parser = MitsuiTochiParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.rehouse.co.jp/buy/tochi/bkdetail/FD3UYA07/"
    item = parser._parsePropertyDetailPage(item, soup)
    # roadWidth は 50m 超のため弾かれて None または 0 になるはず
    assert item.roadWidth is None or item.roadWidth <= 50
    item.full_clean()

@pytest.mark.django_db
def test_nomura_investment_apartment_empty_current_status():
    # 現況が空でもバリデーションエラーにならないこと
    html_path = ROOT_DIR / "logs/runs/20261026/error_pages/nomura_investment_apartment/89429013a6896e10.html"
    assert html_path.exists(), f"{html_path} must exist"

    with open(html_path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")

    parser = NomuraInvestmentApartmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.nomu.com/pro/detail/RB570565/"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.currentStatus == ""
    item.full_clean()

@pytest.mark.django_db
def test_sumai1_investment_genko_shunyu_fallback():
    # 満室時想定収入がなく現行収入のみの投資物件が正しくパースされバリデーションを通ること
    html_path = ROOT_DIR / "logs/runs/20261026/error_pages/sumai1_investment/7f863b6ab021bb80.html"
    assert html_path.exists(), f"{html_path} must exist"

    with open(html_path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")

    parser = Sumai1InvestmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.sumai1.com/buyers/investor/bukken/buk_Ske260169/"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.annualRent is not None and item.annualRent > 0
    assert item.monthlyRent is not None and item.monthlyRent > 0
    item.full_clean()

@pytest.mark.django_db
def test_sumifu_investment_apartment_chikunengetsu_unknown():
    # 築年月不詳物件の実HTMLパーステスト
    html_path = ROOT_DIR / "logs/runs/20261026/error_pages/sumifu_investment_apartment/0530d1d43bd6d3d7.html"
    assert html_path.exists(), f"{html_path} must exist"

    with open(html_path, "rb") as f:
        raw = f.read()
    text = raw.decode("cp932")
    soup = BeautifulSoup(text, "html.parser")

    parser = SumifuInvestmentApartmentParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.stepon.co.jp/pro/detail_36252127/"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.chikunengetsuStr == "築年月不詳"
    assert item.chikunengetsu is None
    item.full_clean()

@pytest.mark.django_db
def test_sumifu_kodate_and_tochi_empty_chisei():
    # 地勢未記載の sumifu 戸建て・土地がバリデーションを通ること
    html_path_kodate = ROOT_DIR / "logs/runs/20261026/error_pages/sumifu_kodate/078a0dc8074d0cf1.html"
    if html_path_kodate.exists():
        with open(html_path_kodate, "rb") as f:
            soup = BeautifulSoup(f.read().decode("cp932", errors="ignore"), "html.parser")
        parser_k = SumifuKodateParser()
        item_k = parser_k.createEntity()
        item_k.pageUrl = "https://www.stepon.co.jp/kodate/detail_96612119/"
        item_k = parser_k._parsePropertyDetailPage(item_k, soup)
        assert item_k.chisei == ""
        item_k.full_clean()

    html_path_tochi = ROOT_DIR / "logs/runs/20261026/error_pages/sumifu_tochi/1d7a1b9a9ea44292.html"
    if html_path_tochi.exists():
        with open(html_path_tochi, "rb") as f:
            soup = BeautifulSoup(f.read().decode("cp932", errors="ignore"), "html.parser")
        parser_t = SumifuTochiParser()
        item_t = parser_t.createEntity()
        item_t.pageUrl = "https://www.stepon.co.jp/tochi/detail_967I1078/"
        item_t = parser_t._parsePropertyDetailPage(item_t, soup)
        assert item_t.chisei == ""
        item_t.full_clean()

@pytest.mark.django_db
def test_totate_mansion_parser_on_sumikae_html():
    # sumikae.ttfuhan.co.jp の実HTMLが TotateMansionParser で正常にパース・バリデーションできること
    html_path = ROOT_DIR / "logs/runs/20261026/error_pages/tokyu_mansion/065d57f76d517f03.html"
    assert html_path.exists(), f"{html_path} must exist"

    with open(html_path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")

    parser = TotateMansionParser()
    item = parser.createEntity()
    item.pageUrl = "https://sumikae.ttfuhan.co.jp/mansion/H01631442/"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.propertyName != ""
    assert item.price > 0
    item.full_clean()

@pytest.mark.django_db
def test_tokyu_kodate_saikou_empty_pass():
    # 方角・採光なしの戸建て物件がバリデーションを通過すること
    html_path = ROOT_DIR / "logs/runs/20261026/error_pages/tokyu_kodate/b0196049ff493cc1.html"
    assert html_path.exists(), f"{html_path} must exist"

    with open(html_path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")

    parser = TokyuKodateParser()
    item = parser.createEntity()
    item.pageUrl = "https://www.livable.co.jp/kodate/C1226X622/"
    item = parser._parsePropertyDetailPage(item, soup)
    assert item.saikou == ""
    item.full_clean()
