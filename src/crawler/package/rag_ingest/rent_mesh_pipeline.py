"""全国賃料・需給メッシュのRAGパイプライン統合マネージャー。"""

import logging
from typing import Optional
from package.rag_ingest.rent_mesh_extractor import (
    MeshHtmlToMarkdownExtractor,
    RentMeshChunk,
    KenbiyaBlockedException,
)
from package.utils.storage import ObjectStorageManager

logger = logging.getLogger(__name__)


class RentMeshPipeline:
    def __init__(self, storage_mgr: Optional[ObjectStorageManager] = None):
        self.storage = storage_mgr or ObjectStorageManager()
        self.extractor = MeshHtmlToMarkdownExtractor()

    def process_page(
        self,
        url: str,
        html_content: str,
        prefecture: str,
        city: Optional[str] = None,
        station: Optional[str] = None,
        source_id: str = "market_data",
        archive_raw_html: bool = False,
    ) -> Optional[RentMeshChunk]:
        """ページHTMLを安全に抽出し、チャンク化（健美家は自動除外）。"""
        try:
            chunk = self.extractor.extract(
                url=url,
                html_content=html_content,
                prefecture=prefecture,
                city=city,
                station=station,
                source_id=source_id,
            )
        except KenbiyaBlockedException as e:
            logger.warning("Blocked URL bypassed safely: %s", e)
            return None

        if archive_raw_html and self.storage:
            try:
                raw_path = f"rag/raw/rent_mesh/source={source_id}/pref={prefecture}/{chunk.id}.html"
                self.storage.upload_bytes(
                    data=html_content.encode("utf-8"),
                    key=raw_path,
                    content_type="text/html; charset=utf-8",
                )
            except Exception:
                logger.exception("Failed to archive raw HTML for %s", url)

        return chunk

    def upload_chunk_to_gcs(self, chunk: RentMeshChunk) -> str:
        """
        構造化チャンクを GCS の rag/curated/statistics/ 配下に保存。
        上書きによる既存メッシュ損失を防ぐため、チャンク固有のIDプレフィックス付きで保存。
        """
        pref = chunk.metadata.get("prefecture", "japan")
        curated_blob = f"rag/curated/statistics/pref={pref}/{chunk.id}.jsonl"

        jsonl_line = chunk.model_dump_json() + "\n"
        return self.storage.upload_bytes(
            data=jsonl_line.encode("utf-8"),
            key=curated_blob,
            content_type="application/x-ndjson",
        )
