# ==============================================================================
# ProxySQL Connection Pooling & Multiplexing Infrastructure
# ==============================================================================
# 目的: ProxySQL によりデータベース接続のリソース管理を効率化し、
#       バックエンド Cloud SQL が耐えられる上限ギリギリのコネクションを維持・多重化する。
# 構成: MIG (e2-micro 固定2台, 2ゾーン冗長) + ILB (内部ロードバランサー) + ヘルスチェック

# 1. ProxySQL 専用サービスアカウント (最小権限)
resource "google_service_account" "proxysql_sa" {
  account_id   = "proxysql-sa-${var.environment}"
  display_name = "ProxySQL Dedicated Service Account"
  description  = "Service account for ProxySQL Compute Engine instances with minimal required permissions."
}

# 2. ProxySQL インスタンステンプレート
#tfsec:ignore:google-compute-disk-encryption-customer-key
#trivy:ignore:AVD-GCP-0034
#trivy:ignore:AVD-GCP-0039
resource "google_compute_instance_template" "proxysql_template" {
  # checkov:skip=CKV_GCP_37: "Customer-supplied encryption keys not required for proxy layer"
  # checkov:skip=CKV_GCP_38: "Confidential compute not required for stateless proxy"
  name_prefix  = "proxysql-template-${var.environment}-"
  machine_type = var.proxysql_machine_type
  region       = var.region

  tags = ["proxysql", "allow-health-check"]

  disk {
    source_image = "debian-cloud/debian-12"
    auto_delete  = true
    boot         = true
    disk_type    = "pd-standard"
    disk_size_gb = 10
  }

  network_interface {
    network    = google_compute_network.vpc_network.id
    subnetwork = google_compute_subnetwork.subnet.id
    # パブリック外部IPは付与せず、VPC内部専用インスタンスとする
  }

  service_account {
    email  = google_service_account.proxysql_sa.email
    scopes = ["https://www.googleapis.com/auth/logging.write", "https://www.googleapis.com/auth/monitoring.write"]
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    set -euo pipefail

    echo "=== [START] ProxySQL Setup and Configuration ==="
    apt-get update && apt-get install -y lsb-release wget gnupg default-mysql-client

    # ProxySQL 公式リポジトリの登録とインストール
    wget -O - 'https://repo.proxysql.com/ProxySQL/proxysql-2.6.x/repo_pub_key' | gpg --dearmor -o /etc/apt/trusted.gpg.d/proxysql.gpg
    echo deb https://repo.proxysql.com/ProxySQL/proxysql-2.6.x/$(lsb_release -sc)/ ./ | tee /etc/apt/sources.list.d/proxysql.list
    apt-get update && apt-get install -y proxysql

    # ProxySQL 初期設定ファイルの生成
    # バックエンド Cloud SQL (${google_sql_database_instance.mysql_instance.private_ip_address}) への接続上限を
    # データベース耐用上限 (${var.proxysql_backend_max_connections}) に維持し、フロントエンドからの接続を効率的に多重化する。
    cat <<'CONFIG' > /etc/proxysql.cnf
    datadir="/var/lib/proxysql"

    admin_variables=
    {
        admin_credentials="admin:admin;radmin:radmin"
        mysql_ifaces="0.0.0.0:6032"
        refresh_interval=2000
    }

    mysql_variables=
    {
        threads=2
        max_connections=2048
        default_query_delay=0
        default_query_timeout=3600000
        have_compress=true
        poll_timeout=2000
        interfaces="0.0.0.0:6033"
        default_schema="information_schema"
        connect_timeout_server=3000
        free_connections_pct=10
        connection_max_age_ms=1800000
    }

    mysql_servers =
    (
        {
            address="${google_sql_database_instance.mysql_instance.private_ip_address}"
            port=3306
            hostgroup=0
            max_connections=${var.proxysql_backend_max_connections}
            max_replication_lag=0
            use_ssl=0
            weight=1
        }
    )

    mysql_users =
    (
        {
            username="${var.db_user}"
            password=""
            default_hostgroup=0
            max_connections=1000
            default_schema="${var.db_name}"
            active=1
            transaction_persistent=1
        }
    )
    CONFIG

    # ProxySQL サービスの起動と永続化
    systemctl daemon-reload
    systemctl enable proxysql
    systemctl restart proxysql

    echo "=== [SUCCESS] ProxySQL is listening on port 6033 (traffic) and 6032 (admin) ==="
  EOF

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    google_sql_database_instance.mysql_instance,
    google_compute_subnetwork.subnet
  ]
}

