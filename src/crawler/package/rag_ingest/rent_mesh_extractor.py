"""全国賃料・需給メッシュデータ抽出およびチャンク化モジュール。"""

import datetime
import hashlib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field


class KenbiyaBlockedException(Exception):
    """健美家（アクセス制限あり）へのアクセスを禁止する例外。"""
    pass


class RentMeshChunk(BaseModel):
    id: str
    source_id: str
    category: str = "statistics"
    kind: str = "fact"
    title: str
    target_types: List[str] = Field(default_factory=lambda: ["一棟アパート", "一棟マンション", "区分マンション", "戸建"])
    region: str
    valid_from: str
    valid_to: str
    url: str
    license: str = "derived_summary"
    summary_only: bool = False
    confidence: float = 0.95
    essence: str
    body_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MeshHtmlToMarkdownExtractor:
    """HTMLから余分なUIノイズを除去し、相場・需給情報をMarkdownおよび構造化チャンクに変換する。"""

    def validate_url(self, url: str) -> None:
        """健美家および禁止ドメインのチェック（末尾ドットも正規化）。"""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if hostname == "kenbiya.com" or hostname.endswith(".kenbiya.com"):
            raise KenbiyaBlockedException(f"Kenbiya access is strictly prohibited: {url}")

    def _convert_table_to_markdown(self, table: Tag) -> List[str]:
        lines: List[str] = []
        rows = table.find_all("tr")
        for i, row in enumerate(rows):
            cols = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            if cols:
                lines.append("| " + " | ".join(cols) + " |")
                if i == 0:
                    lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        if lines:
            lines.append("")
        return lines

    def _convert_element_to_markdown(self, elem: Tag) -> List[str]:
        if elem.name in ["h1", "h2", "h3", "h4"]:
            text = elem.get_text(strip=True)
            if text:
                level = elem.name[1]
                prefix = "#" * int(level) + " "
                return [f"\n{prefix}{text}\n"]
        elif elem.name == "p":
            text = elem.get_text(strip=True)
            if text and len(text) > 5:
                return [f"{text}\n"]
        elif elem.name == "table":
            return self._convert_table_to_markdown(elem)
        elif elem.name in ["section", "article", "div"]:
            # 入れ子要素を再帰的または順次抽出
            nested_lines: List[str] = []
            for child in elem.children:
                if isinstance(child, Tag):
                    nested_lines.extend(self._convert_element_to_markdown(child))
            if nested_lines:
                return nested_lines
            # 子タグがなく直接テキストを持つdiv
            text = elem.get_text(strip=True)
            if text and 20 <= len(text) <= 500:
                return [f"{text}\n"]
        return []

    def _extract_markdown_body(self, soup: BeautifulSoup, raw_title: str) -> str:
        target_container = soup.find("main") or soup.find("article") or soup.find("body") or soup
        markdown_lines: List[str] = []
        if raw_title:
            markdown_lines.append(f"# {raw_title}\n")

        for elem in target_container.children:
            if isinstance(elem, Tag):
                markdown_lines.extend(self._convert_element_to_markdown(elem))

        return "\n".join(markdown_lines).strip()

    def extract(
        self,
        url: str,
        html_content: str,
        prefecture: str,
        city: Optional[str] = None,
        station: Optional[str] = None,
        source_id: str = "market_data",
        valid_days: int = 90
    ) -> RentMeshChunk:
        self.validate_url(url)

        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
            tag.decompose()

        title_tag = soup.find("h1") or soup.find("title")
        raw_title = title_tag.get_text(strip=True) if title_tag else "地域賃料相場・需給動向"

        region_parts = [p for p in [prefecture, city, station] if p]
        region_str = "".join(region_parts)

        body_text = self._extract_markdown_body(soup, raw_title)

        cleaned_summary = re.sub(r"[#|\n\-]", " ", body_text)
        essence = re.sub(r"\s+", " ", cleaned_summary).strip()[:350]

        now = datetime.datetime.now(datetime.timezone.utc)
        valid_from = now.strftime("%Y-%m-%d")
        valid_to = (now + datetime.timedelta(days=valid_days)).strftime("%Y-%m-%d")

        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        chunk_id = f"rent_mesh_{source_id}_{url_hash}_{now.strftime('%Y%m')}"

        return RentMeshChunk(
            id=chunk_id,
            source_id=source_id,
            title=f"{region_str} 賃料相場・需給データ ({now.strftime('%Y年%m月')})",
            region=region_str,
            valid_from=valid_from,
            valid_to=valid_to,
            url=url,
            essence=essence,
            body_text=body_text,
            metadata={
                "prefecture": prefecture,
                "city": city or "",
                "station": station or "",
                "extracted_at": now.isoformat(),
            }
        )
