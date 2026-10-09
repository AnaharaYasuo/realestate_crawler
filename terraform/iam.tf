# Service Account for Cloud Run Jobs & Services
resource "google_service_account" "crawler_runner" {
  account_id   = "crawler-runner-${var.environment}"
  display_name = "Real Estate Crawler Runner Service Account"
}

# Grant Cloud SQL Client Role
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Grant Storage Object Admin on Image Bucket
resource "google_storage_bucket_iam_member" "storage_admin" {
  bucket = google_storage_bucket.property_images.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Grant Secret Manager Secret Accessor (Scoped to specific crawler secrets only)
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  for_each = {
    db_password           = google_secret_manager_secret.db_password_secret.secret_id
    slack_bot             = google_secret_manager_secret.slack_bot_token.secret_id
    slack_app             = google_secret_manager_secret.slack_app_token.secret_id
    new_relic_license_key = google_secret_manager_secret.new_relic_license_key.secret_id
  }

  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Grant Compute Instance Admin Role (for safety-net and on-demand ProxySQL MIG resizing)
resource "google_project_iam_member" "crawler_runner_compute_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Grant Cloud Run Developer & Viewer to crawler_runner (Workflows orchestrates Cloud Run Jobs with overrides)
resource "google_cloud_run_v2_job_iam_member" "crawler_runner_crawler_executor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.crawler_pipeline_job.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}

resource "google_cloud_run_v2_job_iam_member" "crawler_runner_crawler_viewer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.crawler_pipeline_job.name
  role     = "roles/run.viewer"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Grant Project-wide Cloud Run Viewer role for jobs.list and executions inspection
resource "google_project_iam_member" "crawler_runner_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.crawler_runner.email}"
}


resource "google_cloud_run_v2_job_iam_member" "crawler_runner_ml_executor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.ml_pipeline_job.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}

resource "google_cloud_run_v2_job_iam_member" "crawler_runner_ml_viewer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.ml_pipeline_job.name
  role     = "roles/run.viewer"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}

# Deploy SA needs logging.sinks.create (roles/editor no longer includes sink write).
# Required for google_logging_project_sink.new_relic_log_sink in CI Terraform Apply.
# Must match secrets.GCP_SERVICE_ACCOUNT (github-actions-crawler); that SA already has
# roles/resourcemanager.projectIamAdmin so it can manage this binding itself.
resource "google_project_iam_member" "github_actions_logging_config_writer" {
  project = var.project_id
  role    = "roles/logging.configWriter"
  member  = "serviceAccount:${var.github_actions_sa_email}"
}

# Service Account for Cloud Scheduler
resource "google_service_account" "scheduler_invoker" {
  account_id   = "scheduler-invoker-${var.environment}"
  display_name = "Cloud Scheduler Invoker for Cloud Run Jobs"
}

# Grant Cloud Run Invoker to Scheduler Service Account (Scoped to crawler job only)
resource "google_cloud_run_v2_job_iam_member" "run_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.crawler_pipeline_job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# Grant Cloud Run Invoker to Scheduler Service Account (ML pipeline job)
resource "google_cloud_run_v2_job_iam_member" "ml_pipeline_run_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.ml_pipeline_job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# Grant Cloud Run Invoker to Scheduler Service Account (Safety net job)
resource "google_cloud_run_v2_job_iam_member" "safety_net_run_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.resource_safety_net_job.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}


# Grant Cloud Run Job Executor & Viewer to crawler_runner for Recrawl Anomalies Job (Issue #738)
resource "google_cloud_run_v2_job_iam_member" "crawler_runner_recrawl_executor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.recrawl_anomalies_job.name
  role     = "roles/run.jobsExecutor"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}

resource "google_cloud_run_v2_job_iam_member" "crawler_runner_recrawl_viewer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.recrawl_anomalies_job.name
  role     = "roles/run.viewer"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}
