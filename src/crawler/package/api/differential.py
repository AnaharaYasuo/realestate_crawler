# -*- coding: utf-8 -*-
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from asgiref.sync import sync_to_async
from django.utils import timezone


@dataclass
class ListItem:
    url: str
    price: Optional[int] = None
    hash_val: Optional[str] = None

    @classmethod
    def from_raw(cls, raw: str | Tuple[Any, ...] | List[Any] | Dict[str, Any] | "ListItem") -> "ListItem":
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


async def filter_differential_items(
    items: List[Any],
    model_class: Any,
    ttl_days: int = 7,
    force_full: bool = False,
    enabled: bool = True,
) -> Tuple[List[str], List[str]]:
    """
    Filter extracted items into:
    - to_fetch: URLs that must be fetched (new, price changed, expired TTL)
    - to_skip: URLs already in DB and unchanged (cached active)
    
    For to_skip URLs, inputDateTime is batch-updated to mark them as actively confirmed.
    """
    if not items:
        return [], []

    normalized_items = [ListItem.from_raw(item) for item in items]
    all_urls = [item.url for item in normalized_items if item.url]

    # If differential crawling is disabled, force full, or no Django model class provided
    if not enabled or force_full or model_class is None:
        return all_urls, []

    # Query DB for existing properties in batch
    try:
        def query_existing():
            qs = model_class.objects.filter(pageUrl__in=all_urls).values(
                "pageUrl", "price", "updateDateTime", "inputDateTime"
            )
            return {row["pageUrl"]: row for row in qs}

        existing_map: Dict[str, Dict[str, Any]] = await sync_to_async(query_existing)()
    except Exception as e:
        logging.warning(f"[Differential Crawl] Failed to query DB for {model_class}: {e}. Falling back to full crawl.")
        return all_urls, []

    now = timezone.now()
    to_fetch: List[str] = []
    to_skip: List[str] = []

    for item in normalized_items:
        url = item.url
        if not url:
            continue

        if url not in existing_map:
            # New property
            to_fetch.append(url)
            continue

        record = existing_map[url]
        db_price = record.get("price")
        db_dt = record.get("updateDateTime") or record.get("inputDateTime")

        # Check price revision if list page provided a price
        if item.price is not None and db_price is not None and item.price != db_price:
            logging.info(f"[Differential Crawl] Price change detected for {url}: {db_price} -> {item.price}")
            to_fetch.append(url)
            continue

        # Check TTL expiration
        if ttl_days > 0 and db_dt:
            # Handle tz-aware vs naive if needed
            dt_cmp = db_dt
            if timezone.is_aware(now) and timezone.is_naive(dt_cmp):
                dt_cmp = timezone.make_aware(dt_cmp)
            elif timezone.is_naive(now) and timezone.is_aware(dt_cmp):
                dt_cmp = timezone.make_naive(dt_cmp)

            if (now - dt_cmp).total_seconds() > ttl_days * 86400:
                logging.debug(f"[Differential Crawl] TTL expired ({ttl_days}d) for {url}. Refreshing.")
                to_fetch.append(url)
                continue

        # Cached and valid
        to_skip.append(url)

    # Batch update updateDateTime for skipped (confirmed active) listings
    if to_skip:
        try:
            def update_active_cached():
                return model_class.objects.filter(pageUrl__in=to_skip).update(
                    updateDateTime=now
                )

            updated_count = await sync_to_async(update_active_cached)()
            logging.info(f"[Differential Crawl] Batch updated updateDateTime for {updated_count} active cached properties.")
        except Exception as ue:
            logging.warning(f"[Differential Crawl] Failed to update updateDateTime for cached properties: {ue}")

    logging.info(
        f"[Differential Crawl] Total: {len(all_urls)} | "
        f"Fetch: {len(to_fetch)} (New/Changed/Expired) | "
        f"Skip: {len(to_skip)} (Cached Active)"
    )

    return to_fetch, to_skip
