# Cloud Run Job for Real Estate Crawler & ML Pipeline (案A: 単一Job実行, 案C: タスクアレイ拡張対応)
resource "google_cloud_run_v2_job" "crawler_pipeline_job" {
  name     = "realestate-crawler-pipeline-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_compute_address.proxysql_ip,
    google_compute_subnetwork.subnet,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_version.slack_bot_token_version,
    google_secret_manager_secret_version.new_relic_license_key_version,
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
        network_interfaces {
          network    = google_compute_network.vpc_network.name
          subnetwork = google_compute_subnetwork.subnet.name
        }
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

        # データベース接続設定 (ProxySQL 経由ポート 6033)
        env {
          name  = "DB_HOST"
          value = google_compute_address.proxysql_ip.address
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
          name  = "PROXYSQL_INSTANCE_NAME"
          value = google_compute_instance.proxysql_instance.name
        }
        env {
          name  = "PROXYSQL_ZONE"
          value = google_compute_instance.proxysql_instance.zone
        }
        env {
          name  = "CLOUDSQL_INSTANCE_NAME"
          value = google_sql_database_instance.mysql_instance.name
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

        # New Relic 監視設定
        env {
          name = "NEW_RELIC_LICENSE_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.new_relic_license_key.secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "NEW_RELIC_APP_NAME"
          value = "realestate-crawler-pipeline-${var.environment}"
        }
        env {
          name  = "NEW_RELIC_DISTRIBUTED_TRACING_ENABLED"
          value = "true"
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
    google_compute_subnetwork.subnet,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    template {
      service_account = google_service_account.crawler_runner.email
      timeout         = "600s"
      max_retries     = 1

      vpc_access {
        network_interfaces {
          network    = google_compute_network.vpc_network.name
          subnetwork = google_compute_subnetwork.subnet.name
        }
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
          name  = "CLOUDSQL_INSTANCE_NAME"
          value = google_sql_database_instance.mysql_instance.name
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
        env {
          name  = "PROXYSQL_INSTANCE_NAME"
          value = google_compute_instance.proxysql_instance.name
        }
        env {
          name  = "PROXYSQL_ZONE"
          value = google_compute_instance.proxysql_instance.zone
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

# Cloud Run Job for Crawler Dispatcher (ProxySQL起動 & Cloud Tasks一括投入用: 実行時間5秒〜1分)
resource "google_cloud_run_v2_job" "crawler_dispatcher_job" {
  name     = "realestate-crawler-dispatcher-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_compute_address.proxysql_ip,
    google_compute_subnetwork.subnet,
    google_cloud_tasks_queue.crawler_tasks_queue,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    template {
      service_account = google_service_account.crawler_runner.email
      timeout         = "300s" # 5分
      max_retries     = 1

      vpc_access {
        network_interfaces {
          network    = google_compute_network.vpc_network.name
          subnetwork = google_compute_subnetwork.subnet.name
        }
        egress    = "ALL_TRAFFIC"
      }

      containers {
        image = "python:3.11-slim"

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
          name  = "LOG_FORMAT"
          value = "json"
        }
        env {
          name  = "PYTHONIOENCODING"
          value = "utf-8"
        }
        env {
          name  = "DB_HOST"
          value = google_compute_address.proxysql_ip.address
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
        env {
          name  = "PROXYSQL_INSTANCE_NAME"
          value = google_compute_instance.proxysql_instance.name
        }
        env {
          name  = "PROXYSQL_MIG_NAME"
          value = google_compute_instance.proxysql_instance.name
        }
        env {
          name  = "CLOUDSQL_INSTANCE_NAME"
          value = google_sql_database_instance.mysql_instance.name
        }
        env {
          name  = "CLOUD_TASKS_QUEUE"
          value = google_cloud_tasks_queue.crawler_tasks_queue.name
        }
        env {
          name  = "CRAWLER_WORKER_URL"
          value = "${google_cloud_run_v2_service.crawler_worker_service.uri}/api/crawl/task"
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
              secret  = "realestate-estimation-api-key-${var.environment}"
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
      template[0].template[0].containers[0].image,
      template[0].template[0].containers[0].command
    ]
  }
}

# Cloud Run Job for ML Pipeline (全クロール完了後の学習・バルク推論・ProxySQL停止用: 15〜30分)
resource "google_cloud_run_v2_job" "ml_pipeline_job" {
  name     = "realestate-ml-pipeline-${var.environment}"
  location = var.region

  depends_on = [
    google_project_service.enabled_services,
    google_sql_database_instance.mysql_instance,
    google_compute_address.proxysql_ip,
    google_compute_subnetwork.subnet,
    google_secret_manager_secret_version.db_password_version,
    google_secret_manager_secret_version.slack_bot_token_version,
    google_secret_manager_secret_iam_member.secret_accessor
  ]

  template {
    template {
      service_account = google_service_account.crawler_runner.email
      timeout         = "7200s" # 2時間
      max_retries     = 1

      vpc_access {
        network_interfaces {
          network    = google_compute_network.vpc_network.name
          subnetwork = google_compute_subnetwork.subnet.name
        }
        egress    = "ALL_TRAFFIC"
      }

      containers {
        image = "python:3.11-slim"

        resources {
          limits = {
            cpu    = "4"
            memory = "8Gi"
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
          name  = "DB_HOST"
          value = google_compute_address.proxysql_ip.address
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
        env {
          name  = "PROXYSQL_INSTANCE_NAME"
          value = google_compute_instance.proxysql_instance.name
        }
        env {
          name  = "PROXYSQL_MIG_NAME"
          value = google_compute_instance.proxysql_instance.name
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
          name = "SLACK_BOT_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.slack_bot_token.secret_id
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
      template[0].template[0].containers[0].image,
      template[0].template[0].containers[0].command
    ]
  }
}


