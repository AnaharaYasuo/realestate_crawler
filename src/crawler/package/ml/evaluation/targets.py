"""
評価対象モデルおよび未評価物件のストリーミング抽出モジュール (Issue #716, #1160)
"""

import logging
import time
from collections.abc import Iterator
from typing import Any

from django.apps import apps
from django.db import OperationalError, close_old_connections
from package.ml.constants import COMPANIES
from package.utils.crawl_jobs import PORTAL_COMPANIES, UNCRAWLED_COMPANIES

logger = logging.getLogger(__name__)


def get_all_property_models(skip_portals: bool = False, skip_uncrawled: bool = False) -> list[Any]:
    """登録されている全物件モデルを取得"""
    property_models = []
    target_companies = [
        c for c in COMPANIES
        if not (skip_portals and c in PORTAL_COMPANIES)
        and not (skip_uncrawled and c in UNCRAWLED_COMPANIES)
    ]
    app_config = apps.get_app_config("package")
    for model in app_config.get_models():
        model_name = model.__name__.lower()
        if any(model_name.startswith(c) for c in target_companies):
            property_models.append(model)
    return property_models


def _should_skip_item(existing_eval: Any, force: bool) -> bool:
    """スキップ対象物件か判定する (Cognitive Complexity 分散)"""
    if existing_eval and (not getattr(existing_eval, "is_published", True) or getattr(existing_eval, "needs_recrawl", False)):
        return True
    return bool(not force and existing_eval and existing_eval.first_stage_predicted_price is not None)


def iter_active_items(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool = False,
) -> Iterator[tuple[Any, int]]:
    """スキップ判定を通過した物件と、その直前までのスキップ累積数を yield する"""
    skipped_count = 0
    for item in model.objects.all().order_by("pk").iterator(chunk_size=2000):
        page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
        if not page_url:
            continue
        existing_eval = existing_eval_map.get(page_url)
        if _should_skip_item(existing_eval, force):
            skipped_count += 1
            continue
        yield item, skipped_count
        skipped_count = 0


def _is_real_django_model(model: Any) -> bool:
    """本物の Django Model クラスかどうかを判定"""
    from django.db import models
    return isinstance(model, type) and issubclass(model, models.Model)


def _fetch_batch_items_with_retry(
    model: Any,
    last_pk: int,
    fetch_batch_size: int,
    max_retries: int = 3,
) -> list[Any]:
    """OperationalError (2006, 2013, 9001等) 発生時に接続を破棄して再試行するバッチフェッチ (Issue #1160)"""
    for attempt in range(max_retries):
        try:
            close_old_connections()
            return list(model.objects.filter(pk__gt=last_pk).order_by("pk")[:fetch_batch_size])
        except OperationalError as oe:
            close_old_connections()
            if attempt >= max_retries - 1:
                raise
            logger.warning(
                "OperationalError fetching batch for %s (pk>%d, attempt %d/%d): %s. Retrying...",
                getattr(model, "__name__", str(model)),
                last_pk,
                attempt + 1,
                max_retries,
                oe,
            )
            time.sleep(0.1 * (attempt + 1))
    return []


def _iter_target_items(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool,
    fetch_batch_size: int = 2000,
) -> Iterator[tuple[Any | None, int]]:
    """PKベースで未処理対象物件を1件ずつ取得し、(item, skipped_count) を yield する (S3776 分散)"""
    last_pk = 0
    while True:
        batch_items = _fetch_batch_items_with_retry(model, last_pk, fetch_batch_size)
        if not batch_items:
            break

        for item in batch_items:
            last_pk = item.pk
            page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
            if not page_url:
                continue
            if _should_skip_item(existing_eval_map.get(page_url), force):
                yield None, 1
                continue
            yield item, 0


def iter_unprocessed_chunks(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool = False,
    limit: int | None = None,
    chunk_size: int = 1000,
) -> Iterator[tuple[list[Any], int]]:
    """未処理物件を走査し、chunk_size 単位でストリーミング yield する。

    全件 list 化を行わず、同時にメモリ保持する物件数を fetch_batch_size 以下に抑制する。
    本物の Django モデルでは PK ベースのバッチクエリにより、QuerySet カーソルオープン中の
    不正な切断を防ぎ、バッチ境界で安全に close_old_connections() を呼んで DB アイドルタイムアウト
    (OperationalError 2006: MySQL server has gone away) を物理的に根絶する (Issue #909, #1160)。
    Yields:
        (chunk_items, skipped_count_in_this_yield)
    """
    close_old_connections()
    current_chunk: list[Any] = []
    chunk_skipped = 0
    yielded_total = 0

    if _is_real_django_model(model):
        source_iterator = _iter_target_items(model, existing_eval_map, force)
    else:
        source_iterator = iter_active_items(model, existing_eval_map, force)

    for item, skp in source_iterator:
        chunk_skipped += skp
        if item is None:
            continue

        current_chunk.append(item)
        target_size = min(chunk_size, limit - yielded_total) if limit is not None else chunk_size
        if len(current_chunk) >= target_size:
            yield current_chunk, chunk_skipped
            yielded_total += len(current_chunk)
            current_chunk = []
            chunk_skipped = 0
            close_old_connections()
            if limit is not None and yielded_total >= limit:
                return

    if current_chunk:
        yield current_chunk, chunk_skipped
        close_old_connections()
