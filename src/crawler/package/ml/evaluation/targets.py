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
    current_chunk = []
    skipped_count = 0
    yielded_total = 0

    for item in model.objects.all().order_by("pk").iterator(chunk_size=2000):
        page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
        if not page_url:
            continue

        existing_eval = existing_eval_map.get(page_url)
        # 公開終了物件または再クロール待ちの不正物件は除外 (Issue #665)
        if existing_eval and (not getattr(existing_eval, "is_published", True) or getattr(existing_eval, "needs_recrawl", False)):
            skipped_count += 1
            continue

        if not force and existing_eval and existing_eval.first_stage_predicted_price is not None:
            skipped_count += 1
            continue

        current_chunk.append(item)
        if len(current_chunk) >= chunk_size:
            yield current_chunk, skipped_count
            yielded_total += len(current_chunk)
            current_chunk = []
            skipped_count = 0

            if limit and yielded_total >= limit:
                break

    if current_chunk and (not limit or yielded_total < limit):
        if limit and (yielded_total + len(current_chunk) > limit):
            current_chunk = current_chunk[: limit - yielded_total]
        yield current_chunk, skipped_count
