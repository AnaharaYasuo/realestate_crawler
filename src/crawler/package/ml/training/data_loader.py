"""
機械学習用ストリーミングデータローダーモジュール (Issue #715)
"""

import logging
from collections.abc import Iterator
from typing import Any

import numpy as np
from django.apps import apps
from package.ml.constants import COMPANIES
from package.ml.features import build_features_batch
from package.models.evaluation import PropertyEvaluation

logger = logging.getLogger(__name__)


def get_evaluation_and_duplicate_caches() -> tuple[dict[str, tuple[float, float]], set[str]]:
    """PropertyEvaluation から values_list を用いて軽量に評価・重複 URL をロード"""
    logger.info("Caching property evaluations...")
    eval_map: dict[str, tuple[float, float]] = {}
    qs_eval = PropertyEvaluation.objects.all().values_list("property_url", "interior_score", "layout_score")
    for prop_url, int_score, lay_score in qs_eval:
        if prop_url:
            eval_map[prop_url] = (
                float(int_score) if int_score is not None else 3.0,
                float(lay_score) if lay_score is not None else 3.0,
            )
    logger.info("Cached %d evaluations.", len(eval_map))

    logger.info("Caching duplicate property URLs...")
    duplicate_urls = set(
        PropertyEvaluation.objects.filter(duplicate_of__isnull=False)
        .values_list("property_url", flat=True)
    )
    logger.info("Found %d duplicate properties to exclude.", len(duplicate_urls))
    return eval_map, duplicate_urls


def collect_model_classes_by_type() -> dict[str, list[tuple[str, Any]]]:
    """各社×種別の Django モデルクラス群を収集"""
    app_config = apps.get_app_config("package")
    models_by_type: dict[str, list[tuple[str, Any]]] = {
        "mansion": [],
        "kodate": [],
        "apartment": [],
        "tochi": [],
    }
    for model in app_config.get_models():
        model_name = model.__name__.lower()
        matched_company = next((c for c in COMPANIES if model_name.startswith(c)), None)
        if not matched_company:
            continue
        suffix = model_name[len(matched_company):]
        for ptype in ["mansion", "apartment", "tochi", "kodate"]:
            if ptype in suffix:
                models_by_type[ptype].append((matched_company, model))
                break
    return models_by_type


def _collect_lightweight_records_for_ptype(
    models_list: list[tuple[str, Any]],
    duplicate_urls: set[str],
) -> list[tuple[Any, str, int, float, str]]:
    """ORM インスタンスを生成せず、values_list で (model, company, pk, price, page_url) を収集"""
    records: list[tuple[Any, str, int, float, str]] = []
    for company, model in models_list:
        try:
            # qs.count() は発行せず、直接 values_list を実行
            qs = model.objects.order_by("pk").values_list("pk", "price", "pageUrl")
            for pk, price, page_url in qs:
                if not price or price <= 0:
                    continue
                if page_url in duplicate_urls:
                    continue
                records.append((model, company, pk, float(price) / 10000.0, page_url or ""))
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not query model %s: %s", getattr(model, "__name__", "unknown"), e)
    return records


def _process_model_chunk(
    model: Any,
    pks: list[int],
    pk_map: dict[int, tuple[str, int, float, str]],
    ptype: str,
    eval_map: dict[str, tuple[float, float]],
    mkt_master: dict[tuple[str, str, str, int], float],
) -> list[dict[str, Any]]:
    """単一モデルのチャンクから特徴量を抽出しリストとして生成"""
    try:
        objs = list(model.objects.filter(pk__in=pks))
        if not objs:
            logger.warning("No model instances found for model %s with pks: %s", getattr(model, "__name__", "unknown"), pks[:5])
            return []
        features_chunk = build_features_batch(objs, ptype, mkt_comparison_master=mkt_master)
        results = []
        for obj, feat in zip(objs, features_chunk):
            pk_val = getattr(obj, "pk", None)
            item_info = pk_map.get(pk_val)
            if item_info is None:
                continue
            _, _, price_man, page_url = item_info
            int_score, lay_score = eval_map.get(page_url, (3.0, 3.0))

            feat["price"] = price_man
            feat["interior_score"] = int_score
            feat["layout_score"] = lay_score
            feat["input_date"] = getattr(obj, "inputDate", None) or getattr(obj, "inputDateTime", None)
            results.append(feat)
        if not results:
            logger.warning(
                "Chunk of %d objects for model %s yielded 0 features (ptype: %s)",
                len(objs),
                getattr(model, "__name__", "unknown"),
                ptype,
            )
        return results
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to fetch chunk for model %s: %s", getattr(model, "__name__", "unknown"), e)
        return []


def stream_training_features(
    ptype: str,
    models_by_type: dict[str, list[tuple[str, Any]]],
    eval_map: dict[str, tuple[float, float]],
    duplicate_urls: set[str],
    mkt_master: dict[tuple[str, str, str, int], float],
    max_items: int = 15000,
    seed: int = 42,
    chunk_size: int = 1000,
) -> Iterator[dict[str, Any]]:
    """
    指定種別の学習アイテムをチャンク取得し、即座に特徴量化してイテレータとして返却
    ORM オブジェクトの全件常駐を防止
    """
    models_list = models_by_type.get(ptype, [])
    records = _collect_lightweight_records_for_ptype(models_list, duplicate_urls)

    if len(records) > max_items:
        rng = np.random.default_rng(seed)
        sampled_indices = rng.choice(len(records), size=max_items, replace=False)
        records = [records[i] for i in sampled_indices]

    by_model_pks: dict[Any, list[tuple[str, int, float, str]]] = {}
    for model, company, pk, price, page_url in records:
        by_model_pks.setdefault(model, []).append((company, pk, price, page_url))

    for model, pks_info in by_model_pks.items():
        for i in range(0, len(pks_info), chunk_size):
            chunk = pks_info[i : i + chunk_size]
            pk_map = {item[1]: item for item in chunk}
            feats = _process_model_chunk(
                model=model,
                pks=list(pk_map.keys()),
                pk_map=pk_map,
                ptype=ptype,
                eval_map=eval_map,
                mkt_master=mkt_master,
            )
            yield from feats
