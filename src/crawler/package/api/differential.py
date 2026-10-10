# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import sync_to_async
from django.utils import timezone


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
        # 新規物件は詳細フェッチ必須
        return True
    db_price = record.get("price")
    db_dt = record.get("updateDateTime") or record.get("inputDateTime")

    # 一覧で価格が取得できており、かつDBの価格と完全一致している場合は即座にスキップ (TTL内)
    if item.price is not None and db_price is not None:
        if item.price != db_price:
            logging.info(f"[Differential Crawl] Price change detected for {item.url}: {db_price} -> {item.price}")
            return True
        # 価格が完全一致している場合: TTL期限切れでなければスキップ確定
        if not _is_ttl_expired(db_dt, now, ttl_days):
            return False

    # 価格が取れない場合でも、TTL有効期間内であれば不要な再フェッチをスキップ
    if _is_ttl_expired(db_dt, now, ttl_days):
        logging.debug(f"[Differential Crawl] TTL expired ({ttl_days}d) for {item.url}. Refreshing.")
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
        logging.info(f"[Differential Crawl] Batch updated updateDateTime for {updated_count} active cached properties.")
    except Exception as ue:
        logging.warning(f"[Differential Crawl] Failed to update updateDateTime for cached properties: {ue}")


async def filter_differential_items(
    items: list[Any],
    model_class: Any,
    ttl_days: int = 30,
    force_full: bool = False,
    enabled: bool = True,
) -> tuple[list[str], list[str]]:
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

        existing_map: dict[str, dict[str, Any]] = await sync_to_async(query_existing)()
    except Exception as e:
        logging.warning(f"[Differential Crawl] Failed to query DB for {model_class}: {e}. Falling back to full crawl.")
        return all_urls, []

    now = timezone.now()
    to_fetch: list[str] = []
    to_skip: list[str] = []

    for item in normalized_items:
        if not item.url:
            continue
        record = existing_map.get(item.url)
        if _should_fetch_item(item, record, now, ttl_days):
            to_fetch.append(item.url)
        else:
            to_skip.append(item.url)

    await _batch_update_cached(model_class, to_skip, now)

    logging.info(
        f"[Differential Crawl] Total: {len(all_urls)} | "
        f"Fetch: {len(to_fetch)} (New/Changed/Expired) | "
        f"Skip: {len(to_skip)} (Cached Active)"
    )

    return to_fetch, to_skip
