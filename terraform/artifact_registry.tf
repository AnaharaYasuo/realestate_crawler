# Artifact Registry Repository for Crawler Docker Images
resource "google_artifact_registry_repository" "crawler_repo" {
  # checkov:skip=CKV_GCP_84:Use default Google-managed encryption to avoid unnecessary KMS key costs
  location      = var.region
  repository_id = "realestate-crawler-${var.environment}"
  description   = "Docker repository for Real Estate Crawler and ML Pipeline"
  format        = "DOCKER"

  depends_on = [google_project_service.enabled_services]
}
