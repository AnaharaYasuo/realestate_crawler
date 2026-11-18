import pytest
from bs4 import BeautifulSoup
from package.parser.reguideParser import ReguideInvestmentParser
from package.models.reguide import ReguideInvestment

def test_reguide_maybe_switch_parser_investment_compatibility():
    """投資カテゴリ間（investment と apartment）の等価性により、IncompatiblePropertyTypeException を発生させず自身を維持するテスト"""
    parser = ReguideInvestmentParser()
    item = parser.createEntity()
    
    html = """
    <html>
    <head><title>ときわ台★一棟売アパート 一棟売りアパート | 不動産投資なら RE-Guide収益物件</title></head>
    <body>
        <h1>ときわ台★一棟売アパート 一棟売りアパート</h1>
        <table>
            <tr><th>価格(税込)</th><td>4,600万円</td></tr>
            <tr><th>建物構造</th><td>木造</td></tr>
        </table>
    </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    specs = {"価格(税込)": "4,600万円", "建物構造": "木造"}
    url = "https://www.re-guide.jp/investment/421799/"
    
    target_parser, target_item = parser._maybe_switch_parser(
        url=url,
        title="ときわ台★一棟売アパート 一棟売りアパート | 不動産投資なら RE-Guide収益物件",
        soup=soup,
        specs=specs,
        item=item,
    )
    
    assert target_parser is parser
    assert isinstance(target_item, ReguideInvestment)
