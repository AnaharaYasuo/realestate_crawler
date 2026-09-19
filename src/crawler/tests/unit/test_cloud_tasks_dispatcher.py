# -*- coding: utf-8 -*-
"""
Cloud Tasks ディスパッチャーの単体テスト
"""
from package.utils.cloud_tasks_dispatcher import build_task_payload, generate_crawl_tasks


def test_build_task_payload():
    payload = build_task_payload("mitsui", "mansion", "2026-09-19")
    assert payload == {
        "company": "mitsui",
        "property_type": "mansion",
        "execution_date": "2026-09-19"
    }


def test_generate_crawl_tasks_smallest_site_first():
    jobs = [("athome", "mansion"), ("mitsui", "mansion"), ("homes", "kodate")]
    tasks = generate_crawl_tasks(jobs, "2026-09-19")
    
    assert len(tasks) == 3
    assert tasks[0]["company"] == "athome"
    assert tasks[1]["company"] == "mitsui"
    assert tasks[2]["company"] == "homes"
