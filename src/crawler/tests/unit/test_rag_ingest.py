from package.rag_ingest.egov_law import article_to_chunks
from package.rag_ingest.schema import KnowledgeChunk, destination, validate_chunk
from package.rag_ingest.store import group_by_destination, write_local


def _chunk(**kw):
    base = {
        "id": "a", "source_id": "s", "category": "law", "title": "t", "url": "http://x",
        "body_text": "b", "license": "CC BY 4.0", "fetched_at": "2026-01-01"
    }
    base.update(kw)
    return KnowledgeChunk(**base)


def test_valid_goes_to_curated():
    assert destination(_chunk()) == "curated/law"


def test_missing_license_goes_to_quarantine():
    c = _chunk(license="")
    assert "missing license" in validate_chunk(c)
    assert destination(c) == "quarantine"


def test_invalid_category_quarantined():
    assert destination(_chunk(category="blog")) == "quarantine"


def test_group_and_write(tmp_path):
    chunks = [_chunk(), _chunk(id="b", license=""), _chunk(id="c", url="")]
    g = group_by_destination(chunks)
    assert set(g) == {"curated/law", "quarantine"}
    assert chunks[1].license == "未確認(規約確認待ち)" and chunks[1].confidence <= 0.5
    assert len(write_local(chunks, "s", str(tmp_path))) == 2


def test_article_chunking_by_article():
    doc = {"law_full_text": {"tag": "Law", "attr": {}, "children": [
        {"tag": "Article", "attr": {"Num": "1"}, "children": [
            {"tag": "ArticleCaption", "attr": {}, "children": ["（目的）"]},
            {"tag": "ArticleTitle", "attr": {}, "children": ["第一条"]},
            {"tag": "Paragraph", "attr": {"Num": "1"}, "children": ["本文一"]}]},
        {"tag": "Article", "attr": {"Num": "2"}, "children": [
            {"tag": "Paragraph", "attr": {"Num": "1"}, "children": ["本文二"]}]}]}}
    cs = article_to_chunks("L1", "テスト法", doc, "2026-01-01")
    assert [c.id for c in cs] == ["law_L1_1", "law_L1_2"]
    assert "目的" in cs[0].title and cs[0].license

def test_practitioner_empty_license_defaults_internal_but_missing_url_quarantined(tmp_path):
    import json
    from package.rag_ingest.practitioner import load_insights
    p = tmp_path / "n.jsonl"
    rows = [{"text": "A", "source_url": "u", "license": "own", "speaker_role": "仲介"},
            {"text": "B", "source_url": "u"},
            {"text": "C"}]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    cs = load_insights(str(p), "notes")
    assert [destination(c) for c in cs] == ["curated/practitioner_insight", "curated/practitioner_insight", "quarantine"]
    assert cs[0].kind == "judgement" and cs[0].summary_only

def test_reiki_base_html_parsing():
    from package.rag_ingest.local_ordinance import parse_reiki_base_html
    sample_html = """
    <html><body>
    <p class="num">第1条 （目的）この条例は、テスト目的のために制定する。</p>
    <p>2 この条例においてテストとは検証をいう。</p>
    <p class="num">第2条 （制限）高さ10メートルを超える建築物は制限する。</p>
    </body></html>
    """
    chunks = parse_reiki_base_html(sample_html, "sample01", "テスト条例", "http://example.com", "test_city", "2026-01-01")
    assert len(chunks) == 2
    assert chunks[0].id == "ordinance_test_city_sample01_第1条"
    assert chunks[0].category == "law"
    assert "目的" in chunks[0].body_text
    assert chunks[1].id == "ordinance_test_city_sample01_第2条"

def test_chiba_ordinance_collector():
    from package.rag_ingest.local_ordinance import parse_reiki_base_html
    sample_html = """
    <html><body>
    <p class="num">第1条 （目的）この条例は千葉市における地区計画の制限を定める。</p>
    <p>2 この規則において地区計画とは法第68条の2の計画をいう。</p>
    </body></html>
    """
    chunks = parse_reiki_base_html(sample_html, "sample_chiba", "千葉市地区計画条例", "http://example.com", "chiba_city", "2026-01-01")
    assert len(chunks) == 1
    assert chunks[0].id == "ordinance_chiba_city_sample_chiba_第1条"
    assert chunks[0].region == "chiba_city"

def test_legal_rag_search(monkeypatch):
    from package.ml import legal_rag
    # テスト環境（ローカルファイルやGCS接続なし環境）向けにダミーデータを注入
    dummy_laws = [
        {
            "id": "ordinance_kanagawa_yokohama_g202RG00001312_第1条",
            "title": "横浜市斜面地における地下室建築物の建築及び開発の制限等に関する条例",
            "body_text": "第1条 この条例は、斜面地における地下室建築物の建築及び開発の制限について定める。",
            "region": "kanagawa_yokohama",
        },
        {
            "id": "law_egov_325AC0000000201_第1条",
            "title": "建築基準法",
            "body_text": "第1条 この法律は、建築物の敷地、構造、設備及び用途に関する最低の基準を定めて...",
            "region": "national",
        },
    ]
    monkeypatch.setattr(legal_rag, "_load_laws_from_local", lambda: dummy_laws)
    monkeypatch.setattr(legal_rag, "_load_laws_from_gcs", list)
    legal_rag._LAW_CACHE = None

    res = legal_rag.search_legal_knowledge("横浜市 がけ地 斜面地 地下室", region_key="yokohama", top_k=2)
    assert len(res) > 0
    assert any("横浜" in r.get("title", "") for r in res)