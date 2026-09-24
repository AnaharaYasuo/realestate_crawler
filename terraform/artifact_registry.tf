# Artifact Registry Repository for Crawler Docker Images
resource "google_artifact_registry_repository" "crawler_repo" {
  # checkov:skip=CKV_GCP_84:Use default Google-managed encryption to avoid unnecessary KMS key costs
  location      = var.region
  repository_id = "realestate-crawler-${var.environment}"
  description   = "Docker repository for Real Estate Crawler and ML Pipeline"
  format        = "DOCKER"

  cleanup_policy_dry_run = false

  # 最新3世代のみを保持（4世代目以降は自動削除対象）
  cleanup_policies {
    id     = "keep-recent-3"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }

  # タグなし(UNTAGGED)の残存イメージを自動削除
  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state = "UNTAGGED"
    }
  }

  depends_on = [google_project_service.enabled_services]
}
