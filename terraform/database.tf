# Private IP Allocation for Cloud SQL (Private Services Access)
resource "google_compute_global_address" "private_ip_address" {
  name          = "cloudsql-private-ip-${var.environment}"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc_network.id
}

# Peering Connection between VPC and Google Managed Services
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc_network.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip_address.name]
}

# Random string for instance name suffix (re-creation safety)
resource "random_id" "db_suffix" {
  byte_length = 4
}

#tfsec:ignore:google-sql-encrypt-in-transit
#trivy:ignore:AVD-GCP-0015
resource "google_sql_database_instance" "mysql_instance" {
  # checkov:skip=CKV_GCP_60:VPC internal private IP only; unencrypted connections allowed inside VPC
  # checkov:skip=CKV_GCP_6:VPC internal private IP only; ProxySQL terminates connections inside VPC
  name             = "realestate-mysql-${var.environment}-${random_id.db_suffix.hex}"
  database_version = "MYSQL_8_0"
  region           = var.region

  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.enabled_services
  ]

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL" # コスト重視のためシングルゾーン (本番要件によりREGIONAL変更可能)
    disk_type         = "PD_SSD"
    disk_size         = 20
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled                                  = false # パブリックIP露出を排除
      private_network                               = google_compute_network.vpc_network.id
      enable_private_path_for_google_cloud_services = true
      ssl_mode                                      = "ALLOW_UNENCRYPTED_AND_ENCRYPTED" # VPCプライベート接続のため暗号化任意設定
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "19:00" # JST 04:00 (バッチ完了後)
      binary_log_enabled             = true
      transaction_log_retention_days = 7
    }

    database_flags {
      name  = "character_set_server"
      value = "utf8mb4"
    }
    database_flags {
      name  = "collation_server"
      value = "utf8mb4_unicode_ci"
    }
    database_flags {
      name  = "max_connections"
      value = "1000"
    }
    database_flags {
      name  = "cloudsql_iam_authentication"
      value = "on"
    }
    database_flags {
      name  = "local_infile"
      value = "off"
    }
    database_flags {
      name  = "skip_show_database"
      value = "on"
    }
    database_flags {
      name  = "default_authentication_plugin"
      value = "mysql_native_password"
    }
  }

  deletion_protection = true # 誤削除防止 (セキュリティ強化)
}

# Database
resource "google_sql_database" "database" {
  name      = var.db_name
  instance  = google_sql_database_instance.mysql_instance.name
  charset   = "utf8mb4"
  collation = "utf8mb4_unicode_ci"
}

# Random Password for MySQL User
resource "random_password" "db_password" {
  length  = 24
  special = false
}

# MySQL User
resource "google_sql_user" "db_user" {
  name     = var.db_user
  instance = google_sql_database_instance.mysql_instance.name
  host     = "%"
  password = random_password.db_password.result
}

# Random Password for ProxySQL Monitor User
resource "random_password" "db_monitor_password" {
  length  = 24
  special = false
}

# MySQL Monitor User for ProxySQL Health Checks
resource "google_sql_user" "monitor_user" {
  name     = "monitor"
  instance = google_sql_database_instance.mysql_instance.name
  host     = "%"
  password = random_password.db_monitor_password.result
}

