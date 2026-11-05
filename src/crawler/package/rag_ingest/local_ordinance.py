"""地方自治体の不動産関連条例・規則（Reiki-Base等）の取得および条単位チャンク化。

公共データ（条例・規則）。著作権法第13条により権利の目的とならない。
"""
from __future__ import annotations

import logging
import re
import time
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from package.rag_ingest.schema import KnowledgeChunk

logger = logging.getLogger(__name__)

USER_AGENT = "realestate-rag-ingest/1.0"
LICENSE = "地方自治体オープンデータ/条例(著作権法13条対象外)"

YOKOHAMA_BASE = "https://cgi.city.yokohama.lg.jp/somu/reiki/reiki_honbun/"
CHIBA_MENU = "https://www1.g-reiki.net/chiba/reiki_menu.html"
CHIBA_BASE = "https://www1.g-reiki.net/chiba/reiki_honbun/"

YOKOHAMA_KEY_ORDINANCES = {
    "g202RG00000906.html": "横浜市建築基準条例",
    "g202RG00000907.html": "横浜市地区計画の区域内における建築物等の制限に関する条例",
    "g202RG00000908.html": "横浜市特別工業地区建築条例",
    "g202RG00001509.html": "横浜都心機能誘導地区建築条例",
    "g202RG00002076.html": "横浜生活利便機能誘導低層住居地区建築条例",
    "g202RG00001818.html": "横浜市不燃化推進地域における建築物の不燃化の推進に関する条例",
    "g202RG00000910.html": "横浜市建築協定条例",
    "g202RG00000914.html": "横浜市中高層建築物等の建築及び開発事業等に係る住環境の保全等に関する条例",
    "g202RG00002019.html": "横浜市空家等に係る適切な管理、措置等に関する条例",
    "g202RG00000877.html": "横浜市風致地区条例",
    "g202RG00001311.html": "横浜市開発事業等の調整等に関する条例",
    "g202RG00001312.html": "横浜市斜面地における地下室建築物の建築及び開発の制限等に関する条例",
    "g202RG00001472.html": "横浜市地域まちづくり推進条例",
    "g202RG00001506.html": "横浜市魅力ある都市景観の創造に関する条例",
}

CHIBA_KEY_ORDINANCES = {
    "g002RG00000612.html": "千葉市地区計画の区域内における建築物の制限に関する条例",
    "g002RG00000904.html": "千葉市都市計画法に基づく開発行為等の許可の基準に関する条例",
    "g002RG00000619.html": "千葉市中高層建築物の建築に係る紛争の予防と調整に関する条例",
    "g002RG00000816.html": "千葉市新港経済振興地区建築条例",
    "g002RG00001045.html": "千葉市幕張新都心文教地区建築条例",
    "g002RG00001273.html": "千葉市千葉駅東口周辺にぎわい商業業務地区建築条例",
    "g002RG00000597.html": "千葉市都市景観条例",
    "g002RG00000610.html": "千葉市建築協定条例",
    "g002RG00000557.html": "千葉市地区計画等の案の作成手続に関する条例",
    "g002RG00000559.html": "千葉市建築物における駐車施設の附置等に関する条例",
    "g002RG00000562.html": "千葉市開発審査会条例",
    "g002RG00000563.html": "千葉市開発行為等の規制に関する規則",
    "g002RG00000564.html": "千葉市宅地造成及び特定盛土等規制法施行細則",
}


def parse_reiki_base_html(html_text: str, doc_id: str, title: str, url: str, region: str, fetched_at: str) -> list[KnowledgeChunk]:
    soup = BeautifulSoup(html_text, "html.parser")
    p_tags = soup.find_all("p")
    
    chunks: list[KnowledgeChunk] = []
    current_art_num = ""
    current_lines: list[str] = []
    
    art_pattern = re.compile(r'^(第\s*[0-9一二三四五六七八九十百千]+条(?:\s*の\s*[0-9一二三四五六七八九十百千]+)?)\s*(.*)')
    
    def flush_chunk():
        nonlocal current_art_num, current_lines
        if current_art_num and current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                clean_num = current_art_num.replace(" ", "")
                chunk_id = f"ordinance_{region}_{doc_id}_{clean_num}"
                chunks.append(KnowledgeChunk(
                    id=chunk_id,
                    source_id=f"reiki_{region}_{doc_id}",
                    category="law",
                    title=f"{title} {current_art_num}".strip(),
                    url=url,
                    body_text=body,
                    license=LICENSE,
                    fetched_at=fetched_at,
                    region=region,
                    kind="fact",
                    speaker_role="local_ordinance",
                    confidence=1.0,
                    essence=f"{title} {current_art_num}",
                ))
        current_lines = []

    for p in p_tags:
        text = p.get_text().strip()
        if not text:
            continue
        m = art_pattern.match(text)
        if m and "class" in p.attrs and "num" in p.attrs["class"]:
            flush_chunk()
            current_art_num = m.group(1)
            current_lines.append(text)
        elif current_art_num:
            current_lines.append(text)
            
    flush_chunk()
    return chunks


def fetch_and_chunk_yokohama(ordinances: dict[str, str] | None = None, delay: float = 0.5) -> dict[str, list[KnowledgeChunk]]:
    targets = ordinances or YOKOHAMA_KEY_ORDINANCES
    now = datetime.now(UTC).isoformat()
    result: dict[str, list[KnowledgeChunk]] = {}
    
    with requests.Session() as s:
        s.headers.update({"User-Agent": USER_AGENT})
        for fn, title in targets.items():
            doc_id = fn.replace(".html", "")
            url = YOKOHAMA_BASE + fn
            try:
                r = s.get(url, timeout=30)
                r.encoding = r.apparent_encoding
                if r.status_code == 200:
                    chunks = parse_reiki_base_html(
                        html_text=r.text,
                        doc_id=doc_id,
                        title=title,
                        url=url,
                        region="kanagawa_yokohama",
                        fetched_at=now,
                    )
                    result[f"yokohama_{doc_id}"] = chunks
                time.sleep(delay)
            except (requests.RequestException, OSError) as e:
                logger.debug("Yokohama fetch failed for %s: %s", fn, e)
    return result


def fetch_and_chunk_chiba(ordinances: dict[str, str] | None = None, delay: float = 0.5) -> dict[str, list[KnowledgeChunk]]:
    targets = ordinances or CHIBA_KEY_ORDINANCES
    now = datetime.now(UTC).isoformat()
    result: dict[str, list[KnowledgeChunk]] = {}
    
    with requests.Session() as s:
        s.headers.update({"User-Agent": USER_AGENT})
        try:
            s.get(CHIBA_MENU, timeout=20)
        except (requests.RequestException, OSError) as e:
            logger.debug("Chiba menu fetch error: %s", e)
            
        for fn, title in targets.items():
            doc_id = fn.replace(".html", "")
            url = CHIBA_BASE + fn
            try:
                r = s.get(url, timeout=30)
                r.encoding = r.apparent_encoding
                if r.status_code == 200:
                    chunks = parse_reiki_base_html(
                        html_text=r.text,
                        doc_id=doc_id,
                        title=title,
                        url=url,
                        region="chiba_city",
                        fetched_at=now,
                    )
                    result[f"chiba_{doc_id}"] = chunks
                time.sleep(delay)
            except (requests.RequestException, OSError) as e:
                logger.debug("Chiba fetch failed for %s: %s", fn, e)
    return result
