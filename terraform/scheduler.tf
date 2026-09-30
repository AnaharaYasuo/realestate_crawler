# Cloud Scheduler Job to trigger Daily Pipeline via Cloud Workflows
resource "google_cloud_scheduler_job" "crawler_daily_trigger" {
  name             = "realestate-crawler-daily-${var.environment}"
  description      = "Triggers real estate daily pipeline orchestration (ProxySQL -> Crawl -> ML -> Recommendation -> Stop) via Cloud Workflows"
  schedule         = var.schedule_cron
  time_zone        = "Etc/UTC"
  attempt_deadline = "300s"

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/projects/${var.project_id}/locations/${var.region}/workflows/${google_workflows_workflow.daily_pipeline_workflow.name}/executions"

    oauth_token {
      service_account_email = google_service_account.scheduler_invoker.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }

    body = base64encode(jsonencode({
      argument = jsonencode({
        projectId        = var.project_id
        location         = var.region
        zone             = var.zone
        proxysqlInstance = google_compute_instance.proxysql_instance.name
        crawlerJob       = google_cloud_run_v2_job.crawler_pipeline_job.name
        mlPipelineJob    = google_cloud_run_v2_job.ml_pipeline_job.name
      })
    }))
  }

  depends_on = [
    google_project_service.enabled_services,
    google_workflows_workflow.daily_pipeline_workflow,
    google_project_iam_member.scheduler_workflows_invoker
  ]
}

# Cloud Scheduler Job to trigger ML Pipeline once after the crawler job deadline
# Note: Integrated into Cloud Workflows daily orchestration. Paused to prevent duplicate execution.
resource "google_cloud_scheduler_job" "ml_pipeline_daily_trigger" {
  name             = "realestate-ml-pipeline-daily-${var.environment}"
  description      = "Triggers aggregated crawl report, ML training, bulk estimation & recommendations daily at 03:10 JST (18:10 UTC)"
  schedule         = var.ml_pipeline_schedule_cron
  time_zone        = "Etc/UTC"
  attempt_deadline = "300s"
  paused           = true

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ml_pipeline_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler_invoker.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.enabled_services,
    google_cloud_run_v2_job.ml_pipeline_job,
    google_cloud_run_v2_job_iam_member.ml_pipeline_run_invoker
  ]
}

# Cloud Scheduler Job for Resource Safety-Net (Hourly during 02:00-06:00 JST / 17:00-21:00 UTC)
resource "google_cloud_scheduler_job" "crawler_safety_net_trigger" {
  name             = "realestate-safety-net-daily-${var.environment}"
  description      = "Triggers safety net check hourly during 02:00-06:00 JST (17:00-21:00 UTC) to ensure ProxySQL MIG & NAT are stopped"
  schedule         = "0 17-21 * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "300s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.resource_safety_net_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler_invoker.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.enabled_services,
    google_cloud_run_v2_job.resource_safety_net_job,
    google_cloud_run_v2_job_iam_member.safety_net_run_invoker
  ]
}
