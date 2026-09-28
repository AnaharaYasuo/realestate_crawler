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
    interval_sec: int = 15,
    execution_id: str | None = None,
) -> Tuple[bool, List[int]]:
    """
    Task 0 が他全タスクの完了を DB ポーリングで待機するバリア関数。
    execution_id 指定時 (空文字を含む) は同一実行 ID の行のみを対象とし、同日の別実行の行を除外する。
    """
    if task_count <= 1:
        return True, []

    filters = {"execution_date": execution_date}
    if execution_id is not None:
        filters["execution_id"] = execution_id
    start_time = time.time()
    logger.info(f"⏳ [Coordinator Barrier] 全 {task_count} タスクの完了待機を開始 (タイムアウト: {timeout_sec}秒)")
    
    while time.time() - start_time < timeout_sec:
        records = list(model.objects.filter(**filters))
        all_completed, failed = check_all_tasks_completed(records, task_count)
        
        if all_completed:
            logger.info(f"✔ [Coordinator Barrier] 全 {task_count} タスクの完了を検知 (失敗タスク数: {len(failed)})")
            return True, failed
        
        finished_cnt = sum(1 for r in records if r.status in ("COMPLETED", "FAILED"))
        logger.info(f"⏳ [Coordinator Barrier] 進行状況: {finished_cnt}/{task_count} タスク完了。次回確認まで {interval_sec}秒 待機中...")
        time.sleep(interval_sec)
        
    logger.error(f"✘ [Coordinator Barrier] タイムアウト ({timeout_sec}秒) 超過。一部タスクが未完了のまま待機を終了します。")
    records = list(model.objects.filter(**filters))
    _, failed = check_all_tasks_completed(records, task_count)
    return False, failed


def _task_record_fields(rec) -> tuple | None:
    """Returns (results, task_index, status) from a model instance or dict, or None if unsupported."""
    if hasattr(rec, "results_json"):
        return rec.results_json or [], getattr(rec, "task_index", None), getattr(rec, "status", "UNKNOWN")
    if isinstance(rec, dict):
        return rec.get("results_json") or [], rec.get("task_index"), rec.get("status", "UNKNOWN")
    return None


def aggregate_task_array_reports(task_records: list, total_jobs: int = 89) -> dict:
    """
    Aggregates results_json from all CrawlerTaskExecution records.
    Handles both model instances and plain dictionaries.
    """
    all_results = []
    task_stats = []
    for rec in task_records:
        fields = _task_record_fields(rec)
        if fields is None:
            continue
        results, task_idx, status = fields
        all_results.extend(results)
        task_stats.append(
            {
                "task_index": task_idx,
                "status": status,
                "job_count": len(results),
            }
        )

    success_jobs = sum(1 for r in all_results if r.get("status") == "success")
    failed_list = [
        r for r in all_results if r.get("status") in ["failed", "timeout", "error"]
    ]
    failed_jobs = len(failed_list)
    executed_jobs = len(all_results)
    missing_jobs = max(0, total_jobs - executed_jobs)

    msg_lines = ["📢 【クローリング全タスク集約レポート】"]
    msg_lines.append(f"実行タスク数: {len(task_records)} タスク")
    msg_lines.append(
        f"総ジョブ数: {total_jobs} (実行完了: {executed_jobs}, 成功: {success_jobs}, 失敗: {failed_jobs}{f', 未実行: {missing_jobs}' if missing_jobs > 0 else ''})"
    )

    if failed_list:
        msg_lines.append("\n⚠️ 異常・失敗が発生したクローラー:")
        for f in failed_list:
            company = f.get("company", "unknown")
            ptype = f.get("property_type", "unknown")
            status = f.get("status", "failed")
            code = f.get("exit_code", "?")
            dur = f.get("duration", "")
            dur_str = f", 所要: {dur}" if dur else ""
            msg_lines.append(f"• {company} - {ptype}: {status} (Code: {code}{dur_str})")
    elif missing_jobs > 0:
        msg_lines.append(f"\n⚠️ 未実行ジョブが {missing_jobs} 件あります（タスクのタイムアウト・未完了の可能性）。")
    else:
        msg_lines.append(f"\n✅ 全 {executed_jobs} ジョブが正常に実行・完了しました。")

    slack_message = "\n".join(msg_lines)

    return {
        "total_jobs": total_jobs,
        "executed_jobs": executed_jobs,
        "success_jobs": success_jobs,
        "failed_jobs": failed_jobs,
        "missing_jobs": missing_jobs,
        "all_results": all_results,
        "failed_list": failed_list,
        "task_stats": task_stats,
        "slack_message": slack_message,
    }
