# -*- coding: utf-8 -*-
"""
Cloud Run Jobs タスクアレイ分散アルゴリズムの単体テスト
"""
import pytest
from package.utils.task_distribution import distribute_jobs, get_task_config


def test_get_task_config_defaults(monkeypatch):
    monkeypatch.delenv("CLOUD_RUN_TASK_INDEX", raising=False)
    monkeypatch.delenv("CLOUD_RUN_TASK_COUNT", raising=False)
    
    idx, count = get_task_config()
    assert idx is None
    assert count == 1


def test_get_task_config_from_env(monkeypatch):
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "3")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "8")
    
    idx, count = get_task_config()
    assert idx == 3
    assert count == 8


def test_distribute_jobs_single_task():
    jobs = [("mitsui", "mansion"), ("sumifu", "kodate"), ("tokyu", "tochi")]
    
    # task_count = 1 or index is None: 全件が割り当てられる
    assert distribute_jobs(jobs, task_index=None, task_count=1) == jobs
    assert distribute_jobs(jobs, task_index=0, task_count=1) == jobs


def test_distribute_jobs_modulo_split():
    # 10個のジョブを4タスクに分割
    jobs = [(f"company_{i}", "mansion") for i in range(10)]
    
    task_0_jobs = distribute_jobs(jobs, task_index=0, task_count=4)
    task_1_jobs = distribute_jobs(jobs, task_index=1, task_count=4)
    task_2_jobs = distribute_jobs(jobs, task_index=2, task_count=4)
    task_3_jobs = distribute_jobs(jobs, task_index=3, task_count=4)
    
    # 各タスクの割り当て確認
    assert task_0_jobs == [jobs[0], jobs[4], jobs[8]]
    assert task_1_jobs == [jobs[1], jobs[5], jobs[9]]
    assert task_2_jobs == [jobs[2], jobs[6]]
    assert task_3_jobs == [jobs[3], jobs[7]]
    
    # 重複がなく、全ジョブを網羅していることを検証
    all_assigned = task_0_jobs + task_1_jobs + task_2_jobs + task_3_jobs
    assert len(all_assigned) == len(jobs)
    assert set(all_assigned) == set(jobs)


def test_distribute_jobs_out_of_range():
    jobs = [("mitsui", "mansion")]
    with pytest.raises(ValueError):
        distribute_jobs(jobs, task_index=4, task_count=4)
    with pytest.raises(ValueError):
        distribute_jobs(jobs, task_index=-1, task_count=4)
