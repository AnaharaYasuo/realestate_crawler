# Google Cloud Workflows Pipeline Orchestration
# クロール (5h上限) -> ML学習 -> 価格推定・割安配信 -> ProxySQL停止を直列オーケストレーション

resource "google_workflows_workflow" "daily_pipeline_workflow" {
  name            = "realestate-daily-pipeline-${var.environment}"
  region          = var.region
  description     = "Daily orchestrated pipeline for crawl, ML training, estimation & recommendation with 7h deadline"
  service_account = google_service_account.crawler_runner.email

  # ワークフロー全体の上限: 7時間 (25,200秒)
  # クロール上限 (5h) + ML・価格推定 (最長2h) を包括
  source_contents = file("${path.module}/workflows/daily_pipeline.yaml")

  depends_on = [
    google_project_service.enabled_services,
    google_cloud_run_v2_job.crawler_pipeline_job,
    google_cloud_run_v2_job.ml_pipeline_job,
    google_compute_instance.proxysql_instance
  ]
}

# Cloud Scheduler から Cloud Workflows をキックするための権限
resource "google_project_iam_member" "scheduler_workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}
