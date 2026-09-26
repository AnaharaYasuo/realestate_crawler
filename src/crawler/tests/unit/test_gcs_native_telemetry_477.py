from unittest.mock import MagicMock, patch

import setup_env  # noqa: F401
from package.api.api import _sync_save_error_html_by_url
from package.utils.storage import ObjectStorageManager


class TestGcsNativeTelemetry477:
    """Issue #477: Tests for native GCS client in ObjectStorageManager and direct HTML preservation."""

    def test_object_storage_manager_initializes_gcs_when_configured(self, monkeypatch):
        """When STORAGE_BACKEND=gcs, ObjectStorageManager uses google.cloud.storage.Client."""
        monkeypatch.setenv("STORAGE_BACKEND", "gcs")
        monkeypatch.setenv("STORAGE_BUCKET", "test-gcs-bucket")

        mock_gcs_client_cls = MagicMock()
        mock_client_inst = MagicMock()
        mock_gcs_client_cls.return_value = mock_client_inst
        mock_bucket = MagicMock()
        mock_client_inst.bucket.return_value = mock_bucket

        with patch("google.cloud.storage.Client", mock_gcs_client_cls):
            sm = ObjectStorageManager()
            assert sm.is_gcs is True
            assert sm.bucket_name == "test-gcs-bucket"
            mock_client_inst.bucket.assert_called_once_with("test-gcs-bucket")

    def test_object_storage_manager_gcs_upload_and_read(self, monkeypatch):
        """Test upload_bytes, list_files, and read_text using GCS backend."""
        monkeypatch.setenv("STORAGE_BACKEND", "gcs")
        monkeypatch.setenv("STORAGE_BUCKET", "test-gcs-bucket")

        mock_gcs_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_blob.download_as_text.return_value = '{"status": "ok"}'

        mock_blob_item1 = MagicMock()
        mock_blob_item1.name = "runs/20260926/failures/nomura_mansion.json"
        mock_gcs_client.list_blobs.return_value = [mock_blob_item1]

        with patch("google.cloud.storage.Client", return_value=mock_gcs_client):
            mock_gcs_client.bucket.return_value = mock_bucket
            sm = ObjectStorageManager()

            # 1. upload_bytes
            res_path = sm.upload_bytes(b'{"status": "failed"}', "runs/20260926/failures/nomura_mansion.json")
            assert res_path == "gs://test-gcs-bucket/runs/20260926/failures/nomura_mansion.json"
            mock_bucket.blob.assert_called_with("runs/20260926/failures/nomura_mansion.json")
            mock_blob.upload_from_string.assert_called_once_with(
                b'{"status": "failed"}', content_type="application/json"
            )

            # 2. list_files
            files = sm.list_files("runs/20260926/failures/")
            assert len(files) == 1
            assert files[0] == "runs/20260926/failures/nomura_mansion.json"

            # 3. read_text
            content = sm.read_text("runs/20260926/failures/nomura_mansion.json")
            assert content == '{"status": "ok"}'
            mock_blob.download_as_text.assert_called_once_with(encoding="utf-8")

    def test_object_storage_manager_gcs_upload_image_bytes(self, monkeypatch):
        """Test upload_image_bytes returns valid public Google Cloud Storage URL."""
        monkeypatch.setenv("STORAGE_BACKEND", "gcs")
        monkeypatch.setenv("STORAGE_BUCKET", "realestate-images-sumifu-prod")

        mock_gcs_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        with patch("google.cloud.storage.Client", return_value=mock_gcs_client):
            mock_gcs_client.bucket.return_value = mock_bucket
            sm = ObjectStorageManager()

            img_url = sm.upload_image_bytes(b"\xff\xd8\xff\xe0dummy", "nomura/mansion/prop1_0.jpg")
            assert img_url == "https://storage.googleapis.com/realestate-images-sumifu-prod/nomura/mansion/prop1_0.jpg"
            mock_blob.upload_from_string.assert_called_once_with(
                b"\xff\xd8\xff\xe0dummy", content_type="image/jpeg"
            )

    def test_object_storage_manager_minio_operations(self, monkeypatch):
        """Test MinIO/boto3 operations when STORAGE_BACKEND is minio."""
        monkeypatch.setenv("STORAGE_BACKEND", "minio")
        monkeypatch.setenv("STORAGE_BUCKET", "realestate-images")
        monkeypatch.setenv("STORAGE_ENDPOINT", "http://minio:9000")
        monkeypatch.delenv("IS_CLOUD", raising=False)

        mock_boto = MagicMock()
        mock_body = MagicMock()
        mock_body.read.return_value = b"sample text content"
        mock_boto.get_object.return_value = {"Body": mock_body}
        mock_boto.list_objects_v2.return_value = {
            "Contents": [{"Key": "sample1.json"}, {"Key": "sample2.json"}],
            "IsTruncated": False,
        }

        with patch("boto3.client", return_value=mock_boto):
            sm = ObjectStorageManager()
            assert sm.is_gcs is False
            assert sm.s3_client == mock_boto

            # 1. upload_image_bytes
            img_url = sm.upload_image_bytes(b"dummy_img", "prop.jpg")
            assert img_url == "http://localhost:9000/realestate-images/prop.jpg"

            # 2. upload_bytes
            byte_res = sm.upload_bytes(b"data", "test.json")
            assert byte_res == "gs://realestate-images/test.json"

            # 3. list_files
            files = sm.list_files("prefix/")
            assert files == ["sample1.json", "sample2.json"]

            # 4. read_text
            text = sm.read_text("test.json")
            assert text == "sample text content"

    def test_get_storage_manager_singleton(self, monkeypatch):
        """Test get_storage_manager returns the cached singleton instance."""
        import package.utils.storage as storage_mod
        storage_mod._storage_manager = None

        monkeypatch.setenv("STORAGE_BACKEND", "gcs")
        mock_gcs = MagicMock()
        with patch("google.cloud.storage.Client", return_value=mock_gcs):
            sm1 = storage_mod.get_storage_manager()
            sm2 = storage_mod.get_storage_manager()
            assert sm1 is sm2
            assert sm1 is not None

    def test_sync_save_error_html_with_direct_raw_html(self, tmp_path):
        """When raw_html is provided, requests.get must NOT be called."""
        dummy_html = b"<html><head><title>Error</title></head><body>Parse Failed HTML</body></html>"
        url = "https://www.nomu.com/mansion/detail_12345/"

        mock_reporter = MagicMock()
        with (
            patch("package.api.api.ERROR_PAGES_DIR", tmp_path),
            patch("package.api.api.requests.get") as mock_req_get,
            patch("package.api.api.FailureReporter.record_job_failure", mock_reporter)
        ):
            _sync_save_error_html_by_url(
                url=url,
                model_name="NomuraMansion",
                reason="Table not found",
                raw_html=dummy_html
            )

            # requests.get must NOT be invoked since raw_html was provided
            mock_req_get.assert_not_called()

            # Local file must be written
            saved_html = tmp_path / "nomura_mansion" / "12345.html"
            assert saved_html.exists()
            assert saved_html.read_bytes() == dummy_html

            # FailureReporter must be called with raw_html
            mock_reporter.assert_called_once()
            call_kwargs = mock_reporter.call_args.kwargs
            assert call_kwargs["company"] == "nomura"
            assert call_kwargs["property_type"] == "mansion"
            assert call_kwargs["error_message"] == "Table not found"
            assert call_kwargs["target_url"] == url
            assert call_kwargs["raw_html"] == dummy_html

    def test_sync_save_error_html_without_raw_html_fallback(self, tmp_path):
        """When raw_html is None, fallback requests.get is invoked."""
        dummy_content = b"<html><body>Fetched HTML</body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = dummy_content.decode("utf-8")
        mock_resp.content = dummy_content

        mock_reporter = MagicMock()
        with (
            patch("package.api.api.ERROR_PAGES_DIR", tmp_path),
            patch("package.api.api.requests.get", return_value=mock_resp) as mock_req_get,
            patch("package.api.api.FailureReporter.record_job_failure", mock_reporter)
        ):
            _sync_save_error_html_by_url(
                url="https://www.nomu.com/mansion/detail_67890/",
                model_name="NomuraMansion",
                reason="Selector error"
            )

            mock_req_get.assert_called_once()
            saved_html = tmp_path / "nomura_mansion" / "67890.html"
            assert saved_html.exists()
            assert saved_html.read_bytes() == dummy_content
            mock_reporter.assert_called_once()

    def test_sync_save_error_html_handles_request_exception(self, tmp_path):
        """When fallback requests.get fails with timeout/connection error, handles gracefully."""
        mock_reporter = MagicMock()
        with (
            patch("package.api.api.ERROR_PAGES_DIR", tmp_path),
            patch("package.api.api.requests.get", side_effect=TimeoutError("Connection timed out")),
            patch("package.api.api.FailureReporter.record_job_failure", mock_reporter)
        ):
            # Should not raise exception
            _sync_save_error_html_by_url(
                url="https://www.nomu.com/mansion/detail_99999/",
                model_name="NomuraMansion",
                reason="Server timeout"
            )

            # FailureReporter should still be recorded with raw_html=None
            mock_reporter.assert_called_once()
            call_kwargs = mock_reporter.call_args.kwargs
            assert call_kwargs["raw_html"] is None
