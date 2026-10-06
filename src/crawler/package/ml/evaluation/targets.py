"""
評価対象モデルおよび未評価物件のストリーミング抽出モジュール (Issue #716)
"""

import logging
from collections.abc import Iterator
from typing import Any

from django.apps import apps
from package.ml.constants import COMPANIES

logger = logging.getLogger(__name__)

PORTAL_COMPANIES = ["athome", "homes"]


def get_all_property_models(skip_portals: bool = False) -> list[Any]:
    """登録されている全物件モデルを取得"""
    property_models = []
    target_companies = [c for c in COMPANIES if not (skip_portals and c in PORTAL_COMPANIES)]
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


def iter_unprocessed_items(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool = False,
) -> Iterator[tuple[Any | None, bool]]:
    """未処理物件を走査し、(item, was_skipped) を yield する"""
    for item in model.objects.all().order_by("pk").iterator(chunk_size=2000):
        page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
        if not page_url:
            continue
        existing_eval = existing_eval_map.get(page_url)
        if _should_skip_item(existing_eval, force):
            yield None, True
        else:
            yield item, False


def iter_unprocessed_chunks(
    model: Any,
    existing_eval_map: dict[str, Any],
    force: bool = False,
    limit: int | None = None,
    chunk_size: int = 1000,
) -> Iterator[tuple[list[Any], int]]:
    """未処理物件を走査し、chunk_size 単位でストリーミング yield する。

    全件 list 化を行わず、同時にメモリ保持する物件数を chunk_size 以下に抑制する。
    Yields:
        (chunk_items, skipped_count_in_this_yield)
    """
    current_chunk: list[Any] = []
    skipped_count = 0
    yielded_total = 0

    for item, was_skipped in iter_unprocessed_items(model, existing_eval_map, force):
        if was_skipped:
            skipped_count += 1
            continue

        current_chunk.append(item)
        remaining = (limit - yielded_total) if limit is not None else chunk_size
        if len(current_chunk) >= min(chunk_size, remaining):
            to_yield = current_chunk[:remaining] if limit is not None else current_chunk
            yield to_yield, skipped_count
            yielded_total += len(to_yield)
            current_chunk = []
            skipped_count = 0
            if limit is not None and yielded_total >= limit:
                return

    if current_chunk:
        remaining = (limit - yielded_total) if limit is not None else len(current_chunk)
        if remaining > 0:
            yield current_chunk[:remaining], skipped_count
