"""Replay saved crawl error pages through production parsers to find unresolved failures."""
import asyncio
import collections
import json
import logging
import os
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from package.parser.baseParser import ParserBase
from package.utils.failure_reporter import html_meta_key
from package.utils.storage import get_storage_manager
from package.utils.url_router import UrlRouter

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_INVALID = "invalid"
STATUS_PARSE_ERROR = "parse_error"
STATUS_NO_URL = "no_url"
STATUS_NO_PARSER = "no_parser"

_ROUTER_PROPERTY_TYPES = {
    "mansion": "mansion",
    "kodate": "kodate",
    "tochi": "tochi",
    "investment_apartment": "apartment",
    "invest_apartment": "apartment",
}
_URL_SOURCES = (("meta[property='og:url']", "content"), ("link[rel='canonical']", "href"))
_MAX_SAMPLES = 5
_VALUE_PREVIEW_LEN = 80
_ERROR_PREVIEW_LEN = 500


def _result(url: str | None, status: str, invalid_fields: dict | None = None, error: str = "") -> dict[str, Any]:
    return {"url": url, "status": status, "invalid_fields": invalid_fields or {}, "error": error}


class ErrorPageReplayer:
    """障害テレメトリに保存されたエラー HTML を既存パーサーで再パースし、未修正障害を特定する"""

    @staticmethod
    def extract_page_url(html_bytes: bytes) -> str | None:
        soup = ParserBase._soup_from_content(html_bytes, None)
        for selector, attr in _URL_SOURCES:
            tag = soup.select_one(selector)
            if tag is None:
                continue
            value = str(tag.get(attr) or "").strip()
            if value.startswith("http"):
                return value
        return None

    @classmethod
    def replay_html(cls, html_bytes: bytes, job_key: str, url: str | None = None) -> dict[str, Any]:
        url = url or cls.extract_page_url(html_bytes)
        if not url:
            return _result(None, STATUS_NO_URL)
        property_type = _ROUTER_PROPERTY_TYPES.get(job_key.partition("_")[2])
        parser = UrlRouter.create_parser(url, property_type=property_type)
        if parser is None:
            return _result(url, STATUS_NO_PARSER)

        async def _saved_content(*_args, **_kwargs) -> bytes:
            await asyncio.sleep(0)
            return html_bytes

        parser._getContent = _saved_content
        parser.save_error_html = lambda *_args, **_kwargs: None
        item = None
        try:
            item = asyncio.run(parser.parsePropertyDetailPage(None, url))
            item.full_clean(validate_unique=False)
        except ValidationError as ve:
            if item is None or not hasattr(ve, "message_dict"):
                return _result(url, STATUS_PARSE_ERROR, error=f"ValidationError: {ve}"[:_ERROR_PREVIEW_LEN])
            invalid = {
                field: {"value": str(getattr(item, field, None))[:_VALUE_PREVIEW_LEN], "errors": list(errors)}
                for field, errors in ve.message_dict.items()
            }
            return _result(url, STATUS_INVALID, invalid_fields=invalid)
        except Exception as e:  # noqa: BLE001
            return _result(url, STATUS_PARSE_ERROR, error=f"{type(e).__name__}: {e}"[:_ERROR_PREVIEW_LEN])
        return _result(url, STATUS_OK)

    @staticmethod
    def _job_of(key: str) -> str:
        return Path(key).parent.name

    @classmethod
    def _collect_objects(cls, date_str: str, job_key: str | None) -> tuple[dict[str, Any], str | None]:
        """Return {key: loader} for error HTML and sidecar meta from storage and local fallback."""
        prefix = f"runs/{date_str}/error_pages/"
        objects: dict[str, Any] = {}
        storage_error = None
        try:
            sm = get_storage_manager()
            for key in sm.list_files(prefix=prefix):
                objects[key] = lambda k=key: sm.read_bytes(k)
        except Exception as se:  # noqa: BLE001
            storage_error = str(se)
            logger.warning("Failed to list error pages from storage, relying on local fallback: %s", se)

        local_root = Path(os.getenv("STORAGE_LOCAL_FALLBACK_DIR", "logs"))
        local_dir = local_root / prefix
        if local_dir.exists():
            for path in sorted(local_dir.glob("*/*")):
                objects.setdefault(path.relative_to(local_root).as_posix(), path.read_bytes)

        if job_key:
            objects = {k: v for k, v in objects.items() if cls._job_of(k) == job_key}
        return objects, storage_error

    @staticmethod
    def _meta_url(objects: dict[str, Any], html_key: str) -> str | None:
        loader = objects.get(html_meta_key(html_key))
        if loader is None:
            return None
        try:
            return json.loads(loader()).get("target_url") or None
        except Exception as me:  # noqa: BLE001
            logger.warning("Failed to read error page meta for %s: %s", html_key, me)
            return None

    @classmethod
    def replay_date(cls, date_str: str, job_key: str | None = None) -> dict[str, Any]:
        objects, storage_error = cls._collect_objects(date_str, job_key)
        jobs: dict[str, dict[str, Any]] = {}
        for key in sorted(k for k in objects if k.endswith(".html")):
            try:
                html_bytes = objects[key]()
            except Exception as read_err:  # noqa: BLE001
                logger.warning("Failed to read error page %s: %s", key, read_err)
                continue
            job = cls._job_of(key)
            res = cls.replay_html(html_bytes, job, url=cls._meta_url(objects, key))
            summary = jobs.setdefault(job, {
                "total": 0,
                "status_counts": collections.Counter(),
                "field_counts": collections.Counter(),
                "samples": [],
            })
            summary["total"] += 1
            summary["status_counts"][res["status"]] += 1
            summary["field_counts"].update(res["invalid_fields"].keys())
            if res["status"] != STATUS_OK and len(summary["samples"]) < _MAX_SAMPLES:
                summary["samples"].append({"html_key": key, **res})

        for summary in jobs.values():
            summary["status_counts"] = dict(summary["status_counts"])
            summary["field_counts"] = dict(summary["field_counts"])
        total = sum(s["total"] for s in jobs.values())
        unresolved = sum(s["total"] - s["status_counts"].get(STATUS_OK, 0) for s in jobs.values())
        return {"total": total, "unresolved": unresolved, "storage_error": storage_error, "jobs": jobs}
