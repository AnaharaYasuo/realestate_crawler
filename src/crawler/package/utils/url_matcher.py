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
    ただし、Rearie等、クエリパラメータ自体が物件の一意IDを表すサイトでは、
    当該IDパラメータを保護してURL衝突（全物件同一URL上書き）を防止する。
    """

    KEEP_QUERY_PARAMS = {
        "homes.panasonic.com": {"id"},
    }

    @classmethod
    def normalize(cls, url: str) -> str:
        """
        URLから不要なクエリパラメータおよびフラグメントを除去し、正規化されたベースURLを返却。
        ホスト名やスキームの小文字化、標準ポートの省略を行う。
        特定サイトの必須IDパラメータ（Rearie の ?id= 等）は保持する。
        """
        if not url or not isinstance(url, str):
            return ""
        url = url.strip()
        try:
            u = URL(url).with_fragment(None)
            host = (u.host or "").lower()
            allowed_keys = cls.KEEP_QUERY_PARAMS.get(host)
            if allowed_keys:
                clean_query = {k: v for k, v in u.query.items() if k in allowed_keys}
                u = u.with_query(clean_query if clean_query else None)
            else:
                u = u.with_query(None)
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

    @classmethod
    def build_db_filter(cls, field_name: str, url: str) -> Q:
        """
        DB内レコード（クエリ付き/無し/末尾スラッシュ有無）に双方向適合するQオブジェクトを生成。
        例:
          - field == "https://site/prop/1/"
          - field.startswith("https://site/prop/1/?")
          - field == "https://site/prop/1"
          - field.startswith("https://site/prop/1?")
        クエリパラメータ保持サイト（Rearie等）の場合は、正規化された完全URLをそのまま照会。
        """
        norm = cls.normalize(url)
        if "?" in norm:
            return Q(**{field_name: norm}) | Q(**{f"{field_name}__startswith": norm + "&"})

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
        """
        QuerySetからクエリパラメータを無視してURLが一致するレコードを1件抽出。
        DB側のQフィルターで候補を絞り込み、Python側の is_same_url で確実に検証する。
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


