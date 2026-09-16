# ==============================================================================
# Legacy Compute Engine & Disks Management (既存GCEリソースのTerraform管理)
# ==============================================================================

# 既存ブートディスク (CentOS 7, 30GB)
resource "google_compute_disk" "legacy_boot_disk" {
  name = "backup2022-02-01"
  type = "pd-standard"
  zone = "us-central1-a"
  size = 30
}

# 既存追加ディスク (MySQLデータ領域, 50GB SSD)
resource "google_compute_disk" "legacy_data_disk" {
  name = "disk-3"
  type = "pd-ssd"
  zone = "us-central1-a"
  size = 50

  labels = {
    purpose = "mysql_data"
  }
}

# 既存レガシーVMインスタンス (現在停止中: TERMINATED)
resource "google_compute_instance" "legacy_vm" {
  name         = "backup2022-02-01"
  machine_type = "e2-micro"
  zone         = "us-central1-a"

  # 停止状態を維持（勝手に起動させない）
  desired_status = "TERMINATED"

  deletion_protection = false

  boot_disk {
    auto_delete = true
    device_name = "instance-2"
    source      = google_compute_disk.legacy_boot_disk.id
  }

  attached_disk {
    source      = google_compute_disk.legacy_data_disk.id
    device_name = "disk-3"
    mode        = "READ_WRITE"
  }

  network_interface {
    network    = "default"
    subnetwork = "default"

    access_config {
      network_tier = "PREMIUM"
    }
  }

  service_account {
    email = "634731722260-compute@developer.gserviceaccount.com"
    scopes = [
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
      "https://www.googleapis.com/auth/service.management.readonly",
      "https://www.googleapis.com/auth/servicecontrol",
      "https://www.googleapis.com/auth/trace.append",
    ]
  }

  metadata = {
    enable-osconfig = "TRUE"
  }

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    preemptible         = false
    provisioning_model  = "STANDARD"
  }

  labels = {
    goog-ops-agent-policy = "v2-x86-template-1-1-0"
  }
}

# ==============================================================================
# Terraform 1.5+ Import Blocks (既存クラウド実リソースの自動インポート宣言)
# ==============================================================================
import {
  id = "projects/sumifu/zones/us-central1-a/disks/backup2022-02-01"
  to = google_compute_disk.legacy_boot_disk
}

import {
  id = "projects/sumifu/zones/us-central1-a/disks/disk-3"
  to = google_compute_disk.legacy_data_disk
}

import {
  id = "projects/sumifu/zones/us-central1-a/instances/backup2022-02-01"
  to = google_compute_instance.legacy_vm
}
