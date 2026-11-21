import pytest
from bs4 import BeautifulSoup

from package.models.misawa import MisawaMansion, MisawaTochi
from package.parser.baseParser import ListingEndedException
from package.parser.misawaParser import MisawaMansionParser, MisawaTochiParser


@pytest.mark.parametrize(
    "parser_cls,model_cls",
    [
        (MisawaMansionParser, MisawaMansion),
        (MisawaTochiParser, MisawaTochi),
    ],
)
def test_misawa_raises_listing_ended_on_stopped_message(parser_cls, model_cls):
    html = """
    <html>
      <head><title>物件詳細 | 不動産検索 | ミサワホーム不動産株式会社</title></head>
      <body>
        <div class="main">
          <h1>【売地】青梅市裏宿町土地 物件番号：9535695</h1>
          <p>現在、こちらの物件は掲載を停止しております。</p>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = parser_cls()
    with pytest.raises(ListingEndedException, match="Misawa listing ended"):
        parser._parsePropertyDetailPage(model_cls(), soup)
