import os
from typing import Any


def calculate_container_recommendations(
    cpu_peak_percent: float,
    mem_max_mb: float,
    current_task_count: int = 4,
    current_cpu_cores: float = 1.0,
    current_mem_mb: float = 3072.0,
    job_duration_min: float | None = None,
) -> dict[str, Any]:
    """Calculate recommended Cloud Run container specs and task array count.

    Rules:
    - CPU Peak Threshold: 90% (user tolerance). If > 90%, recommend scale up. If < 40%, recommend scale down.
    - Memory Peak Threshold: 85% of limit (e.g. 2611 MB for 3GiB). If > 85%, recommend scale up to prevent OOM.
    - Task Count (container count): default 4. If execution duration > 45min, recommend 6-8 tasks.
    """
    rec_cpu = float(current_cpu_cores)
    rec_cpu_reason = "適正（ピーク90%以内）"
    if cpu_peak_percent > 90.0:
        rec_cpu = 2.0
        rec_cpu_reason = f"CPU負荷高（ピーク{cpu_peak_percent:.1f}% > 90%）のため 2 vCPU 推奨"
    elif cpu_peak_percent < 35.0 and current_cpu_cores > 1.0:
        rec_cpu = 1.0
        rec_cpu_reason = f"CPU余裕あり（ピーク{cpu_peak_percent:.1f}% < 35%）のため 1 vCPU 推奨"

    rec_mem_mb = float(current_mem_mb)
    rec_mem_reason = "適正（OOM安全マージン確保・利用率85%以内）"
    mem_usage_ratio = (mem_max_mb / current_mem_mb) * 100.0 if current_mem_mb > 0 else 0.0
    if mem_usage_ratio > 85.0 or mem_max_mb > 2600.0:
        rec_mem_mb = 4096.0
        rec_mem_reason = f"メモリ逼迫（{mem_max_mb:.0f}MB / 85%超過）のため 4 GiB 推奨"
    elif mem_max_mb < 1500.0 and current_mem_mb > 2048.0:
        rec_mem_mb = 2048.0
        rec_mem_reason = f"メモリ余裕あり（最大{mem_max_mb:.0f}MB < 1.5GiB）のため 2 GiB 推奨"

    rec_tasks = current_task_count
    rec_tasks_reason = "適正（4並列ハッシュ分散・DB接続枠安定）"
    if job_duration_min is not None and job_duration_min > 45.0:
        rec_tasks = 6
        rec_tasks_reason = f"所要時間超過（{job_duration_min:.1f}分 > 45分）のため 6〜8 台分散推奨"

    return {
        "recommended_cpu_cores": rec_cpu,
        "recommended_cpu_cores_str": f"{int(rec_cpu) if rec_cpu.is_integer() else rec_cpu} vCPU",
        "recommended_cpu_reason": rec_cpu_reason,
        "recommended_memory_mb": rec_mem_mb,
        "recommended_memory_str": f"{rec_mem_mb / 1024:g}GiB",
        "recommended_memory_reason": rec_mem_reason,
        "recommended_task_count": rec_tasks,
        "recommended_task_count_str": f"{rec_tasks} 台 (並行{rec_tasks}台)",
        "recommended_task_reason": rec_tasks_reason,
    }
