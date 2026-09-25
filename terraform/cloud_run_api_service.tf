# Cloud Run Service for Web APIs & Swagger UI (価格推定推論API 外部公開用)
resource "google_cloud_run_v2_service" "estimation_api_service" {
  name     = "realestate-api-${var.environment}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # 外部からのインバウンドアクセスを許可

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_compute_subnetwork.subnet,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_version.estimation_api_key_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    service_account = google_service_account.crawler_runner.email

    scaling {
      min_instance_count = 0 # アイドル時0台 (待機コスト¥0)
      max_instance_count = 2 # 過剰スケール防止
    }

    vpc_access {
      network_interfaces {
        network    = google_compute_network.vpc_network.name
        subnetwork = google_compute_subnetwork.subnet.name
      }
      egress    = "PRIVATE_RANGES_ONLY" # Cloud SQLへのDB通信のみVPC経由。NAT停止時も外部スクレイピング疎通可能
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        startup_cpu_boost = true
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

      # データベース接続設定: Gmailチェッカー等常時API呼び出しのため、ProxySQLではなくCloud SQLへ直接接続 (ポート3306)
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.mysql_instance.private_ip_address
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
        value = "3306"
      }
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
            secret  = google_secret_manager_secret.estimation_api_key_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].containers[0].image,
      template[0].containers[0].command
    ]
  }
}

# 外部アクセス用のパブリック呼出し権限 (未認証アクセスの許可、認証はAPIキーにて制御)
resource "google_cloud_run_v2_service_iam_member" "estimation_api_public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.estimation_api_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
