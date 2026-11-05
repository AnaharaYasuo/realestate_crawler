from package.rag_ingest.egov_law import article_to_chunks
from package.rag_ingest.schema import KnowledgeChunk, destination, validate_chunk
from package.rag_ingest.store import group_by_destination, write_local


def _chunk(**kw):
    base = dict(id="a", source_id="s", category="law", title="t", url="http://x", body_text="b",
                license="CC BY 4.0", fetched_at="2026-01-01")
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
    chunks = [_chunk(), _chunk(id="b", license="")]
    assert set(group_by_destination(chunks)) == {"curated/law", "quarantine"}
    paths = write_local(chunks, "s", str(tmp_path))
    assert len(paths) == 2


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