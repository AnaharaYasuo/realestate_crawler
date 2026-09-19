# -*- coding: utf-8 -*-
"""クローラー並行度スケジューラーの単体テスト (TDD)

要件:
- 取扱物件数に応じた階層的同時プロセス数制御:
  - homes: 5本 (超大規模ポータル HTTP)
  - athome: 2本 (超大規模ポータル Playwright / メモリ保護)
  - 大手5社 (mitsui, sumifu, tokyu, nomura, misawa): 2本
  - 中小・電鉄・ハウスメーカー (sekisui, daiwa, etc.): 1本 (同一会社内完全直列)
- 会社間は全社一斉に並行スタート可能
"""
from package.utils.crawler_scheduler import (
    get_company_concurrency_limit,
    select_next_job,
)


def test_company_concurrency_limits_mapping():
    """会社別の同時プロセス数上限マッピングを検証"""
    # 超大規模ポータル
    assert get_company_concurrency_limit("homes") == 5
    assert get_company_concurrency_limit("athome") == 3

    # 大手5社
    for major in ["mitsui", "sumifu", "tokyu", "nomura", "misawa"]:
        assert get_company_concurrency_limit(major) == 2, f"{major} should have concurrency limit 2"

    # 中小・電鉄・ハウスメーカー系列 (デフォルト 1本)
    for small in ["sekisui", "daiwa", "afr", "totate", "odakyu", "sumirin", "heim", "rearie", "keio", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "smtrc", "sumai1", "mizuho"]:
        assert get_company_concurrency_limit(small) == 1, f"{small} should have concurrency limit 1"

    # 大文字小文字の区別なし
    assert get_company_concurrency_limit("HOMES") == 5
    assert get_company_concurrency_limit("Mitsui") == 2
    assert get_company_concurrency_limit("Sekisui") == 1


def test_select_next_job_respects_limits():
    """スケジューラーが各社の上限枠に従ってジョブを選択することを検証"""
    job_queue = [
        ("mitsui", "mansion"),
        ("mitsui", "kodate"),
        ("mitsui", "tochi"),
        ("sekisui", "mansion"),
        ("sekisui", "kodate"),
        ("homes", "mansion"),
        ("homes", "kodate"),
    ]

    # ケース 1: 最初は何のプロセスも動いていない -> 先頭の mitsui-mansion が選ばれる
    active_counts = {}
    idx, job = select_next_job(job_queue, active_counts)
    assert idx == 0
    assert job == ("mitsui", "mansion")

    # ケース 2: mitsui が 1 プロセス実行中 -> mitsui は上限2なので、次の mitsui-kodate も選ばれる
    active_counts = {"mitsui": 1}
    idx, job = select_next_job(job_queue, active_counts)
    assert idx == 0
    assert job == ("mitsui", "mansion")

    # ケース 3: mitsui が 2 プロセス実行中 (上限到達) -> mitsui のジョブはスキップされ、sekisui-mansion が選ばれる
    active_counts = {"mitsui": 2}
    idx, job = select_next_job(job_queue, active_counts)
    assert idx == 3
    assert job == ("sekisui", "mansion")

    # ケース 4: sekisui が 1 プロセス実行中 (上限1到達) -> sekisui もスキップされ、homes-mansion が選ばれる
    active_counts = {"mitsui": 2, "sekisui": 1}
    idx, job = select_next_job(job_queue, active_counts)
    assert idx == 5
    assert job == ("homes", "mansion")

    # ケース 5: homes が 4 プロセス実行中 (上限5未満) -> homes-mansion が選ばれる
    active_counts = {"mitsui": 2, "sekisui": 1, "homes": 4}
    idx, job = select_next_job(job_queue, active_counts)
    assert idx == 5
    assert job == ("homes", "mansion")

    # ケース 6: 全ての会社が上限到達 -> None が返る (待機)
    active_counts = {"mitsui": 2, "sekisui": 1, "homes": 5}
    res = select_next_job(job_queue, active_counts)
    assert res is None
