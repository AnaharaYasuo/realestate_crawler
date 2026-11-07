import pytest
from package.rag_ingest.rent_mesh_extractor import (
    RentMeshChunk,
    MeshHtmlToMarkdownExtractor,
    KenbiyaBlockedException,
)

SAMPLE_HOMES_HTML = """
<!DOCTYPE html>
<html>
<head><title>中目黒駅の家賃相場【LIFULL HOME'S】</title></head>
<body>
<nav><a href="/">ホーム</a></nav>
<div class="header">広告バナー</div>
<main>
  <h1>中目黒駅の家賃相場情報</h1>
  <p class="lead">中目黒駅（東京都目黒区）の家賃相場情報です。駅徒歩分数や間取りごとの賃料水準と市場動向を掲載しています。</p>
  
  <section class="price-section">
    <h2>間取り別 家賃相場</h2>
    <div class="table-wrapper">
      <table class="price-table">
        <thead>
          <tr><th>間取り</th><th>マンション相場</th><th>アパート相場</th></tr>
        </thead>
        <tbody>
          <tr><td>ワンルーム</td><td>10.8万円</td><td>8.9万円</td></tr>
          <tr><td>1K・1DK</td><td>11.5万円</td><td>9.4万円</td></tr>
          <tr><td>1LDK・2K・2DK</td><td>19.8万円</td><td>15.2万円</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <article class="walk-section">
    <h2>駅徒歩分数別の相場傾向</h2>
    <div class="walk-desc">
      徒歩5分以内の物件は単身層・DINKS層の需要が極めて高く、徒歩10分超と比べて賃料維持率が約15%高い傾向にあります。
    </div>
  </article>
</main>
<footer><p>Copyright 2026</p></footer>
</body>
</html>
"""

def test_kenbiya_exclusion_guard():
    extractor = MeshHtmlToMarkdownExtractor()
    with pytest.raises(KenbiyaBlockedException, match="Kenbiya access is strictly prohibited"):
        extractor.validate_url("https://www.kenbiya.com/price/tokyo/")

    with pytest.raises(KenbiyaBlockedException, match="Kenbiya access is strictly prohibited"):
        extractor.validate_url("https://www.kenbiya.com./price/tokyo/")


def test_extract_markdown_and_chunk():
    extractor = MeshHtmlToMarkdownExtractor()
    chunk = extractor.extract(
        url="https://www.homes.co.jp/chintai/tokyo/nakameguro-st/price/",
        html_content=SAMPLE_HOMES_HTML,
        prefecture="東京都",
        city="目黒区",
        station="中目黒",
        source_id="homes_market"
    )
    
    assert isinstance(chunk, RentMeshChunk)
    assert chunk.source_id == "homes_market"
    assert chunk.category == "statistics"
    assert chunk.kind == "fact"
    assert "中目黒" in chunk.title
    assert "ワンルーム" in chunk.body_text
    assert "10.8万円" in chunk.body_text
    assert "広告バナー" not in chunk.body_text
    assert "Copyright" not in chunk.body_text
    assert chunk.metadata["prefecture"] == "東京都"
    assert chunk.metadata["city"] == "目黒区"
    assert chunk.metadata["station"] == "中目黒"
    assert chunk.valid_to > chunk.valid_from
