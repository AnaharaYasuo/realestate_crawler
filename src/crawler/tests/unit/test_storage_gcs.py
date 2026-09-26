import os
from unittest.mock import MagicMock, patch

from package.utils.storage import ObjectStorageManager


def test_object_storage_manager_gcs_backend():
    with patch.dict(os.environ, {"STORAGE_BACKEND": "gcs", "STORAGE_BUCKET": "test-gcs-bucket"}, clear=False), \
         patch("google.cloud.storage.Client") as mock_gcs_cls:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_gcs_cls.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        mgr = ObjectStorageManager()
        assert mgr.is_gcs is True
        assert mgr.bucket_name == "test-gcs-bucket"

        # Test upload_bytes
        path = mgr.upload_bytes(b"hello world", "test/key.json", "application/json")
        assert path == "gs://test-gcs-bucket/test/key.json"
        mock_bucket.blob.assert_called_with("test/key.json")
        mock_blob.upload_from_string.assert_called_once_with(b"hello world", content_type="application/json")

        # Test upload_image_bytes
        mock_blob.upload_from_string.reset_mock()
        mock_bucket.blob.reset_mock()
        url = mgr.upload_image_bytes(b"image_bytes", "images/pic.jpg", "image/jpeg")
        assert url == "https://storage.googleapis.com/test-gcs-bucket/images/pic.jpg"
        mock_bucket.blob.assert_called_with("images/pic.jpg")
        mock_blob.upload_from_string.assert_called_once_with(b"image_bytes", content_type="image/jpeg")

        # Test list_files
        b1 = MagicMock()
        b1.name = "test/file1.json"
        b2 = MagicMock()
        b2.name = "test/file2.json"
        mock_client.list_blobs.return_value = [b1, b2]
        files = mgr.list_files("test/")
        assert files == ["test/file1.json", "test/file2.json"]
        mock_client.list_blobs.assert_called_once_with(mock_bucket, prefix="test/")

        # Test read_text
        mock_bucket.blob.reset_mock()
        mock_blob.download_as_text.return_value = '{"status": "ok"}'
        text = mgr.read_text("test/key.json")
        assert text == '{"status": "ok"}'
        mock_bucket.blob.assert_called_with("test/key.json")
        mock_blob.download_as_text.assert_called_once()


def test_object_storage_manager_gcs_via_is_cloud():
    env = {
        "IS_CLOUD": "true",
        "STORAGE_BUCKET": "cloud-bucket",
    }
    # Ensure STORAGE_BACKEND / STORAGE_ENDPOINT do not force MinIO
    clear_keys = ["STORAGE_BACKEND", "STORAGE_ENDPOINT"]
    with patch.dict(os.environ, env, clear=False), \
         patch("google.cloud.storage.Client") as mock_gcs_cls:
        for key in clear_keys:
            os.environ.pop(key, None)
        mock_client = MagicMock()
        mock_gcs_cls.return_value = mock_client
        mock_client.bucket.return_value = MagicMock()

        mgr = ObjectStorageManager()
        assert mgr.is_gcs is True
        assert mgr.bucket_name == "cloud-bucket"


def test_object_storage_manager_s3_when_cloud_has_endpoint():
    with patch.dict(
        os.environ,
        {
            "IS_CLOUD": "true",
            "STORAGE_ENDPOINT": "http://minio:9000",
            "STORAGE_BACKEND": "minio",
            "STORAGE_BUCKET": "test-s3-bucket",
        },
        clear=False,
    ), patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        mgr = ObjectStorageManager()
        assert mgr.is_gcs is False
        assert mgr.bucket_name == "test-s3-bucket"
        mock_boto.assert_called_once()
        assert mock_boto.call_args.kwargs.get("endpoint_url") == "http://minio:9000"
    with patch.dict(
        os.environ,
        {"IS_CLOUD": "false", "STORAGE_BACKEND": "minio", "STORAGE_BUCKET": "test-s3-bucket"},
        clear=False,
    ), patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        mgr = ObjectStorageManager()
        assert mgr.is_gcs is False
        assert mgr.bucket_name == "test-s3-bucket"

        # Test upload_bytes
        path = mgr.upload_bytes(b"hello s3", "test/s3.json", "application/json")
        assert path == "gs://test-s3-bucket/test/s3.json"
        mock_s3.put_object.assert_called_once_with(Bucket="test-s3-bucket", Key="test/s3.json", Body=b"hello s3", ContentType="application/json")

        # Test read_text
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"s3 data")}
        text = mgr.read_text("test/s3.json")
        assert text == "s3 data"
        mock_s3.get_object.assert_called_once_with(Bucket="test-s3-bucket", Key="test/s3.json")
