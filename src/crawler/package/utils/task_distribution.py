# -*- coding: utf-8 -*-
"""
Cloud Run Jobs タスク分散ユーティリティ
"""
import datetime
import os
from typing import List, Tuple, Optional

EXECUTION_DATE_ENV = "CRAWLER_EXECUTION_DATE"


def get_task_config() -> Tuple[Optional[int], int]:
    """環境変数から Cloud Run Jobs のタスク番号と総タスク数を取得"""
    raw_index = os.getenv("CLOUD_RUN_TASK_INDEX")
    raw_count = os.getenv("CLOUD_RUN_TASK_COUNT")
    
    task_index = int(raw_index) if raw_index is not None and raw_index.isdigit() else None
    task_count = int(raw_count) if raw_count is not None and raw_count.isdigit() else 1
    
    return task_index, task_count


def get_execution_id() -> str:
    """同一 Cloud Run Jobs 実行の全タスクで共通の実行名 (CLOUD_RUN_EXECUTION) を返す (ローカル実行時は空文字)"""
    return os.getenv("CLOUD_RUN_EXECUTION", "")


def _parse_pinned_date(raw: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def get_execution_date() -> datetime.date:
    """パイプライン起動時に固定した実行日 (CRAWLER_EXECUTION_DATE) を返す (未固定・不正値ならローカル日付)"""
    pinned = _parse_pinned_date(os.getenv(EXECUTION_DATE_ENV, ""))
    return pinned or datetime.datetime.now(datetime.timezone.utc).astimezone().date()


def pin_execution_date() -> datetime.date:
    """実行日を環境変数に固定し、日付を跨いでも子プロセスを含め同一の実行日を参照させる"""
    execution_date = get_execution_date()
    os.environ[EXECUTION_DATE_ENV] = execution_date.isoformat()
    return execution_date


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
