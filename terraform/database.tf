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

# Cloud SQL for MySQL 8.0 Instance
resource "google_sql_database_instance" "mysql_instance" {
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
      require_ssl                                   = true  # 通信の暗号化強制
    }

    backup_configuration {
      enabled            = true
      start_time         = "19:00" # JST 04:00 (バッチ完了後)
      binary_log_enabled = false
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
  password = random_password.db_password.result
}
