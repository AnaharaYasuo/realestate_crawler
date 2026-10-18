# -*- coding: utf-8 -*-
"""
Issue #980: 8タスク分散平準化および集約レポート母数適正化のユニットテスト
"""
from package.utils.crawl_jobs import CRAWL_JOBS
from package.utils.task_distribution import _assign_8_task_index
from package.utils.pipeline_coordinator import aggregate_task_array_reports


def test_8_task_distribution_balanced_job_counts():
    """全104ジョブが8タスクに平準化されて配分され、極端な偏り（Task 4に60件等）がないこと"""
    task_map = {i: [] for i in range(8)}
    for company, ptype in CRAWL_JOBS:
        idx = _assign_8_task_index(company.lower(), ptype.lower())
        task_map[idx].append((company, ptype))

    # 全ジョブが漏れなく重複なく8タスクのいずれかに配分されていること
    total_assigned = sum(len(jobs) for jobs in task_map.values())
    assert total_assigned == len(CRAWL_JOBS)
    assert total_assigned == 104

    # 最大タスクでも30件未満であること（従来の60件から大幅平準化）
    max_jobs_in_task = max(len(jobs) for jobs in task_map.values())
    assert max_jobs_in_task <= 30

    # 各タスクの件数範囲チェック (4〜26件)
    for t_idx, jobs in task_map.items():
        assert len(jobs) >= 4, f"Task {t_idx} has too few jobs ({len(jobs)})"
        assert len(jobs) <= 30, f"Task {t_idx} has too many jobs ({len(jobs)})"


def test_8_task_distribution_specific_category_routing():
    """各社・各物件種別が意図したタスクへルーティングされること"""
    # Task 0: 大手5社 mansion + daikyo mansion
    assert _assign_8_task_index("mitsui", "mansion") == 0
    assert _assign_8_task_index("daikyo", "mansion") == 0

    # Task 1: 大手5社 kodate + daikyo kodate / tochi
    assert _assign_8_task_index("sumifu", "kodate") == 1
    assert _assign_8_task_index("daikyo", "kodate") == 1
    assert _assign_8_task_index("daikyo", "tochi") == 1

    # Task 2: 大手5社 tochi + 信託3社居住用全般
    assert _assign_8_task_index("tokyu", "tochi") == 2
    assert _assign_8_task_index("smtrc", "mansion") == 2
    assert _assign_8_task_index("sumai1", "kodate") == 2
    assert _assign_8_task_index("mizuho", "tochi") == 2

    # Task 3: 投資用・事業用
    assert _assign_8_task_index("mitsui", "invest_kodate") == 3
    assert _assign_8_task_index("smtrc", "investment") == 3
    assert _assign_8_task_index("reguide", "investment") == 3
    assert _assign_8_task_index("kenbiya", "invest_apartment") == 3

    # Task 4: 電鉄・ハウスメーカー系 kodate & tochi
    assert _assign_8_task_index("sekisui", "kodate") == 4
    assert _assign_8_task_index("sekisui", "tochi") == 4
    assert _assign_8_task_index("odakyu", "kodate") == 4

    # Task 5: homes 全種別
    assert _assign_8_task_index("homes", "mansion") == 5
    assert _assign_8_task_index("homes", "invest_apartment") == 5

    # Task 6: athome mansion + 中堅仲介全種別
    assert _assign_8_task_index("athome", "mansion") == 6
    assert _assign_8_task_index("kenbiya", "mansion") == 6
    assert _assign_8_task_index("ietan", "tochi") == 6
    assert _assign_8_task_index("toho", "kodate") == 6

    # Task 7: athome その他 + 電鉄・ハウスメーカー系 mansion
    assert _assign_8_task_index("athome", "kodate") == 7
    assert _assign_8_task_index("athome", "tochi") == 7
    assert _assign_8_task_index("athome", "invest_apartment") == 7
    assert _assign_8_task_index("sekisui", "mansion") == 7
    assert _assign_8_task_index("odakyu", "mansion") == 7


def test_aggregate_task_array_reports_default_total_jobs():
    """aggregate_task_array_reports の既定 total_jobs が 104 (len(CRAWL_JOBS)) となること"""
    task_0 = {
        "task_index": 0,
        "status": "COMPLETED",
        "results_json": [
            {"company": "mitsui", "property_type": "mansion", "status": "success"},
        ],
    }
    agg = aggregate_task_array_reports([task_0])
    assert agg["total_jobs"] == len(CRAWL_JOBS)
    assert agg["total_jobs"] == 104
    assert agg["executed_jobs"] == 1
    assert agg["missing_jobs"] == 103
