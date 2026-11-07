import pytest
from bs4 import BeautifulSoup
from package.parser.sumirinParser import SumirinTochiParser

def test_sumirin_address_excludes_shop_info():
    html = """
    <html>
      <body>
        <main class="l-body-main">
          <section class="overview">
            <dl class="list">
              <dt>所在地</dt>
              <dd>大阪府富田林市錦織南２丁目</dd>
              <dt>価格</dt>
              <dd>200万円</dd>
            </dl>
          </section>
          <section>
            <div class="uq-shp-blk-pt2">
              <div class="dtl">
                <dl>
                  <dt>所在地</dt>
                  <dd>〒564-0052大阪府吹田市広芝町９−１７ M's COMFORT ESAKA１０１ ２０１</dd>
                  <dt>電話番号</dt>
                  <dd>0120-144-063</dd>
                </dl>
              </div>
            </div>
          </section>
        </main>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = SumirinTochiParser()
    address = parser._parseAddress(soup)
    assert address == "大阪府富田林市錦織南２丁目"
    assert "吹田市" not in address
