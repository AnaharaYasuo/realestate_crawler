# -*- coding: utf-8 -*-
"""UrlMatcher: 追跡パラメータ除去と物件識別子クエリ保持の単体テスト (Issue #317)"""
from unittest.mock import MagicMock

from django.db.models import Q

from package.utils.url_matcher import UrlMatcher


def test_normalize_strips_tracking_params_but_keeps_identity_id():
    raw = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=33874&utm_source=mail"
    normalized = UrlMatcher.normalize(raw)
    assert "id=33874" in normalized
    assert "utm_source" not in normalized
    assert "#" not in normalized


def test_normalize_distinguishes_different_identity_ids():
    u1 = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=33874"
    u2 = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=33555"
    assert UrlMatcher.normalize(u1) != UrlMatcher.normalize(u2)
    assert not UrlMatcher.is_same_url(u1, u2)


def test_is_same_url_ignores_tracking_only_differences():
    u1 = "https://www.kenbiya.com/pp2/s/tokyo/re_123/"
    u2 = "https://www.kenbiya.com/pp2/s/tokyo/re_123/?utm_source=newmail&utm_medium=email"
    assert UrlMatcher.is_same_url(u1, u2)


def test_normalize_path_only_urls_unchanged_semantically():
    u = "https://www.odakyu-chukai.com/detail/B01419-001363/"
    assert UrlMatcher.normalize(u).rstrip("/") == u.rstrip("/")


def test_normalize_strips_trailing_slash_before_query():
    with_slash = "https://homes.panasonic.com/rearie/buy/property/land/detail/?id=33874"
    without_slash = "https://homes.panasonic.com/rearie/buy/property/land/detail?id=33874"
    assert UrlMatcher.normalize(with_slash) == UrlMatcher.normalize(without_slash)
    assert UrlMatcher.is_same_url(with_slash, without_slash)


def test_normalize_fallback_keeps_identity_query():
    raw = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=1&utm_source=x#frag"
    assert UrlMatcher._normalize_fallback(raw) == (
        "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=1"
    )


def test_build_db_filter_for_identity_query_covers_slash_variants():
    path_no = "https://homes.panasonic.com/rearie/buy/property/land/detail.html"
    path_yes = path_no + "/"
    q = UrlMatcher.build_db_filter("pageUrl", f"{path_no}?id=33874")
    assert isinstance(q, Q)

    def _flatten(node):
        pairs = []
        for child in node.children:
            if isinstance(child, Q):
                pairs.extend(_flatten(child))
            else:
                pairs.append(child)
        return pairs

    pairs = _flatten(q)
    assert ("pageUrl", f"{path_no}?id=33874") in pairs
    assert ("pageUrl", f"{path_yes}?id=33874") in pairs
    assert ("pageUrl__startswith", f"{path_no}?id=33874&") in pairs
    assert ("pageUrl__startswith", f"{path_yes}?id=33874&") in pairs
    # 追跡パラメータが先頭のDB値用（この2つが無いと回帰する）
    assert ("pageUrl__startswith", f"{path_no}?") in pairs
    assert ("pageUrl__startswith", f"{path_yes}?") in pairs


def test_find_match_when_db_has_tracking_before_identity():
    """DBが ?utm...&id= でもリクエスト ?id= と is_same_url で一致する。"""
    db_url = (
        "https://homes.panasonic.com/rearie/buy/property/land/detail.html"
        "?utm_source=mail&id=33874"
    )
    req = "https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=33874"
    match = MagicMock(pageUrl=db_url)
    other = MagicMock(pageUrl="https://homes.panasonic.com/rearie/buy/property/land/detail.html?id=99999")

    class RecordingQuerySet:
        def __init__(self, rows):
            self._rows = rows
            self.last_q = None

        def filter(self, *args, **kwargs):
            self.last_q = args[0] if args else kwargs
            # 簡略: startswith path? があれば utm 先頭レコードを候補に含める
            path_prefix = (
                "https://homes.panasonic.com/rearie/buy/property/land/detail.html?"
            )
            q = self.last_q
            pairs = []
            if isinstance(q, Q):
                for child in q.children:
                    if isinstance(child, tuple):
                        pairs.append(child)
            has_broad = any(
                k == "pageUrl__startswith" and v == path_prefix for k, v in pairs
            )
            if not has_broad:
                return []
            return [match, other]

    qs = RecordingQuerySet([match, other])
    found = UrlMatcher.find_match_in_queryset(qs, "pageUrl", req)
    assert found is match
    assert UrlMatcher.is_same_url(db_url, req)
    assert isinstance(qs.last_q, Q)


def test_find_match_in_queryset_uses_is_same_url_on_iterable():
    match = MagicMock(pageUrl="https://example.com/a/?utm_source=x")
    other = MagicMock(pageUrl="https://example.com/b/")
    qs = MagicMock()
    qs.filter.return_value = [other, match]
    found = UrlMatcher.find_match_in_queryset(qs, "pageUrl", "https://example.com/a/")
    assert found is match


def test_normalize_empty_and_none():
    assert UrlMatcher.normalize("") == ""
    assert UrlMatcher.normalize(None) == ""  # type: ignore[arg-type]
    assert UrlMatcher.is_same_url("", "https://x/") is False


def test_find_match_in_queryset_first_fallback_without_url_attr():
    item = MagicMock(spec=[])
    qs = MagicMock()
    qs.filter.return_value = MagicMock(first=MagicMock(return_value=item))
    # iterable empty: make filter result non-iterable-friendly via first only
    qs.filter.return_value.__iter__ = lambda self: iter(())
    found = UrlMatcher.find_match_in_queryset(qs, "pageUrl", "https://example.com/a/")
    assert found is item


def test_build_db_filter_path_only():
    q = UrlMatcher.build_db_filter("pageUrl", "https://site.example/detail/1/")
    assert "detail/1" in str(q)


def test_has_numeric_yield_markers_without_regex():
    from package.utils.property_type_detector import PropertyTypeDetector

    assert PropertyTypeDetector._has_numeric_yield("想定年収: 120") is True
    assert PropertyTypeDetector._has_numeric_yield("年間予定賃料＝90") is True
    assert PropertyTypeDetector._has_numeric_yield("利回り: -") is False
    assert PropertyTypeDetector._spec_entry_has_yield("表面利回り", "8.5%") is True
    assert PropertyTypeDetector._spec_entry_has_yield("表面利回り", "未定") is False
    assert PropertyTypeDetector._spec_entry_has_yield("想定年収", "120万円") is True
    assert PropertyTypeDetector.detect(specs={"想定年収": "120万円"}) == "apartment"
