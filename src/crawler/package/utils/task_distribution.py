# -*- coding: utf-8 -*-
"""
Cloud Run Jobs タスク分散ユーティリティ
"""
import os
from typing import List, Tuple, Optional


def get_task_config() -> Tuple[Optional[int], int]:
    """環境変数から Cloud Run Jobs のタスク番号と総タスク数を取得"""
    raw_index = os.getenv("CLOUD_RUN_TASK_INDEX")
    raw_count = os.getenv("CLOUD_RUN_TASK_COUNT")
    
    task_index = int(raw_index) if raw_index is not None and raw_index.isdigit() else None
    task_count = int(raw_count) if raw_count is not None and raw_count.isdigit() else 1
    
    return task_index, task_count


def distribute_jobs(
    jobs: List[Tuple[str, str]],
    task_index: Optional[int] = None,
    task_count: int = 1
) -> List[Tuple[str, str]]:
    """
    全ジョブリストをタスクインデックスに応じて Modulo 分割して返す。
    task_count <= 1 または task_index is None の場合は全ジョブを返す。
    """
    if task_count <= 1 or task_index is None:
        return list(jobs)
    
    if task_index < 0 or task_index >= task_count:
        raise ValueError(f"task_index ({task_index}) out of range for task_count ({task_count})")
    
    return [job for i, job in enumerate(jobs) if i % task_count == task_index]
