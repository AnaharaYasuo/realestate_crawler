# ==============================================================================
# Legacy Compute Engine & Disks Management (既存GCEリソースのTerraform管理)
# ==============================================================================

# 既存ブートディスク (CentOS 7, 30GB)
#tfsec:ignore:google-compute-disk-encryption-customer-key
#trivy:ignore:AVD-GCP-0034
resource "google_compute_disk" "legacy_boot_disk" {
  # checkov:skip=CKV_GCP_37: "Customer-supplied encryption keys deprecated by Google"
  name = "backup2022-02-01"
  type = "pd-standard"
  zone = "us-central1-a"
  size = 30
}

# 既存追加ディスク (MySQLデータ領域, 50GB SSD)
#tfsec:ignore:google-compute-disk-encryption-customer-key
#trivy:ignore:AVD-GCP-0034
resource "google_compute_disk" "legacy_data_disk" {
  # checkov:skip=CKV_GCP_37: "Customer-supplied encryption keys deprecated by Google"
  name = "disk-3"
  type = "pd-ssd"
  zone = "us-central1-a"
  size = 50

  labels = {
    purpose = "mysql_data"
  }
}

# 既存レガシーVMインスタンス (現在停止中: TERMINATED)
#tfsec:ignore:google-compute-no-default-service-account
#tfsec:ignore:google-compute-disk-encryption-customer-key
#tfsec:ignore:google-compute-enable-shielded-vm-vtpm
#tfsec:ignore:google-compute-enable-shielded-vm-im
#tfsec:ignore:google-compute-enable-shielded-vm-sb
#trivy:ignore:AVD-GCP-0030
#trivy:ignore:AVD-GCP-0033
#trivy:ignore:AVD-GCP-0067
#trivy:ignore:AVD-GCP-0068
#trivy:ignore:AVD-GCP-0069
#trivy:ignore:AVD-GCP-0070
resource "google_compute_instance" "legacy_vm" {
  # checkov:skip=CKV_GCP_41: "Legacy stopped backup VM imported from 2022"
  # checkov:skip=CKV_GCP_38: "Customer-supplied encryption keys deprecated by Google"
  # checkov:skip=CKV_GCP_39: "Legacy CentOS 7 VM is not UEFI-enabled and does not support Shielded VM"
  # checkov:skip=CKV_GCP_40: "Legacy CentOS 7 VM is not UEFI-enabled and does not support Shielded VM"
  name         = "backup2022-02-01"
  machine_type = "e2-micro"
  zone         = "us-central1-a"

  # 停止状態を維持（勝手に起動させない）
  desired_status = "TERMINATED"

  deletion_protection = true

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
    enable-osconfig        = "TRUE"
    enable-oslogin         = "TRUE"
    block-project-ssh-keys = "TRUE"
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
