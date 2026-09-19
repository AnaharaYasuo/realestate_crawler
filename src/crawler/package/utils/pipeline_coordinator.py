# -*- coding: utf-8 -*-
"""
Cloud Run Jobs タスクアレイ Coordinator バリア同期ユーティリティ
"""
import time
import logging
from typing import List, Tuple, Any

logger = logging.getLogger(__name__)


def check_all_tasks_completed(records: List[Any], task_count: int) -> Tuple[bool, List[int]]:
    """
    全タスクが完了（COMPLETED または FAILED）しているかを判定。
    戻り値: (all_completed, failed_task_indices)
    """
    if task_count <= 1:
        return True, []
    
    status_map = {r.task_index: r.status for r in records}
    failed_indices = []
    
    for idx in range(task_count):
        if idx not in status_map:
            return False, []
        status = status_map[idx]
        if status not in ("COMPLETED", "FAILED"):
            return False, []
        if status == "FAILED":
            failed_indices.append(idx)
            
    return True, failed_indices


def wait_for_all_tasks(
    model: Any,
    execution_date: Any,
    task_count: int,
    timeout_sec: int = 1800,
    interval_sec: int = 15
) -> Tuple[bool, List[int]]:
    """
    Task 0 が他全タスクの完了を DB ポーリングで待機するバリア関数。
    """
    if task_count <= 1:
        return True, []
    
    start_time = time.time()
    logger.info(f"⏳ [Coordinator Barrier] 全 {task_count} タスクの完了待機を開始 (タイムアウト: {timeout_sec}秒)")
    
    while time.time() - start_time < timeout_sec:
        records = list(model.objects.filter(execution_date=execution_date))
        all_completed, failed = check_all_tasks_completed(records, task_count)
        
        if all_completed:
            logger.info(f"✔ [Coordinator Barrier] 全 {task_count} タスクの完了を検知 (失敗タスク数: {len(failed)})")
            return True, failed
        
        finished_cnt = sum(1 for r in records if r.status in ("COMPLETED", "FAILED"))
        logger.info(f"⏳ [Coordinator Barrier] 進行状況: {finished_cnt}/{task_count} タスク完了。次回確認まで {interval_sec}秒 待機中...")
        time.sleep(interval_sec)
        
    logger.error(f"✘ [Coordinator Barrier] タイムアウト ({timeout_sec}秒) 超過。一部タスクが未完了のまま待機を終了します。")
    records = list(model.objects.filter(execution_date=execution_date))
    _, failed = check_all_tasks_completed(records, task_count)
    return False, failed