# 3. ProxySQL リージョンヘルスチェック (TCP: 6033)
resource "google_compute_region_health_check" "proxysql_health_check" {
  name               = "proxysql-health-check-${var.environment}"
  region             = var.region
  check_interval_sec = 10
  timeout_sec        = 5
  healthy_threshold  = 2
  unhealthy_threshold = 3

  tcp_health_check {
    port = 6033
  }
}

# 4. マネージドインスタンスグループ (MIG: e2-micro, 2ゾーン配置, オートスケーリング管理)
resource "google_compute_region_instance_group_manager" "proxysql_mig" {
  name                      = "proxysql-mig-${var.environment}"
  base_instance_name        = "proxysql"
  region                    = var.region
  distribution_policy_zones = ["${var.region}-a", "${var.region}-c"]

  version {
    instance_template = google_compute_instance_template.proxysql_template.id
  }

  auto_healing_policies {
    health_check      = google_compute_region_health_check.proxysql_health_check.id
    initial_delay_sec = 180
  }

  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 1
    max_unavailable_fixed = 0
  }

  lifecycle {
    ignore_changes = [target_size]
  }
}

# 4.1 ProxySQL リージョンオートスケーラー (通常1台 -> 負荷時最大2台)
resource "google_compute_region_autoscaler" "proxysql_autoscaler" {
  name   = "proxysql-autoscaler-${var.environment}"
  region = var.region
  target = google_compute_region_instance_group_manager.proxysql_mig.id

  autoscaling_policy {
    min_replicas    = var.proxysql_min_replicas
    max_replicas    = var.proxysql_max_replicas
    cooldown_period = 60

    cpu_utilization {
      target = 0.7
    }
  }
}

# 5. ILB リージョンバックエンドサービス (Connection Draining対応)
resource "google_compute_region_backend_service" "proxysql_backend" {
  name                            = "proxysql-backend-${var.environment}"
  region                          = var.region
  protocol                        = "TCP"
  load_balancing_scheme           = "INTERNAL"
  health_checks                   = [google_compute_region_health_check.proxysql_health_check.id]
  connection_draining_timeout_sec = 300 # スケールイン時の既存クエリ切断防止

  backend {
    group          = google_compute_region_instance_group_manager.proxysql_mig.instance_group
    balancing_mode = "CONNECTION"
  }
}

# 6. ILB 転送ルール (Internal Forwarding Rule)
resource "google_compute_forwarding_rule" "proxysql_forwarding_rule" {
  name                  = "proxysql-ilb-forwarding-rule-${var.environment}"
  region                = var.region
  load_balancing_scheme = "INTERNAL"
  backend_service       = google_compute_region_backend_service.proxysql_backend.id
  ports                 = ["6033"]
  network               = google_compute_network.vpc_network.id
  subnetwork            = google_compute_subnetwork.subnet.id
  ip_protocol           = "TCP"
  allow_global_access   = true
}

# 7. ファイアウォールルール: GCP ヘルスチェック許可 (35.191.0.0/16, 130.211.0.0/22)
resource "google_compute_firewall" "allow_proxysql_health_check" {
  name    = "allow-proxysql-health-check-${var.environment}"
  network = google_compute_network.vpc_network.id

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
  target_tags   = ["proxysql"]

  allow {
    protocol = "tcp"
    ports    = ["6032", "6033"]
  }
}

# 8. ファイアウォールルール: 内部 VPC トラフィック許可 (Cloud Run / VPC Connector / Subnet)
resource "google_compute_firewall" "allow_proxysql_internal" {
  name    = "allow-proxysql-internal-${var.environment}"
  network = google_compute_network.vpc_network.id

  source_ranges = ["10.0.0.0/24", "10.8.0.0/28"]
  target_tags   = ["proxysql"]

  allow {
    protocol = "tcp"
    ports    = ["6033"]
  }
}
