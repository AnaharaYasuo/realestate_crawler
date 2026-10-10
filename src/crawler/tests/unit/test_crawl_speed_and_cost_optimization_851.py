# -*- coding: utf-8 -*-
"""
Issue #851: クローリング高速化およびCloud Runコスト最適化のユニットテスト
"""
import os
from unittest.mock import patch
from bs4 import BeautifulSoup

from package.parser.daikyoParser import DaikyoMansionParser
from package.api.differential import ListItem
from package.utils.task_distribution import distribute_jobs, _assign_8_task_index
from package.api.adaptive_concurrency import AdaptiveConcurrencyController


def test_daikyo_extract_detail_items_with_price():
    """大京穴吹パーサーが一覧からURLと価格を抽出しListItemとして返すこと"""
    html = """
    <div class="result-list__item">
        <a href="/buy/detail/MHF12345/">グランドメゾン</a>
        <div class="price">4,580万円</div>
    </div>
    <div class="result-list__item">
        <a href="/buy/detail/MHF67890/">ライオンズマンション</a>
        <div class="price">3,200万円</div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    parser = DaikyoMansionParser()
    detail_links = set()
    items = list(parser._extract_detail_links(soup, detail_links))
    
    assert len(items) == 2
    assert isinstance(items[0], ListItem)
    assert items[0].url == "https://www.daikyo-anabuki.co.jp/buy/detail/MHF12345/"
    assert items[0].price == 45800000
    assert items[1].url == "https://www.daikyo-anabuki.co.jp/buy/detail/MHF67890/"
    assert items[1].price == 32000000


def test_task_distribution_daikyo_rebalancing():
    """大京の重いタスクがTask 0/1に再配置されTask 4のロングテールが解消されること"""
    # daikyo mansion should go to Task 0 (大手mansion枠)
    assert _assign_8_task_index("daikyo", "mansion") == 0
    # daikyo kodate and tochi should go to Task 1
    assert _assign_8_task_index("daikyo", "kodate") == 1
    assert _assign_8_task_index("daikyo", "tochi") == 1
    
    # Task 4 に大京が含まれないこと
    jobs = [
        ("daikyo", "mansion"),
        ("daikyo", "kodate"),
        ("daikyo", "tochi"),
        ("sekisui", "mansion"),
    ]
    t0 = distribute_jobs(jobs, task_index=0, task_count=8)
    t1 = distribute_jobs(jobs, task_index=1, task_count=8)
    t4 = distribute_jobs(jobs, task_index=4, task_count=8)
    
    assert ("daikyo", "mansion") in t0
    assert ("daikyo", "kodate") in t1
    assert ("daikyo", "tochi") in t1
    assert ("daikyo", "mansion") not in t4
    assert ("sekisui", "mansion") in t4


def test_adaptive_concurrency_higher_default():
    """AdaptiveConcurrencyControllerがアクティブジョブ1の際に高並行度(最大15)を返すこと"""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CLOUD_DETAIL_CONCURRENCY", None)
        concurrency = AdaptiveConcurrencyController.calculate_detail_concurrency(active_jobs=1)
        assert concurrency >= 10


def test_differential_should_fetch_item_price_match_skips():
    """URLと価格が一致している既存レコードは詳細フェッチをスキップすること"""
    from package.api.differential import _should_fetch_item
    from django.utils import timezone
    now = timezone.now()

    item = ListItem(url="https://example.com/item1", price=35000000)
    record_same_price = {
        "price": 35000000,
        "updateDateTime": now,
    }
    record_diff_price = {
        "price": 38000000,
        "updateDateTime": now,
    }

    # 価格一致 -> スキップ (False)
    assert _should_fetch_item(item, record_same_price, now, ttl_days=30) is False
    # 価格変動 -> フェッチ必要 (True)
    assert _should_fetch_item(item, record_diff_price, now, ttl_days=30) is True
