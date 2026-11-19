from unittest.mock import patch

from package.utils.storage import ObjectStorageManager


def test_storage_backend_auto_selects_gcs_on_port_6033(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("DB_PORT", "6033")
    with patch("package.utils.storage.ObjectStorageManager._ensure_bucket_exists"):
        mgr = ObjectStorageManager()
        assert mgr.backend == "gcs"


def test_storage_backend_defaults_to_minio_on_other_ports(monkeypatch):
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.setenv("DB_PORT", "3306")
    with patch("package.utils.storage.ObjectStorageManager._ensure_bucket_exists"):
        mgr = ObjectStorageManager()
        assert mgr.backend == "minio"
