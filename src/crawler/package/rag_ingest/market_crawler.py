"""全国メッシュ家賃相場・キャップレート収集＆GCSハイブリッドアーカイバ (Issue #1354).

生HTML原本を Cloud Storage (`rag/raw/rent_mesh/`) に保存し、
構造化Markdown/JSONLチャンクを `rag/curated/statistics/` に保存するとともに、
取得台帳 `rag/manifest/rent_mesh_sources.jsonl` を更新する。
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import secrets
import time
from typing import Any

import requests

from package.rag_ingest.rent_mesh_extractor import MeshHtmlToMarkdownExtractor

logger = logging.getLogger(__name__)

DEFAULT_GCS_BUCKET = "realestate-images-sumifu-prod"


class GcsArchiveStorage:
    """Google Cloud Storage へ原本HTML・構造化JSONLを直接保存・参照するアダプタ。"""

    def __init__(self, bucket_name: str | None = None) -> None:
        from google.cloud import storage as gcs_storage

        resolved = (
            bucket_name
            or os.getenv("GCS_BUCKET_NAME")
            or os.getenv("STORAGE_BUCKET")
            or DEFAULT_GCS_BUCKET
        )
        self.bucket_name = resolved
        self.client = gcs_storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        blob = self.bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket_name}/{key}"

    def list_files(self, prefix: str = "") -> list[str]:
        return [b.name for b in self.client.list_blobs(self.bucket, prefix=prefix)]

    def read_bytes(self, key: str) -> bytes:
        return self.bucket.blob(key).download_as_bytes()

DEFAULT_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

META_COMMENT_PREFIX = "<!-- RENT_MESH_META: "
META_COMMENT_SUFFIX = " -->"


def parse_embedded_raw_meta(raw_html: str) -> dict[str, Any]:
    """GCS保存HTML先頭のメタデータコメントを抽出する。"""
    first_line = raw_html.splitlines()[0] if raw_html else ""
    if first_line.startswith(META_COMMENT_PREFIX) and first_line.endswith(META_COMMENT_SUFFIX):
        payload = first_line[len(META_COMMENT_PREFIX):-len(META_COMMENT_SUFFIX)]
        try:
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return {}
    return {}


class MarketDataCrawler:
    """レート制限・健美家除外ガード・GCS二層アーカイブを備えた市場データ収集クライアント。"""

    def __init__(
        self,
        storage_mgr: Any = None,
        min_interval_sec: float = 1.0,
        session: requests.Session | None = None,
    ) -> None:
        self.storage = storage_mgr if storage_mgr is not None else GcsArchiveStorage()
        self.min_interval_sec = max(0.0, float(min_interval_sec))
        self.extractor = MeshHtmlToMarkdownExtractor()
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_BROWSER_HEADERS)
        self._last_request_ts: float = 0.0
        self._rng = secrets.SystemRandom()
        self._manifest_cache: bytes | None = None

    def validate_url(self, url: str) -> None:
        """健美家（kenbiya.com）等の禁止ドメインを検証・遮断する。"""
        self.extractor.validate_url(url)

    def _respect_rate_limit(self) -> None:
        if self.min_interval_sec <= 0.0:
            return
        elapsed = time.monotonic() - self._last_request_ts
        jitter = self._rng.uniform(0.05, 0.35)
        wait_sec = (self.min_interval_sec + jitter) - elapsed
        if wait_sec > 0.0:
            time.sleep(wait_sec)

    def fetch_html(self, url: str, timeout: int = 20) -> str | None:
        """安全検証とレート制限を経て対象URLからHTMLテキストを取得する。"""
        self.validate_url(url)
        self._respect_rate_limit()
        try:
            resp = self.session.get(url, timeout=timeout)
            self._last_request_ts = time.monotonic()
            if resp.status_code != 200:
                logger.warning("MarketDataCrawler non-200 status=%d for %s", resp.status_code, url)
                return None
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.RequestException as exc:
            logger.warning("MarketDataCrawler request failed for %s: %s", url, exc)
            return None

    def _append_manifest(self, entry: dict[str, Any]) -> str:
        manifest_key = "rag/manifest/rent_mesh_sources.jsonl"
        if self._manifest_cache is None:
            existing_files = self.storage.list_files("rag/manifest/")
            if manifest_key in existing_files:
                try:
                    self._manifest_cache = self.storage.read_bytes(manifest_key)
                except (OSError, RuntimeError, KeyError):
                    self._manifest_cache = b""
            else:
                self._manifest_cache = b""
        new_line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
        self._manifest_cache = self._manifest_cache + new_line
        self.storage.upload_bytes(
            data=self._manifest_cache,
            key=manifest_key,
            content_type="application/x-ndjson",
        )
        return manifest_key

    def archive_raw_and_curated_to_gcs(
        self,
        url: str,
        html_content: str,
        source_id: str,
        prefecture: str,
        city: str = "",
        station: str = "",
        building_type: str = "all",
        extracted_count: int = 0,
    ) -> dict[str, str]:
        """生HTML原本および構造化Markdownチャンク・台帳をGCSへ保存する。"""
        self.validate_url(url)
        now = datetime.datetime.now(datetime.UTC)
        ymd = now.strftime("%Y%m%d")
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:14]

        raw_key = f"rag/raw/rent_mesh/source={source_id}/pref={prefecture}/{ymd}/{url_hash}.html"
        meta_obj = {
            "url": url,
            "source_id": source_id,
            "prefecture": prefecture,
            "city": city,
            "station": station,
            "building_type": building_type,
            "fetched_at": now.isoformat(),
        }
        header_comment = f"{META_COMMENT_PREFIX}{json.dumps(meta_obj, ensure_ascii=False)}{META_COMMENT_SUFFIX}\n"
        raw_payload = (header_comment + html_content).encode("utf-8")
        self.storage.upload_bytes(data=raw_payload, key=raw_key, content_type="text/html; charset=utf-8")

        chunk = self.extractor.extract(
            url=url,
            html_content=html_content,
            prefecture=prefecture,
            city=city or None,
            station=station or None,
            source_id=source_id,
        )
        chunk.metadata["building_type"] = building_type
        chunk.metadata["extracted_count"] = extracted_count
        chunk.metadata["gcs_raw_key"] = raw_key

        curated_key = f"rag/curated/statistics/pref={prefecture}/{chunk.id}.jsonl"
        curated_bytes = (chunk.model_dump_json() + "\n").encode("utf-8")
        self.storage.upload_bytes(data=curated_bytes, key=curated_key, content_type="application/x-ndjson")

        manifest_key = self._append_manifest({
            "url": url,
            "source_id": source_id,
            "prefecture": prefecture,
            "city": city,
            "station": station,
            "building_type": building_type,
            "raw_key": raw_key,
            "curated_key": curated_key,
            "extracted_count": extracted_count,
            "synced_at": now.isoformat(),
        })
        return {
            "raw_key": raw_key,
            "curated_key": curated_key,
            "manifest_key": manifest_key,
        }

    def list_existing_gcs_statistics_inventory(self) -> dict[str, Any]:
        """クラウドストレージ上の既存RAG/統計ファイルを棚卸し分類する。"""
        all_keys = self.storage.list_files("rag/")
        law_keys = [k for k in all_keys if k.startswith("rag/curated/law/")]
        raw_mesh_keys = [k for k in all_keys if k.startswith("rag/raw/rent_mesh/")]
        stat_keys = [k for k in all_keys if k.startswith("rag/curated/statistics/")]
        blog_keys = [k for k in all_keys if "danchou" in k]
        return {
            "total_rag_blobs": len(all_keys),
            "law_count": len(law_keys),
            "danchou_blog_count": len(blog_keys),
            "rent_mesh_raw_count": len(raw_mesh_keys),
            "statistics_curated_count": len(stat_keys),
            "has_manifest": "rag/manifest/rent_mesh_sources.jsonl" in all_keys,
        }
