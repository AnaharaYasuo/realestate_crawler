# ==============================================================================
# ProxySQL Connection Pooling & Multiplexing Infrastructure (Single Instance)
# ==============================================================================
# 目的: ProxySQL によりデータベース接続のリソース管理を効率化し、
#       バックエンド Cloud SQL が耐えられる上限ギリギリのコネクションを維持・多重化する。
# 構成: 単一 Compute Engine インスタンス (初期値 e2-micro, スケールアップ対応) + 固定内部IP (10.0.0.10)
#       ※ ILB (転送ルール) は固定課金排除のため廃止し、Direct VPC から固定IPへ直結。

# 1. ProxySQL 専用サービスアカウント (最小権限)
resource "google_service_account" "proxysql_sa" {
  account_id   = "proxysql-sa-${var.environment}"
  display_name = "ProxySQL Dedicated Service Account"
  description  = "Service account for ProxySQL Compute Engine instances with minimal required permissions."
}

# 2. ProxySQL 固定内部 IP (ILB不要のダイレクトルーティング用)
resource "google_compute_address" "proxysql_ip" {
  name         = "proxysql-ip-${var.environment}"
  subnetwork   = google_compute_subnetwork.subnet.id
  address_type = "INTERNAL"
  address      = "10.0.0.10"
  region       = var.region
}

# 3. ProxySQL 単一 Compute Engine インスタンス (垂直スケールアップ対応)
#tfsec:ignore:google-compute-disk-encryption-customer-key
#trivy:ignore:AVD-GCP-0034
#trivy:ignore:AVD-GCP-0039
resource "google_compute_instance" "proxysql_instance" {
  # checkov:skip=CKV_GCP_37: "Customer-supplied encryption keys not required for proxy layer"
  # checkov:skip=CKV_GCP_38: "Confidential compute not required for stateless proxy"
  name         = "proxysql-instance-${var.environment}"
  machine_type = var.proxysql_machine_type
  zone         = "${var.region}-a"

  tags = ["proxysql"]

  boot_disk {
    auto_delete = true
    initialize_params {
      image = "debian-cloud/debian-12"
      type  = "pd-standard"
      size  = 10
    }
  }

  network_interface {
    network    = google_compute_network.vpc_network.id
    subnetwork = google_compute_subnetwork.subnet.id
    network_ip = google_compute_address.proxysql_ip.address
    # パブリック外部IPは付与せず、VPC内部専用インスタンスとする
  }

  service_account {
    email  = google_service_account.proxysql_sa.email
    scopes = ["https://www.googleapis.com/auth/logging.write", "https://www.googleapis.com/auth/monitoring.write"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    block-project-ssh-keys = "true"
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
    cat <<'CONFIG' > /etc/proxysql.cnf
    datadir="/var/lib/proxysql"

    admin_variables=
    {
        admin_credentials="admin:${random_password.proxysql_admin_password.result};radmin:${random_password.proxysql_admin_password.result}"
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
        monitor_username="monitor"
        monitor_password="${random_password.db_monitor_password.result}"
        monitor_ping_interval=10000
        monitor_read_only_interval=15000
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
            password="${random_password.db_password.result}"
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

  depends_on = [
    google_sql_database_instance.mysql_instance,
    google_sql_user.monitor_user,
    google_compute_subnetwork.subnet,
    google_compute_address.proxysql_ip
  ]
}

# 4. ファイアウォールルール: 内部 VPC トラフィック許可 (10.0.0.0/24 からの 6033 ポート)
resource "google_compute_firewall" "allow_proxysql_internal" {
  name    = "allow-proxysql-internal-${var.environment}"
  network = google_compute_network.vpc_network.id

  source_ranges = ["10.0.0.0/24"]
  target_tags   = ["proxysql"]

  allow {
    protocol = "tcp"
    ports    = ["6033"]
  }
}
