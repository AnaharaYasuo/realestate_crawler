# Cloud Run Job for Real Estate Crawler & ML Pipeline (案A: 単一Job実行, 案C: タスクアレイ拡張対応)
resource "google_cloud_run_v2_job" "crawler_pipeline_job" {
  name     = "realestate-crawler-pipeline-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_compute_forwarding_rule.proxysql_forwarding_rule,
    google_vpc_access_connector.vpc_connector,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_version.slack_bot_token_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    # 案C: Cloud Run Jobs タスクアレイ並列分散実行
    task_count  = var.crawler_task_count
    parallelism = var.crawler_parallelism

    template {
      service_account = google_service_account.crawler_runner.email
      timeout         = var.crawler_timeout
      max_retries     = 1

      vpc_access {
        connector = google_vpc_access_connector.vpc_connector.id
        egress    = "ALL_TRAFFIC" # 全外部通信をVPC経由にし、Cloud NAT(固定IP)から送信
      }

      containers {
        image = "python:3.11-slim"

        command = ["python", "-c", "import sys; print('Initial Cloud Run Job placeholder container'); sys.exit(0)"]

        resources {
          limits = {
            cpu    = var.crawler_cpu
            memory = var.crawler_memory
          }
        }

        # 実行環境 & ロギング設定
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
        env {
          name  = "CLOUD_DETAIL_CONCURRENCY"
          value = "5"
        }
        env {
          name  = "ML_NUM_THREADS"
          value = "-1"
        }
        env {
          name  = "BULK_EVAL_CONCURRENCY"
          value = "4"
        }

        # データベース接続設定 (ProxySQL ILB 経由ポート 6033)
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
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.db_password_secret.secret_id
              version = "latest"
            }
          }
        }

        # ストレージ設定 (GCS)
        env {
          name  = "STORAGE_BACKEND"
          value = "gcs"
        }
        env {
          name  = "STORAGE_BUCKET"
          value = google_storage_bucket.property_images.name
        }

        # Slack トークン設定
        env {
          name = "SLACK_BOT_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.slack_bot_token.secret_id
              version = "latest"
            }
          }
        }

        # Slack チャンネル設定
        env {
          name  = "SLACK_CHANNEL_ID"
          value = "C0BGJF4E737"
        }
        env {
          name  = "SLACK_DEV_CHANNEL"
          value = "C0BKBHWD26T"
        }
        env {
          name  = "SLACK_ALERT_PROPERTY_ALERT"
          value = "property_alert"
        }
        env {
          name  = "SLACK_RECOMMEND_MANSION"
          value = "C0BJ87V7BM0"
        }
        env {
          name  = "SLACK_RECOMMEND_KODATE"
          value = "C0BJ87VEV0S"
        }
        env {
          name  = "SLACK_RECOMMEND_TOCHI"
          value = "C0BJA5D1GMP"
        }
        env {
          name  = "SLACK_RECOMMEND_INVEST_APARTMENT"
          value = "C0BJBUMSYGL"
        }
        env {
          name  = "SLACK_RECOMMEND_INVEST_KODATE"
          value = "C0BJ20EMQ67"
        }

        # Playwright は --disable-dev-shm-usage フラグで /tmp を利用するため shm の個別マウント不要
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image,
      template[0].template[0].containers[0].command
    ]
  }
}

# Cloud Run Job for DB Migration (デプロイ時の自動マイグレーション実行用)
resource "google_cloud_run_v2_job" "db_migrate_job" {
  name     = "realestate-migrate-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_vpc_access_connector.vpc_connector,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    template {
      service_account = google_service_account.crawler_runner.email
      timeout         = "600s"
      max_retries     = 1

      vpc_access {
        connector = google_vpc_access_connector.vpc_connector.id
        egress    = "ALL_TRAFFIC"
      }

      containers {
        image   = "python:3.11-slim"
        command = ["python", "src/crawler/manage.py", "migrate", "--noinput"]

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }

        env {
          name  = "IS_CLOUD"
          value = "true"
        }
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
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image
    ]
  }
}

# Cloud Run Job for Safety-Net Resource Inspection (ゾンビ課金防止 自動強制停止ジョブ)
resource "google_cloud_run_v2_job" "resource_safety_net_job" {
  name     = "realestate-safety-net-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_secret_manager_secret_version.slack_bot_token_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    template {
      service_account = google_service_account.crawler_runner.email
      timeout         = "300s"
      max_retries     = 1

      containers {
        image   = "python:3.11-slim"
        command = ["python", "-c", "import sys; print('Initial safety-net job placeholder'); sys.exit(0)"]

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
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
        env {
          name = "SLACK_BOT_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.slack_bot_token.secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "SLACK_ALERT_PROPERTY_ALERT"
          value = "property_alert"
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
      template[0].template[0].containers[0].image,
      template[0].template[0].containers[0].command
    ]
  }
}


