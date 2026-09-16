terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # NOTE: 本番運用時は GCS backend に切り替えてステートを安全に管理することを推奨
  # backend "gcs" {
  #   bucket = "realestate-crawler-tfstate-sumifu"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# 必要な Google API サービスの自動有効化
resource "google_project_service" "enabled_services" {
  for_each = toset([
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "compute.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com"
  ])

  service                    = each.key
  disable_dependent_services = false
  disable_on_destroy         = false
}
