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

# Serverless VPC Access Connector (Cloud Run -> VPC)
resource "google_vpc_access_connector" "vpc_connector" {
  name          = "cr-connector-${var.environment}"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc_network.name
  min_instances = 2
  max_instances = 3
  machine_type  = "e2-micro"

  depends_on = [
    google_project_service.enabled_services,
    google_compute_network.vpc_network
  ]
}

# Static External IP for Cloud NAT (固定送信元IPでBotブロック回避)
resource "google_compute_address" "nat_static_ip" {
  name   = "crawler-nat-static-ip-${var.environment}"
  region = var.region
}

# Cloud Router for Cloud NAT
resource "google_compute_router" "router" {
  name    = "realestate-router-${var.environment}"
  region  = var.region
  network = google_compute_network.vpc_network.id
}

# Cloud NAT Gateway (VPC Connector経由の全外部通信を固定IP化)
resource "google_compute_router_nat" "nat_gateway" {
  name                               = "realestate-nat-${var.environment}"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = [google_compute_address.nat_static_ip.self_link]
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}
