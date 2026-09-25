# Cloud Scheduler Job to trigger Crawler Pipeline Daily
resource "google_cloud_scheduler_job" "crawler_daily_trigger" {
  name             = "realestate-crawler-daily-${var.environment}"
  description      = "Triggers real estate crawling & ML pipeline daily at 01:00 JST (16:00 UTC)"
  schedule         = var.schedule_cron
  time_zone        = "Etc/UTC"
  attempt_deadline = "300s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.crawler_pipeline_job.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler_invoker.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.enabled_services,
    google_cloud_run_v2_job.crawler_pipeline_job,
    google_cloud_run_v2_job_iam_member.run_invoker
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
