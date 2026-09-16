# GCS Bucket for Property Images & Artifacts (MinIO代替)
resource "google_storage_bucket" "property_images" {
  name          = "realestate-images-${var.project_id}-${var.environment}"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced" # 意図しないパブリック公開を完全遮断

  versioning {
    enabled = true
  }

  # 非現行バージョン（過去履歴）は30日で自動消去しストレージ無駄課金を抑止
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
    }
    action {
      type = "Delete"
    }
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
