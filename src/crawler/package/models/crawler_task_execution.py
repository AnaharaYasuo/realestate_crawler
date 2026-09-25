# -*- coding: utf-8 -*-
from django.db import models


class CrawlerTaskExecution(models.Model):
    """Cloud Run Jobs タスクアレイの各タスク実行状態を追跡・同期するモデル"""
    execution_date = models.DateField(db_index=True)
    task_index = models.IntegerField(default=0)
    task_count = models.IntegerField(default=1)
    status = models.CharField(max_length=20, default="RUNNING")  # RUNNING, COMPLETED, FAILED
    jobs_assigned = models.IntegerField(default=0)
    jobs_success = models.IntegerField(default=0)
    jobs_failed = models.IntegerField(default=0)
    results_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crawler_task_execution"
        unique_together = ("execution_date", "task_index")
