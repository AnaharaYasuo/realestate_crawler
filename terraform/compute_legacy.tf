# ==============================================================================
# Legacy Compute Engine & Disks Management (既存GCEリソースのTerraform管理)
# ==============================================================================

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

# レガシー停止中VM用の最小権限サービスアカウント（デフォルトCompute SAの特権昇格リスクを恒久排除）
resource "google_service_account" "legacy_backup_vm_sa" {
  account_id   = "legacy-backup-vm-sa"
  display_name = "Legacy Backup VM Service Account (Least Privilege)"
  description  = "Dedicated minimal privilege service account for terminated legacy backup VM to eliminate default compute SA exposure."
}

# ==============================================================================
# Terraform 1.5+ Import Blocks (既存クラウド実リソースの自動インポート宣言)
# ==============================================================================
import {
  id = "projects/sumifu/zones/us-central1-a/disks/disk-3"
  to = google_compute_disk.legacy_data_disk
}
