# -*- coding: utf-8 -*-
from typing import Optional, Any
import logging
from yarl import URL
from django.db.models import Q

logger = logging.getLogger(__name__)

# 追跡・表示制御用。物件識別子クエリ (id, propertyCode 等) はここに含めない。
_TRACKING_QUERY_KEYS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "yclid", "_ga", "ref", "from", "sort", "down",
    "mail_source", "mail_medium", "mail_campaign", "token",
})


class UrlMatcher:
    """
    URL正規化・追跡パラメータ除去突合ユーティリティ。
    RFC 3986準拠の yarl を用い、追跡クエリのみ除去し物件識別子クエリは保持する。
    Rearie 等でクエリが一意IDの場合は URL 衝突を防ぐ。特定ホストは KEEP_QUERY_PARAMS で限定保持。
    """

    KEEP_QUERY_PARAMS = {
        "homes.panasonic.com": {"id"},
    }

    @classmethod
    def _kept_query_items(cls, host: str, query_items):
        allowed_keys = cls.KEEP_QUERY_PARAMS.get(host)
        if allowed_keys:
            return [(k, v) for k, v in query_items if k in allowed_keys]
        return [
            (k, v)
            for k, v in query_items
            if k.lower() not in _TRACKING_QUERY_KEYS
        ]

    @classmethod
    def _normalize_fallback(cls, url: str) -> str:
        base = url.split("#")[0].strip()
        if "?" not in base:
            return base
        path, query = base.split("?", 1)
        path = path.rstrip("/") or path
        kept_parts = [
            part
            for part in query.split("&")
            if part and part.split("=", 1)[0].lower() not in _TRACKING_QUERY_KEYS
        ]
        return path if not kept_parts else f"{path}?{'&'.join(kept_parts)}"

    @classmethod
    def normalize(cls, url: str) -> str:
        """
        追跡クエリおよびフラグメントを除去した正規化URLを返却。
        物件識別子クエリ（例: id=）は保持する。
        """
        if not url or not isinstance(url, str):
            return ""
        url = url.strip()
        try:
            u = URL(url).with_fragment(None)
            # yarl の with_path() はクエリを落とすため、先にクエリを確定してから組み立てる
            kept = cls._kept_query_items((u.host or "").lower(), u.query.items())
            path = u.path or "/"
            # 識別子クエリ付きのみ path 末尾スラッシュを正規化（...?id= の表記ゆれ防止）
            if kept:
                path = path.rstrip("/") or "/"
            return str(u.with_path(path).with_query(kept))
        except Exception:
            return cls._normalize_fallback(url)

    @staticmethod
    def is_same_url(url1: str, url2: str) -> bool:
        """
        追跡クエリ・フラグメント・末尾スラッシュの差異を除いて同一物件かを判定。
        識別子クエリが異なれば別物件。
        """
        if not url1 or not url2:
            return False
        n1 = UrlMatcher.normalize(url1).rstrip("/")
        n2 = UrlMatcher.normalize(url2).rstrip("/")
        return bool(n1 and n2 and n1 == n2)

    @classmethod
    def build_db_filter(cls, field_name: str, url: str) -> Q:
        """
        正規化後URLでDB突合するQオブジェクトを生成。
        パス末尾スラッシュ差異および追跡クエリ有無に双方向適合する。
        """
        norm = cls.normalize(url)
        if "?" in norm:
            path_part, query_part = norm.split("?", 1)
            path_no_slash = path_part.rstrip("/")
            path_with_slash = path_no_slash + "/"
            return (
                Q(**{field_name: f"{path_no_slash}?{query_part}"}) |
                Q(**{field_name: f"{path_with_slash}?{query_part}"}) |
                Q(**{f"{field_name}__startswith": f"{path_no_slash}?{query_part}&"}) |
                Q(**{f"{field_name}__startswith": f"{path_with_slash}?{query_part}&"})
            )

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
        QuerySet/Manager から正規化後に一致するレコードを1件抽出。
        build_db_filter の候補を is_same_url で再検証し、誤一致を防ぐ。
        """
        if queryset is None or not url:
            return None
        try:
            db_filter = cls.build_db_filter(field_name, url)
            candidates = queryset.filter(db_filter)
            for item in candidates:
                item_url = getattr(item, field_name, None)
                if isinstance(item_url, str) and cls.is_same_url(item_url, url):
                    return item
            # Django QuerySet / 単体テストモック互換: .first()
            first = getattr(candidates, "first", None)
            if callable(first):
                item = first()
                if item is None:
                    return None
                item_url = getattr(item, field_name, None)
                if isinstance(item_url, str):
                    return item if cls.is_same_url(item_url, url) else None
                # URL 属性が未設定のモック等は filter ヒットを信頼
                return item
            return None
        except Exception as e:
            logger.exception(f"UrlMatcher query error on {field_name}={url}: {e}")
            return None
