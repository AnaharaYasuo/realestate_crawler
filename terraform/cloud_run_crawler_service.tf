# Cloud Run Service for Crawler Worker (Cloud Tasks からの分散並列スクレイピング受付用)
resource "google_cloud_run_v2_service" "crawler_worker_service" {
  name     = "realestate-crawler-worker-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # Cloud Tasks からの OIDC 認証付き HTTP POST 呼び出しを許可

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_compute_forwarding_rule.proxysql_forwarding_rule,
    google_vpc_access_connector.vpc_connector,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    service_account = google_service_account.crawler_runner.email
    timeout         = "900s" # 1タスクあたり最大15分

    scaling {
      min_instance_count = 0 # アイドル時0台 (待機コスト完全¥0)
      max_instance_count = var.crawler_queue_max_concurrent_dispatches # 過剰スケール・接続枯渇防止
    }

    vpc_access {
      connector = google_vpc_access_connector.vpc_connector.id
      egress    = "ALL_TRAFFIC" # 外部スクレイピングは Cloud NAT (固定IP)、DB は ProxySQL ILB 経由
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }

      env {
        name  = "IS_CLOUD"
        value = "true"
      }
      env {
        name  = "LOG_FORMAT"
        value = "json"
      }
      env {
        name  = "PYTHONIOENCODING"
        value = "utf-8"
      }

      # データベース接続設定: ProxySQL ILB 経由ポート 6033
      env {
        name  = "DB_HOST"
        value = google_compute_forwarding_rule.proxysql_forwarding_rule.ip_address
      }
      env {
        name  = "DB_NAME"
        value = var.db_name
      }
      env {
        name  = "DB_USER"
        value = var.db_user
      }
      env {
        name  = "DB_PORT"
        value = "6033"
      }
      env {
        name  = "CONN_MAX_AGE"
        value = "0"
      }

      # Cloud Storage 画像保存バケット
      env {
        name  = "STORAGE_BUCKET"
        value = google_storage_bucket.property_images.name
      }

      # Secret Manager からのシークレット注入
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_password_secret.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "ESTIMATION_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "realestate-estimation-api-key-${var.environment}"
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image
    ]
  }
}

# Grant Cloud Run Invoker role to crawler runner service account for crawler worker
resource "google_cloud_run_v2_service_iam_member" "crawler_worker_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.crawler_worker_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.crawler_runner.email}"
}
