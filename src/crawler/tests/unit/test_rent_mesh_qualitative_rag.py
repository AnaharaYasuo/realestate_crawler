import pytest
from unittest.mock import MagicMock, patch
from package.ml.rent_mesh_rag import (
    search_rent_mesh_knowledge,
    format_rent_mesh_context,
    clear_rent_mesh_cache,
)
from package.ml.report_generator import _build_rag_prompt


SAMPLE_CHUNKS = [
    {
        "id": "rent_mesh_homes_tokyo_meguro_nakameguro_202611",
        "source_id": "homes_market",
        "category": "statistics",
        "kind": "fact",
        "title": "東京都目黒区中目黒・中目黒駅周辺の賃料相場と需給データ",
        "region": "東京都目黒区中目黒",
        "metadata": {
            "prefecture": "東京都",
            "city": "目黒区",
            "station": "中目黒",
        },
        "essence": "中目黒駅周辺のワンルーム相場は10.8万円。需給は極めて引き締まっており空室期間が短い。",
        "body_text": "| 間取り | 相場 |\n| --- | --- |\n| ワンルーム | 10.8万円 |",
    },
    {
        "id": "rent_mesh_homes_tokyo_shinjuku_202611",
        "source_id": "homes_market",
        "category": "statistics",
        "kind": "fact",
        "title": "東京都新宿区の賃料相場データ",
        "region": "東京都新宿区",
        "metadata": {
            "prefecture": "東京都",
            "city": "新宿区",
            "station": "新宿",
        },
        "essence": "新宿区全体のワンルーム相場は9.5万円。単身者需要が旺盛。",
        "body_text": "| 間取り | 相場 |\n| --- | --- |\n| ワンルーム | 9.5万円 |",
    },
]


@pytest.fixture(autouse=True)
def setup_test():
    clear_rent_mesh_cache()
    yield
    clear_rent_mesh_cache()


def test_search_rent_mesh_exact_station():
    with patch("package.ml.rent_mesh_rag.load_rent_mesh_knowledge_base", return_value=SAMPLE_CHUNKS):
        matches = search_rent_mesh_knowledge(
            prefecture="東京都",
            city="目黒区",
            station="中目黒",
            top_k=2
        )
        assert len(matches) > 0
        assert matches[0]["metadata"]["station"] == "中目黒"
        assert "中目黒" in matches[0]["title"]


def test_format_rent_mesh_context():
    formatted = format_rent_mesh_context(SAMPLE_CHUNKS[:1])
    assert "【周辺賃料相場・需給メッシュ（統計RAG）】" in formatted
    assert "中目黒駅周辺のワンルーム相場は10.8万円" in formatted


def test_build_rag_prompt_injects_rent_mesh():
    eval_rec = MagicMock(estimated_sekisan_price=1000, cash_flow=100, dscr=1.5)
    prop = MagicMock(
        tochiMenseki="50",
        tatemonoMenseki="80",
        chikunengetsuStr="2010年1月",
        kouzou="RC",
        setsudou="公道",
        pageUrl="https://example.com/prop1",
    )

    rent_mesh_items = [SAMPLE_CHUNKS[0]]
    prompt = _build_rag_prompt(
        eval_rec=eval_rec,
        prop=prop,
        ptype_jp="区分マンション",
        asking_price_man=3000,
        address="東京都目黒区中目黒1-1",
        access="東急東横線 中目黒駅 徒歩3分",
        matched_kb=[],
        far_slack=10.0,
        rent_mesh_items=rent_mesh_items,
    )

    assert "【周辺賃料相場・需給メッシュ（統計RAG）】" in prompt
    assert "中目黒駅周辺のワンルーム相場は10.8万円" in prompt
