# -*- coding: utf-8 -*-
"""
Issue #716 バルクML評価ストリーミングおよび責務分割の単体テスト
"""

from unittest.mock import MagicMock
from package.ml.evaluation.targets import iter_unprocessed_chunks
from package.ml.evaluation.record_builder import (
    resolve_company_and_type,
)
from package.ml.evaluation.runner import evaluate_single_model


def test_resolve_company_and_type():
    assert resolve_company_and_type("MitsuiMansion") == ("mitsui", "mansion")
    assert resolve_company_and_type("SumifuKodate") == ("sumifu", "kodate")
    assert resolve_company_and_type("TokyuTochi") == ("tokyu", "tochi")


def test_iter_unprocessed_chunks_memory_streaming():
    """未評価物件の全件 list 化が無く、同時にメモリ保持する物件数が chunk_size 以下であることの検証"""
    mock_items = []
    for i in range(25):
        m = MagicMock()
        m.pk = i + 1
        m.pageUrl = f"https://example.com/property/{i + 1}"
        mock_items.append(m)

    mock_model = MagicMock()
    mock_model.objects.all.return_value.order_by.return_value.iterator.return_value = iter(mock_items)

    chunk_size = 10
    chunks = list(iter_unprocessed_chunks(
        model=mock_model,
        existing_eval_map={},
        force=False,
        limit=None,
        chunk_size=chunk_size,
    ))

    # 25件を chunk_size=10 で回すと 10, 10, 5 の 3 チャンクになること
    assert len(chunks) == 3
    assert len(chunks[0][0]) == 10
    assert len(chunks[1][0]) == 10
    assert len(chunks[2][0]) == 5

    # 全チャンクで chunk_size を超えていないことを検証
    for c, _ in chunks:
        assert len(c) <= chunk_size


def test_iter_unprocessed_chunks_skip_logic():
    """公開終了物件および評価済み物件が適切にスキップされることの検証"""
    item1 = MagicMock(pk=1, pageUrl="https://example.com/1")
    item2 = MagicMock(pk=2, pageUrl="https://example.com/2")
    item3 = MagicMock(pk=3, pageUrl="https://example.com/3")

    existing_eval_map = {
        # 公開終了
        "https://example.com/1": MagicMock(is_published=False, needs_recrawl=False, first_stage_predicted_price=None),
        # 評価済み
        "https://example.com/2": MagicMock(is_published=True, needs_recrawl=False, first_stage_predicted_price=5000.0),
    }

    mock_model = MagicMock()
    mock_model.objects.all.return_value.order_by.return_value.iterator.return_value = iter([item1, item2, item3])

    chunks = list(iter_unprocessed_chunks(
        model=mock_model,
        existing_eval_map=existing_eval_map,
        force=False,
        chunk_size=10,
    ))

    assert len(chunks) == 1
    chunk_items, skipped = chunks[0]
    assert len(chunk_items) == 1
    assert chunk_items[0].pageUrl == "https://example.com/3"
    assert skipped == 2


def test_evaluate_single_model_streaming_orchestration(monkeypatch):
    """単一モデルのストリーミング評価で bulk_predict と save_chunk がチャンク単位で呼ばれること"""
    item1 = MagicMock(pk=1, pageUrl="https://example.com/item1")
    item2 = MagicMock(pk=2, pageUrl="https://example.com/item2")

    mock_model = MagicMock()
    mock_model.__name__ = "MitsuiMansion"
    mock_model.objects.all.return_value.order_by.return_value.iterator.return_value = iter([item1, item2])

    monkeypatch.setattr("package.ml.evaluation.runner.bulk_predict_first_stage", lambda chunk: [5000.0] * len(chunk))

    saved_calls = []

    def fake_save_chunk(chunk, predicted_prices, existing_eval_map, company, property_type, batch_size):
        saved_calls.append(len(chunk))
        return len(chunk), 0

    monkeypatch.setattr("package.ml.evaluation.runner.save_chunk", fake_save_chunk)

    evaluated_cnt, skipped_cnt, _passed_cnt, _dup_cnt = evaluate_single_model(
        model=mock_model,
        existing_eval_map={},
        force=False,
        limit_per_model=None,
        batch_size=1,
    )

    assert evaluated_cnt == 2
    assert skipped_cnt == 0
    assert len(saved_calls) == 2  # batch_size=1 なので2回チャンク保存された
