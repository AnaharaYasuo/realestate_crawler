# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
from typing import Any

from asgiref.sync import sync_to_async
from django.utils import timezone

from package.utils.crawler_diagnostics import record_thread_activity
from package.utils.crawler_watchdog import touch_crawler_progress

logger = logging.getLogger(__name__)


class ListItem(str):
    url: str
    price: int | None
    hash_val: str | None

    def __new__(cls, url: str, price: int | None = None, hash_val: str | None = None):
        instance = super().__new__(cls, url)
        instance.url = url
        instance.price = price
        instance.hash_val = hash_val
        return instance

    def __repr__(self) -> str:
        return f"ListItem(url={self.url!r}, price={self.price!r}, hash_val={self.hash_val!r})"

    @classmethod
    def from_raw(cls, raw: str | tuple[Any, ...] | list[Any] | dict[str, Any] | ListItem) -> ListItem:
        if isinstance(raw, ListItem):
            return raw
        if isinstance(raw, str):
            return cls(url=raw)
        if isinstance(raw, (tuple, list)):
            url = raw[0]
            price = raw[1] if len(raw) > 1 else None
            hash_val = raw[2] if len(raw) > 2 else None
            return cls(url=url, price=price, hash_val=hash_val)
        if isinstance(raw, dict):
            return cls(
                url=raw.get("url", ""),
                price=raw.get("price"),
                hash_val=raw.get("hash_val") or raw.get("hash")
            )
        return cls(url=str(raw))


def _is_ttl_expired(db_dt: Any, now: Any, ttl_days: int) -> bool:
    if ttl_days <= 0 or not db_dt:
        return False
    dt_cmp = db_dt
    if timezone.is_aware(now) and timezone.is_naive(dt_cmp):
        dt_cmp = timezone.make_aware(dt_cmp)
    elif timezone.is_naive(now) and timezone.is_aware(dt_cmp):
        dt_cmp = timezone.make_naive(dt_cmp)
    return (now - dt_cmp).total_seconds() > ttl_days * 86400


def _should_fetch_item(item: ListItem, record: dict[str, Any] | None, now: Any, ttl_days: int) -> bool:
    if not record:
        return True
    db_price = record.get("price")
    db_dt = record.get("updateDateTime") or record.get("inputDateTime")

    if item.price is not None and db_price is not None:
        if item.price != db_price:
            logger.info(f"[Differential Crawl] Price change detected for {item.url}: {db_price} -> {item.price}")
            return True
        if not _is_ttl_expired(db_dt, now, ttl_days):
            return False

    if _is_ttl_expired(db_dt, now, ttl_days):
        logger.debug(f"[Differential Crawl] TTL expired ({ttl_days}d) for {item.url}. Refreshing.")
        return True
    return False


async def _batch_update_cached(model_class: Any, to_skip: list[str], now: Any) -> None:
    if not to_skip:
        return
    try:
        def update_active_cached():
            return model_class.objects.filter(pageUrl__in=to_skip).update(
                updateDateTime=now
            )

        updated_count = await sync_to_async(update_active_cached)()
        _touch_differential_progress(model_class)
        logging.info(f"[Differential Crawl] Batch updated updateDateTime for {updated_count} active cached properties.")
    except Exception as ue:
        logging.warning(f"[Differential Crawl] Failed to update updateDateTime for cached properties: {ue}")


def _detect_company_and_type_from_model(model_class):
    """Djangoモデルクラス名から会社名と物件種別を逆引き判定する"""
    if model_class is None:
        return None, None
    name = getattr(model_class, "__name__", "").lower()
    companies = [
        "mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1", "mizuho",
        "odakyu", "afr", "sekisui", "daiwa", "totate", "athome", "homes", "seibu",
        "keikyu", "sotetsu", "keisei", "daikyo", "rearie", "heim", "sumirin", "keio",
        "adcast", "toho", "ietan", "haseko", "kenbiya"
    ]
    comp = None
    for c in sorted(companies, key=len, reverse=True):
        if name.startswith(c):
            comp = c
            break

    ptype_pairs = [
        ("investment_apartment", "invest_apartment"),
        ("investmentapartment", "invest_apartment"),
        ("invest_apartment", "invest_apartment"),
        ("investment_building", "invest_building"),
        ("investmentbuilding", "invest_building"),
        ("invest_building", "invest_building"),
        ("investment_kodate", "invest_kodate"),
        ("investmentkodate", "invest_kodate"),
        ("invest_kodate", "invest_kodate"),
        ("investment", "investment"),
        ("mansion", "mansion"),
        ("kodate", "kodate"),
        ("tochi", "tochi"),
        ("building", "building"),
        ("land", "land"),
    ]
    ptype = None
    for token, canonical in ptype_pairs:
        if token in name:
            ptype = canonical
            break

    return comp, ptype


def _touch_differential_progress(model_class):
    """差分キャッシュスキップ時にウォッチドッグ進捗通知ファイルを更新する"""
    try:
        comp = os.getenv("CRAWLER_JOB_COMPANY")
        ptype = os.getenv("CRAWLER_JOB_TYPE")
        if not (comp and ptype):
            comp, ptype = _detect_company_and_type_from_model(model_class)
        if comp and ptype:
            touch_crawler_progress(str(comp).lower(), str(ptype).lower())
    except Exception:
        pass


