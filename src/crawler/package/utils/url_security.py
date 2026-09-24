# -*- coding: utf-8 -*-
import socket
import ipaddress
import urllib.parse
import aiohttp
import logging
from bs4 import BeautifulSoup

PROPERTY_KEYWORDS = [
    "価格", "販売価格", "物件価格", "専有面積", "建物面積", "土地面積",
    "間取り", "所在地", "築年月", "徒歩", "駅", "構造", "賃料", "総戸数"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
}


def _is_blocked_ip(ip_obj) -> bool:
    return any((ip_obj.is_private, ip_obj.is_loopback, ip_obj.is_link_local, ip_obj.is_reserved, ip_obj.is_multicast))


def _validate_ip_or_dns(hostname: str) -> tuple[bool, str]:
    try:
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if _is_blocked_ip(ip_obj):
                return False, f"Blocked private/loopback/link-local IP address: {hostname} (SSRF Defense)"
            return True, ""
        except ValueError:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                resolved_ip_str = item[4][0]
                ip_obj = ipaddress.ip_address(resolved_ip_str)
                if _is_blocked_ip(ip_obj):
                    return False, f"Blocked domain resolving to private/loopback IP: {hostname} -> {resolved_ip_str} (SSRF Defense)"
            return True, ""
    except socket.gaierror:
        return True, ""
    except Exception as e:
        return False, f"Security validation error: {str(e)}"


class UrlSecurityValidator:
    """
    URL安全性検証およびSSRF防御・到達性判定クラス
    """

    @staticmethod
    def validate_url_security(url: str) -> tuple[bool, str]:
        """
        URLのセキュリティチェック (SSRF / 不正スキーム / ポート / 内部IP遮断)
        Returns:
            (is_safe, error_reason)
        """
        if not url or not isinstance(url, str):
            return False, "URL is empty or invalid"

        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            return False, f"URL parse error: {str(e)}"

        # 1. スキーム検証
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"Invalid scheme '{parsed.scheme}'. Only http and https are allowed."

        # 2. ホスト名検証
        hostname = parsed.hostname
        if not hostname:
            return False, "URL missing hostname"

        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False, "Blocked loopback hostname (SSRF Defense)"

        # 3. ポート検証
        if parsed.port is not None and parsed.port not in (80, 443):
            return False, f"Blocked non-standard port: {parsed.port}. Only ports 80 and 443 are allowed."

        # 4. IPアドレス名前解決 & プライベート/リンクローカル判定
        return _validate_ip_or_dns(hostname)

    @staticmethod
    async def check_property_content_and_reachability(
        url: str,
        timeout_sec: int = 3,
        max_bytes: int = 150000
    ) -> tuple[bool, str, list[str]]:
        """
        未対応URLの到達性チェックおよび不動産コンテンツ判定
        Returns:
            (is_property_page, page_title, matched_keywords)
        """
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_sec)
            async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status >= 400:
                        logging.info(f"Candidate check: HTTP {response.status} for {url}")
                        return False, "", []

                    # Content-Length 上限チェック (2MB)
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > 2 * 1024 * 1024:
                        return False, "File too large", []

                    # 先頭バイトのみ読み出し (巨大レスポンス爆弾対策)
                    raw_content = await response.content.read(max_bytes)
                    encoding = response.charset or "utf-8"
                    try:
                        text = raw_content.decode(encoding, errors="replace")
                    except Exception:
                        text = raw_content.decode("utf-8", errors="replace")

                    soup = BeautifulSoup(text, "html.parser")
                    title = soup.title.string.strip() if soup.title and soup.title.string else ""

                    # 不動産キーワードの出現判定
                    body_text = soup.get_text()
                    matched = [kw for kw in PROPERTY_KEYWORDS if kw in body_text]

                    # 3つ以上の不動産キーワードが含まれていれば物件ページと判定
                    is_property = len(matched) >= 3
                    return is_property, title, matched

        except Exception as e:
            logging.warning(f"Candidate check failed for {url}: {e}")
            return False, "", []
