# VPC Network
resource "google_compute_network" "vpc_network" {
  name                    = "realestate-vpc-${var.environment}"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.enabled_services]
}

# Subnet for general resources
resource "google_compute_subnetwork" "subnet" {
  name                     = "realestate-subnet-${var.environment}"
  ip_cidr_range            = "10.0.0.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc_network.id
  private_ip_google_access = true

  log_config {
    aggregation_interval = "INTERVAL_10_MIN"
    flow_sampling        = 0.1 # コスト最適化のためサンプリング間引き (0.5 -> 0.1)
    metadata             = "INCLUDE_ALL_METADATA"
  }
}


# Cloud NAT 撤廃 (Issue #673):
# 全対象サイトにおいて Google 動的 IP でのアクセス・パース疎通性を実証したため、
# Cloud NAT ゲートウェイ (realestate-nat) および静的外部 IP (crawler-nat-static-ip) は撤廃済み。
# 各 Cloud Run / Jobs は PRIVATE_RANGES_ONLY により DB 通信のみ VPC 経由とし、
# 外部通信は直接インターネットへ抜けることで固定維持費 (月約$35-$40) を完全削減。

# Google IAP から ProxySQL へのインバウンド接続許可 (Issue #857: ローカル Docker クローラー安全接続用)
# Google IAP 専用 IP ブロック (35.235.240.0/20) から ProxySQL ポート 6033 および SSH 22 への通信を許可
resource "google_compute_firewall" "allow_iap_to_proxysql" {
  name        = "allow-iap-to-proxysql-${var.environment}"
  description = "Allow inbound connections from Google Identity-Aware Proxy to ProxySQL instance"
  network     = google_compute_network.vpc_network.id

  allow {
    protocol = "tcp"
    ports    = ["6033", "22"]
  }

  source_ranges = ["35.235.240.0/20"] # Google Cloud IAP の固定予約 CIDR
  target_tags   = ["proxysql"]
}