DIFFERENTIAL_CHUNK_SIZE: int = 200


def _build_lookup_urls(chunk_urls: list[str]) -> list[str]:
    from package.utils.url_matcher import UrlMatcher

    lookup_url_set: set[str] = set()
    for raw_u in chunk_urls:
        lookup_url_set.add(raw_u)
        norm_u = UrlMatcher.normalize(raw_u)
        if not norm_u:
            continue
        lookup_url_set.add(norm_u)
        base_u = norm_u.rstrip("/")
        if base_u:
            lookup_url_set.add(base_u)
            lookup_url_set.add(base_u + "/")
    return list(lookup_url_set)


def _query_existing_records_sync(model_class: Any, urls: list[str]) -> dict[str, dict[str, Any]]:
    from package.utils.url_matcher import UrlMatcher

    qs = model_class.objects.filter(pageUrl__in=urls).values(
        "pageUrl", "price", "updateDateTime", "inputDateTime"
    )
    res_map: dict[str, dict[str, Any]] = {}
    for row in qs:
        p_url = row["pageUrl"]
        res_map[p_url] = row
        norm_key = UrlMatcher.normalize(p_url).rstrip("/")
        if norm_key and norm_key not in res_map:
            res_map[norm_key] = row
    return res_map


def _partition_chunk_items(
    chunk_items: list[ListItem],
    existing_map: dict[str, dict[str, Any]],
    now: Any,
    ttl_days: int,
) -> tuple[list[str], list[str]]:
    from package.utils.url_matcher import UrlMatcher

    chunk_to_fetch: list[str] = []
    chunk_to_skip: list[str] = []
    for item in chunk_items:
        if not item.url:
            continue
        norm_key = UrlMatcher.normalize(item.url).rstrip("/")
        record = existing_map.get(item.url) or (existing_map.get(norm_key) if norm_key else None)
        if _should_fetch_item(item, record, now, ttl_days):
            chunk_to_fetch.append(item.url)
        else:
            skip_url = record.get("pageUrl") if record else None
            chunk_to_skip.append(skip_url or item.url)
    return chunk_to_fetch, chunk_to_skip


async def _process_differential_chunk(
    chunk_items: list[ListItem],
    model_class: Any,
    now: Any,
    ttl_days: int,
) -> tuple[list[str], list[str]]:
    chunk_urls = [item.url for item in chunk_items if item.url]
    if not chunk_urls:
        return [], []

    record_thread_activity("differential_query", current_url=chunk_urls[0])
    lookup_urls = _build_lookup_urls(chunk_urls)
    try:
        existing_map: dict[str, dict[str, Any]] = await sync_to_async(_query_existing_records_sync)(
            model_class, lookup_urls
        )
    except Exception as e:
        logging.warning(
            f"[Differential Crawl] Failed to query DB for {model_class}: {e}. Falling back to full crawl for chunk."
        )
        return chunk_urls, []

    _touch_differential_progress(model_class)
    chunk_to_fetch, chunk_to_skip = _partition_chunk_items(chunk_items, existing_map, now, ttl_days)
    if chunk_to_skip:
        await _batch_update_cached(model_class, chunk_to_skip, now)
        try:
            from package.utils.job_metrics import record_item_skipped
            record_item_skipped(len(chunk_to_skip))
        except Exception:
            pass

    return chunk_to_fetch, chunk_to_skip


async def filter_differential_items(
    items: list[Any],
    model_class: Any,
    ttl_days: int = 30,
    force_full: bool = False,
    enabled: bool = True,
    chunk_size: int = DIFFERENTIAL_CHUNK_SIZE,
) -> tuple[list[str], list[str]]:
    """
    Filter extracted items into:
    - to_fetch: URLs that must be fetched (new, price changed, expired TTL)
    - to_skip: URLs already in DB and unchanged (cached active)
    
    Processes items in chunks (default 200) to stream updateDateTime updates to DB,
    ensuring continuous progress is visible to crawler watchdogs.
    """
    if not items:
        return [], []

    normalized_items = [ListItem.from_raw(item) for item in items]
    all_urls = [item.url for item in normalized_items if item.url]

    if not enabled or force_full or model_class is None:
        return all_urls, []

    step = max(1, chunk_size)
    all_to_fetch: list[str] = []
    all_to_skip: list[str] = []
    now = timezone.now()

    for i in range(0, len(normalized_items), step):
        chunk_items = normalized_items[i:i + step]
        to_fetch, to_skip = await _process_differential_chunk(chunk_items, model_class, now, ttl_days)
        all_to_fetch.extend(to_fetch)
        all_to_skip.extend(to_skip)

    logging.info(
        f"[Differential Crawl] Total: {len(all_urls)} | "
        f"Fetch: {len(all_to_fetch)} (New/Changed/Expired) | "
        f"Skip: {len(all_to_skip)} (Cached Active)"
    )

    return all_to_fetch, all_to_skip
