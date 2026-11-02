import pytest
from package.utils.container_sizing import calculate_container_recommendations


def test_calculate_container_recommendations_optimal():
    rec = calculate_container_recommendations(
        cpu_peak_percent=75.0,
        mem_max_mb=2100.0,
        current_task_count=4,
        current_cpu_cores=1.0,
        current_mem_mb=3072.0,
        job_duration_min=25.0,
    )
    assert rec["recommended_cpu_cores"] == 1.0
    assert rec["recommended_cpu_cores_str"] == "1 vCPU"
    assert "適正" in rec["recommended_cpu_reason"]
    assert rec["recommended_memory_mb"] == 3072.0
    assert rec["recommended_memory_str"] == "3GiB"
    assert rec["recommended_task_count"] == 4
    assert rec["recommended_task_count_str"] == "4 台 (並行4台)"


def test_calculate_container_recommendations_high_cpu_over_90():
    rec = calculate_container_recommendations(
        cpu_peak_percent=92.5,
        mem_max_mb=2000.0,
        current_task_count=4,
        current_cpu_cores=1.0,
        current_mem_mb=3072.0,
    )
    assert rec["recommended_cpu_cores"] == 2.0
    assert rec["recommended_cpu_cores_str"] == "2 vCPU"
    assert "90%" in rec["recommended_cpu_reason"]


def test_calculate_container_recommendations_high_memory():
    rec = calculate_container_recommendations(
        cpu_peak_percent=85.0,
        mem_max_mb=2700.0,
        current_task_count=4,
        current_cpu_cores=1.0,
        current_mem_mb=3072.0,
    )
    assert rec["recommended_memory_mb"] == 4096.0
    assert rec["recommended_memory_str"] == "4GiB"
    assert "4 GiB 推奨" in rec["recommended_memory_reason"]


def test_calculate_container_recommendations_duration_scale_tasks():
    rec = calculate_container_recommendations(
        cpu_peak_percent=60.0,
        mem_max_mb=2000.0,
        current_task_count=4,
        current_cpu_cores=1.0,
        current_mem_mb=3072.0,
        job_duration_min=50.0,
    )
    assert rec["recommended_task_count"] == 6
    assert "6〜8 台分散推奨" in rec["recommended_task_reason"]


def test_calculate_container_recommendations_int_inputs_and_fractional_mem():
    rec = calculate_container_recommendations(
        cpu_peak_percent=50.0,
        mem_max_mb=1200.0,
        current_task_count=4,
        current_cpu_cores=1,  # int input
        current_mem_mb=1536,  # int input (1.5 GiB)
    )
    assert rec["recommended_cpu_cores"] == 1.0
    assert rec["recommended_cpu_cores_str"] == "1 vCPU"
    assert rec["recommended_memory_str"] == "1.5GiB"

