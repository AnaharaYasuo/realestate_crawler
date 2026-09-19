# Cloud Tasks Queue for Parallel Crawling
resource "google_cloud_tasks_queue" "crawler_tasks_queue" {
  name     = "realestate-crawler-queue-${var.environment}"
  location = var.region

  rate_limits {
    max_dispatches_per_second = var.crawler_queue_max_dispatches_per_second
    max_concurrent_dispatches = var.crawler_queue_max_concurrent_dispatches
  }

  retry_config {
    max_attempts  = 3
    min_backoff   = "5s"
    max_backoff   = "60s"
    max_doublings = 3
  }

  depends_on = [
    google_project_service.enabled_services
  ]
}

# Grant Cloud Tasks Enqueuer role to crawler runner service account
resource "google_project_iam_member" "crawler_runner_tasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Grant Cloud Run Invoker role to crawler runner service account for task dispatch
resource "google_cloud_run_v2_service_iam_member" "crawler_runner_service_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.slack_agent_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}
