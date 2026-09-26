"""
オブジェクトストレージ (MinIO / GCS 互換) 操作用ユーティリティ
将来的な Google Cloud (Cloud Storage) 移管を見据え、
S3/GCS互換のMinIOオブジェクトストレージへ画像をアップロード・管理するインターフェースを提供します。
"""
import json
import logging
import os

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)


def _load_gcs_storage():
    """Lazy-import google.cloud.storage so MinIO-only environments stay bootable."""
    from google.cloud import storage as gcs_storage

    return gcs_storage


class ObjectStorageManager:
    def __init__(self):
        self.backend = os.getenv("STORAGE_BACKEND", "minio").lower()
        self.bucket_name = os.getenv("STORAGE_BUCKET", "realestate-images")
        self.endpoint_url = os.getenv("STORAGE_ENDPOINT", "http://minio:9000")
        self.access_key = os.getenv("STORAGE_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("STORAGE_SECRET_KEY", "minioadmin")

        is_cloud_enabled = os.getenv("IS_CLOUD", "").strip().lower() in ("true", "1")
        has_endpoint = bool(os.getenv("STORAGE_ENDPOINT", "").strip())
        if self.backend == "gcs" or (is_cloud_enabled and not has_endpoint):
            self.is_gcs = True
            gcs_storage = _load_gcs_storage()
            self.gcs_client = gcs_storage.Client()
            self.gcs_bucket = self.gcs_client.bucket(self.bucket_name)
            self.s3_client = None
        else:
            self.is_gcs = False
            self.gcs_client = None
            self.gcs_bucket = None
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                config=Config(signature_version='s3v4'),
                region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
            )
            self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """
        指定されたバケットが存在するか確認し、存在しない場合は自動で新規作成します。
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket '{self.bucket_name}' already exists.")
        except Exception:  # noqa: BLE001
            try:
                # 公開読み取りポリシーを設定
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PublicRead",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{self.bucket_name}/*"]
                        }
                    ]
                }
                self.s3_client.put_bucket_policy(Bucket=self.bucket_name, Policy=json.dumps(policy))
                logger.info(f"Successfully created bucket '{self.bucket_name}' with public-read policy.")
            except Exception:
                logger.exception("Failed to create bucket '%s'", self.bucket_name)

    def upload_image_bytes(self, image_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
        """
        画像のバイナリデータをオブジェクトストレージにアップロードし、アクセス可能なURLを返します。
        
        :param image_bytes: 画像のバイナリ
        :param filename: 保存するファイル名 (一意なキー)
        :param content_type: MimeType
        :return: 保存先URL
        """
        if self.is_gcs:
            try:
                blob = self.gcs_bucket.blob(filename)
                blob.upload_from_string(image_bytes, content_type=content_type)
                public_url = f"https://storage.googleapis.com/{self.bucket_name}/{filename}"
                logger.info("Successfully uploaded image to GCS: %s", public_url)
                return public_url
            except Exception:
                logger.exception("Failed to upload image '%s' to GCS", filename)
                raise
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=image_bytes,
                ContentType=content_type
            )
            # ローカル開発環境(MinIO)の場合は、コンテナ外(localhost)から参照できるよう、
            # エンドポイントのホストをlocalhostに置換してURLを返します。
            # 本番GCS移行時はこの置換ロジックは不要（または環境変数で調整）
            url_host = self.endpoint_url
            if "minio:9000" in url_host:
                url_host = url_host.replace("minio:9000", "localhost:9000")
                
            public_url = f"{url_host}/{self.bucket_name}/{filename}"
            logger.info("Successfully uploaded image to storage: %s", public_url)
            return public_url
        except Exception:
            logger.exception("Failed to upload image '%s' to storage", filename)
            raise

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/json") -> str:
        """
        任意のバイト列をストレージにアップロードし、参照パスまたはURLを返します。
        """
        if self.is_gcs:
            try:
                blob = self.gcs_bucket.blob(key)
                blob.upload_from_string(data, content_type=content_type)
                gcs_path = f"gs://{self.bucket_name}/{key}"
                logger.info("Successfully uploaded bytes to GCS: %s", gcs_path)
                return gcs_path
            except Exception:
                logger.exception("Failed to upload bytes '%s' to GCS", key)
                raise
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type
            )
            gcs_path = f"gs://{self.bucket_name}/{key}"
            logger.info("Successfully uploaded bytes to storage: %s", gcs_path)
            return gcs_path
        except Exception:
            logger.exception("Failed to upload bytes '%s' to storage", key)
            raise

    def list_files(self, prefix: str) -> list:
        """
        指定したプレフィックスに一致するオブジェクトキー一覧を取得します。
        """
        if self.is_gcs:
            try:
                blobs = self.gcs_client.list_blobs(self.gcs_bucket, prefix=prefix)
                return [b.name for b in blobs]
            except Exception:
                logger.exception("Failed to list GCS files with prefix '%s'", prefix)
                return []
        keys = []
        continuation_token = None
        try:
            while True:
                kwargs = {
                    "Bucket": self.bucket_name,
                    "Prefix": prefix
                }
                if continuation_token:
                    kwargs["ContinuationToken"] = continuation_token
                response = self.s3_client.list_objects_v2(**kwargs)
                contents = response.get("Contents", [])
                keys.extend([obj["Key"] for obj in contents if "Key" in obj])
                if response.get("IsTruncated"):
                    continuation_token = response.get("NextContinuationToken")
                else:
                    break
            return keys
        except Exception:
            logger.exception("Failed to list files with prefix '%s'", prefix)
            return []

    def read_text(self, key: str) -> str:
        """
        指定したキーのテキストコンテンツを取得します。
        """
        if self.is_gcs:
            try:
                blob = self.gcs_bucket.blob(key)
                return blob.download_as_text(encoding="utf-8")
            except Exception:
                logger.exception("Failed to read GCS text file '%s'", key)
                raise
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            body = response["Body"].read()
            return body.decode("utf-8")
        except Exception:
            logger.exception("Failed to read text file '%s'", key)
            raise

_storage_manager = None

def get_storage_manager() -> ObjectStorageManager:
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = ObjectStorageManager()
    return _storage_manager
