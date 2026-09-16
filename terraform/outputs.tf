output "nat_static_ip" {
  description = "Cloud NAT Static External IP (クローラー送信元固定IP)"
  value       = google_compute_address.nat_static_ip.address
}

output "cloud_sql_private_ip" {
  description = "Cloud SQL Private IP Address"
  value       = google_sql_database_instance.mysql_instance.private_ip_address
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL Instance Connection Name"
  value       = google_sql_database_instance.mysql_instance.connection_name
}

output "gcs_image_bucket" {
  description = "Cloud Storage Bucket for Property Images"
  value       = google_storage_bucket.property_images.name
}

output "artifact_registry_repo" {
  description = "Artifact Registry Docker Repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.crawler_repo.name}"
}

output "cloud_run_job_name" {
  description = "Cloud Run Pipeline Job Name"
  value       = google_cloud_run_v2_job.crawler_pipeline_job.name
}

output "cloud_run_service_url" {
  description = "Cloud Run Slack Agent Service URL"
  value       = google_cloud_run_v2_service.slack_agent_service.uri
}

output "budget_pubsub_topic" {
  description = "Pub/Sub Topic for Budget Alerts (Slack integration)"
  value       = google_pubsub_topic.budget_alert_topic.id
}

