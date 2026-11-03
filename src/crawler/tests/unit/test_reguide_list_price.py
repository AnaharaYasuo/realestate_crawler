import pytest
from bs4 import BeautifulSoup
from package.parser.reguideParser import ReguideInvestmentParser


@pytest.mark.asyncio
async def test_reguide_parse_root_page_extracts_url_and_price():
    parser = ReguideInvestmentParser()

    sample_html = """
    <ul id="result_list">
        <li>
            <div class="body">
                <div class="name">
                    <a class="name" href="/investment/421487/">
                        <span class="a_text">テスト物件1</span>
                    </a>
                </div>
                <div class="info">
                    <div class="estate_info">
                        <table class="price">
                            <tr>
                                <th>価格</th>
                                <th>利回り</th>
                            </tr>
                            <tr>
                                <td>3億5,800万円</td>
                                <td>4.55%</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </li>
        <li>
            <div class="body">
                <div class="name">
                    <a class="name" href="/investment/421488/">
                        <span class="a_text">テスト物件2</span>
                    </a>
                </div>
                <div class="info">
                    <div class="estate_info">
                        <table class="price">
                            <tr>
                                <th>価格</th>
                                <th>利回り</th>
                            </tr>
                            <tr>
                                <td>1,980万円</td>
                                <td>6.20%</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </li>
        <li>
            <!-- 利回りが先、価格が後のカード -->
            <div class="body">
                <div class="name">
                    <a class="name" href="/investment/421490/">
                        <span class="a_text">テスト物件4（利回り先行）</span>
                    </a>
                </div>
                <div class="info">
                    <div class="estate_info">
                        <table class="price">
                            <tr>
                                <th>利回り</th>
                                <th>価格</th>
                            </tr>
                            <tr>
                                <td>5.20%</td>
                                <td>5,000万円</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </li>
        <li>
            <!-- 物件カードだが価格が「相談」または未記載 -->
            <div class="body">
                <div class="name">
                    <a class="name" href="/investment/421489/">
                        <span class="a_text">テスト物件3（価格未定）</span>
                    </a>
                </div>
                <div class="info">
                    <div class="estate_info">
                        <table class="price">
                            <tr>
                                <th>価格</th>
                            </tr>
                            <tr>
                                <td>価格応相談</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </li>
    </ul>
    """

    soup = BeautifulSoup(sample_html, "html.parser")
    items = [item async for item in parser.parseRootPage(soup)]

    assert len(items) == 4

    # Item 1
    assert items[0].url == "https://www.re-guide.jp/investment/421487/"
    assert items[0].price == 358000000

    # Item 2
    assert items[1].url == "https://www.re-guide.jp/investment/421488/"
    assert items[1].price == 19800000

    # Item 3 (利回り先行カード)
    assert items[2].url == "https://www.re-guide.jp/investment/421490/"
    assert items[2].price == 50000000

    # Item 4: 価格解析不可時は None でフォールバック
    assert items[3].url == "https://www.re-guide.jp/investment/421489/"
    assert items[3].price is None
