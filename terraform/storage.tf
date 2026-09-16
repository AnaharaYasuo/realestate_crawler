# GCS Bucket for Property Images & Artifacts (MinIO代替)
resource "google_storage_bucket" "property_images" {
  name          = "realestate-images-${var.project_id}-${var.environment}"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = 180 # 180日経過した古い画像はNearlineへ移行してコスト最適化
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.enabled_services]
}
