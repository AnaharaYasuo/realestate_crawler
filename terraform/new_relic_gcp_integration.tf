# ---------------------------------------------------------
# New Relic GCP Log Streaming & Cloud Logging Integration
# Issue #473: Log in Context and centralized observability
# ---------------------------------------------------------

resource "google_pubsub_topic" "new_relic_log_topic" {
  name    = "realestate-newrelic-logs-${var.environment}"
  project = var.project_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "newrelic-logging"
  }
}

resource "google_logging_project_sink" "new_relic_log_sink" {
  name                   = "realestate-newrelic-sink-${var.environment}"
  project                = var.project_id
  destination            = "pubsub.googleapis.com/${google_pubsub_topic.new_relic_log_topic.id}"
  unique_writer_identity = true

  # Stream logs from Cloud Run, Cloud Run Jobs, Cloud SQL, and GCE ProxySQL instances
  filter = <<-EOT
    resource.type = "cloud_run_revision" OR
    resource.type = "cloud_run_job" OR
    resource.type = "cloudsql_database" OR
    resource.type = "gce_instance"
  EOT

  # Ensure Deploy SA has logging.sinks.create before creating this sink.
  depends_on = [google_project_iam_member.github_actions_logging_config_writer]
}

resource "google_pubsub_topic_iam_member" "new_relic_sink_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.new_relic_log_topic.name
  role    = "roles/pubsub.publisher"
  member  = google_logging_project_sink.new_relic_log_sink.writer_identity
}

# Push subscription to New Relic HTTP log intake endpoint
resource "google_pubsub_subscription" "new_relic_log_push" {
  name    = "realestate-newrelic-logs-push-${var.environment}"
  project = var.project_id
  topic   = google_pubsub_topic.new_relic_log_topic.id

  ack_deadline_seconds       = 60
  message_retention_duration = "86400s" # 1 day

  push_config {
    push_endpoint = var.new_relic_log_ingest_url != "" ? var.new_relic_log_ingest_url : "https://gcp-api.newrelic.com/log/v1?Api-Key=${google_secret_manager_secret_version.new_relic_license_key_version.secret_data}"
    attributes = {
      "x-goog-version" = "v1"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}
