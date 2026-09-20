# -*- coding: utf-8 -*-
from typing import Optional, Any
import logging
from yarl import URL
from django.db.models import Q

logger = logging.getLogger(__name__)


class UrlMatcher:
    """
    URL正規化・クエリパラメータ無視突合ユーティリティ
    RFC 3986準拠の yarl ライブラリを利用してURLパラメータやフラグメントを除去し、
    クロール済み物件との確実な同一性判定およびDB照会用Qオブジェクトを提供する。
    """

    @staticmethod
    def normalize(url: str) -> str:
        """
        URLからクエリパラメータおよびフラグメントを除去し、正規化されたベースURLを返却。
        ホスト名やスキームの小文字化、標準ポートの省略を行う。
        """
        if not url or not isinstance(url, str):
            return ""
        url = url.strip()
        try:
            u = URL(url).with_query(None).with_fragment(None)
            return str(u)
        except Exception:
            # yarlでパースできない異常文字が含まれる場合のフォールバック
            return url.split("?")[0].split("#")[0].strip()

    @staticmethod
    def is_same_url(url1: str, url2: str) -> bool:
        """
        2つのURLがクエリパラメータ・フラグメント・末尾スラッシュの差異を除いて
        同一の物件詳細ページを指しているかを判定。
        """
        if not url1 or not url2:
            return False
        n1 = UrlMatcher.normalize(url1).rstrip("/")
        n2 = UrlMatcher.normalize(url2).rstrip("/")
        return bool(n1 and n2 and n1 == n2)

    @staticmethod
    def build_db_filter(field_name: str, url: str) -> Q:
        """
        DB内レコード（クエリ付き/無し/末尾スラッシュ有無）に双方向適合するQオブジェクトを生成。
        例:
          - field == "https://site/prop/1/"
          - field.startswith("https://site/prop/1/?")
          - field == "https://site/prop/1"
          - field.startswith("https://site/prop/1?")
        """
        norm = UrlMatcher.normalize(url)
        norm_no_slash = norm.rstrip("/")
        norm_with_slash = norm_no_slash + "/"

        return (
            Q(**{field_name: norm_with_slash}) |
            Q(**{f"{field_name}__startswith": norm_with_slash + "?"}) |
            Q(**{field_name: norm_no_slash}) |
            Q(**{f"{field_name}__startswith": norm_no_slash + "?"})
        )

    @classmethod
    def find_match_in_queryset(cls, queryset: Any, field_name: str, url: str) -> Optional[Any]:
        """Return the first record whose field matches the URL without its query.

        A database filter narrows the candidates before normalized URLs are
        compared. Query and iteration errors are logged with a traceback and
        treated as no match.
        """
        if queryset is None or not url:
            return None
        try:
            db_filter = cls.build_db_filter(field_name, url)
            candidates = queryset.filter(db_filter)
            for item in candidates:
                item_url = getattr(item, field_name, None)
                if item_url and cls.is_same_url(item_url, url):
                    return item
            return None
        except Exception as e:
            logger.exception(f"UrlMatcher query error on {field_name}={url}: {e}")
            return None


