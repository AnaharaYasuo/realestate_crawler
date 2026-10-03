# -*- coding: utf-8 -*-
"""Unit tests for Issue #608: Task distribution optimization and company concurrency limits."""
from package.utils.crawl_jobs import CRAWL_JOBS
from package.utils.task_distribution import distribute_jobs
from package.utils.crawler_scheduler import get_company_concurrency_limit


def test_distribute_jobs_8_tasks_categorization():
    """Verify that 8 tasks are distributed according to Issue #608 specification."""
    # Collect jobs for all 8 tasks
    all_assigned = []
    task_jobs = {}
    for t in range(8):
        assigned = distribute_jobs(CRAWL_JOBS, task_index=t, task_count=8)
        task_jobs[t] = assigned
        all_assigned.extend(assigned)

    # 1. Total jobs count and uniqueness: all CRAWL_JOBS must be covered exactly once
    assert len(all_assigned) == len(CRAWL_JOBS)
    assert set(all_assigned) == set(CRAWL_JOBS)

    # 2. Task 0: Major brokers mansion
    major_5 = {"mitsui", "sumifu", "tokyu", "nomura", "misawa"}
    assert set(task_jobs[0]) == {(c, "mansion") for c in major_5}

    # 3. Task 1: Major brokers kodate
    assert set(task_jobs[1]) == {(c, "kodate") for c in major_5}

    # 4. Task 2: Major brokers tochi
    assert set(task_jobs[2]) == {(c, "tochi") for c in major_5}

    # 5. Task 3: Major and Trust bank investment
    # Major 5 invest_kodate / invest_apartment + smtrc/sumai1/mizuho/odakyu/sumirin investment
    task3_companies = {c for c, _ in task_jobs[3]}
    assert "athome" not in task3_companies
    assert "homes" not in task3_companies
    for c, p in task_jobs[3]:
        assert p in ("invest_kodate", "invest_apartment", "investment")

    # 6. Task 4: Trust residential + Mid/Small/Rail/House makers residential
    for c, p in task_jobs[4]:
        assert c not in major_5
        assert c not in ("athome", "homes")
        assert p in ("mansion", "kodate", "tochi")

    # 7. Task 5: Homes all types
    assert set(task_jobs[5]) == {
        ("homes", "mansion"),
        ("homes", "kodate"),
        ("homes", "tochi"),
        ("homes", "invest_apartment"),
    }

    # 8. Task 6: Athome mansion only
    assert set(task_jobs[6]) == {("athome", "mansion")}

    # 9. Task 7: Athome other types
    assert set(task_jobs[7]) == {
        ("athome", "kodate"),
        ("athome", "tochi"),
        ("athome", "invest_apartment"),
    }


def test_distribute_jobs_fallback_when_not_8():
    """Verify fallback to modulo when task_count != 8."""
    jobs = [("a", "m"), ("b", "m"), ("c", "m"), ("d", "m")]
    t0 = distribute_jobs(jobs, task_index=0, task_count=2)
    t1 = distribute_jobs(jobs, task_index=1, task_count=2)
    assert t0 == [("a", "m"), ("c", "m")]
    assert t1 == [("b", "m"), ("d", "m")]


def test_company_concurrency_limits_relaxed():
    """Verify major broker companies have concurrency limit of 5 to run all types simultaneously."""
    for c in ["mitsui", "sumifu", "tokyu", "nomura", "misawa"]:
        assert get_company_concurrency_limit(c) == 5, f"{c} concurrency limit should be 5"
    assert get_company_concurrency_limit("homes") == 5
    assert get_company_concurrency_limit("athome") == 3
