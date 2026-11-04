# -*- coding: utf-8 -*-
"""
積算価格一括リカバリスクリプト (Issue #1242)

既存の PropertyEvaluation レコードの中で estimated_sekisan_price が NULL または 0 のレコードを対象に、
全社・全物件種別の原簿モデルから物件データ（土地面積、建物面積、構造、築年、所在地）を取得し、
積算価格を高速に算出して bulk_update します。

仕様:
- バッチサイズ: 100
- スレッド数（並列数）: 16
"""

import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

# Django設定の初期化
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import realestateSettings
realestateSettings.configure()

from django.apps import apps
from django.db import close_old_connections
from django.db.models import Q
from package.models.evaluation import PropertyEvaluation
from package.ml.investment_evaluator import calculate_sekisan_price, _extract_pref_and_city

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s"
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 100
MAX_WORKERS = 16

# 全具象モデルのマップを事前構築
ALL_MODELS = {
    m._meta.object_name.lower(): m
    for m in apps.get_models()
    if hasattr(m, 'objects') and not getattr(m._meta, 'abstract', False)
}


def resolve_model_for_eval(eval_rec: PropertyEvaluation):
    """評価レコードから正確な物件モデルクラスを特定する"""
    comp = (eval_rec.company or "").lower().strip()
    ptype = (eval_rec.property_type or "").lower().strip()
    url = (eval_rec.property_url or "").lower().strip()

    # 特殊な会社名正規化
    if "asahi-kasei" in url or comp == "asahi-kasei":
        comp = "afr"
    elif "ad-cast" in url or comp == "adcast":
        comp = "adcast"
    elif "re-guide" in url or "reguide" in url:
        comp = "reguide"

    # モデル名候補の探索
    candidates = []
    # 1. 会社名 + 種別 (例: nomuratochi, sumirintochi)
    candidates.append(f"{comp}{ptype}")
    # 2. 投資系の場合 (例: sumifuinvestmentapartment, kenbiyainvestmentapartment)
    if "apartment" in ptype:
        candidates.append(f"{comp}investmentapartment")
        candidates.append(f"{comp}apartment")
    if "building" in ptype:
        candidates.append(f"{comp}investmentbuilding")
    if "kodate" in ptype:
        candidates.append(f"{comp}investmentkodate")
        candidates.append(f"{comp}kodate")
    if "investment" in ptype or "invest" in ptype:
        candidates.append(f"{comp}investment")
        candidates.append(f"{comp}investmentapartment")
        candidates.append(f"{comp}investmentkodate")

    for cand in candidates:
        if cand in ALL_MODELS:
            return ALL_MODELS[cand]

    # 部分一致でのフォールバック
    for name, model_cls in ALL_MODELS.items():
        if comp and comp in name and ptype and (ptype in name or (ptype == "tochi" and "tochi" in name)):
            return model_cls

    return None


def process_eval_chunk(eval_ids: List[int]) -> int:
    """単一チャンク（100件）の積算価格を算出して bulk_update するワーカー関数"""
    close_old_connections()
    try:
        evals = list(
            PropertyEvaluation.objects.filter(id__in=eval_ids)
            .only("id", "company", "property_type", "property_id", "property_url", "estimated_sekisan_price")
        )
        if not evals:
            return 0

        # モデルごとにレコードをグルーピングしてプロパティを一括取得
        evals_by_model = {}
        for rec in evals:
            if not rec.property_id:
                continue
            model_cls = resolve_model_for_eval(rec)
            if not model_cls:
                continue
            evals_by_model.setdefault(model_cls, []).append(rec)

        updated_records = []
        for model_cls, model_evals in evals_by_model.items():
            prop_ids = [e.property_id for e in model_evals]
            props = {p.id: p for p in model_cls.objects.filter(id__in=prop_ids)}

            for rec in model_evals:
                prop = props.get(rec.property_id)
                if not prop:
                    continue

                address = getattr(prop, "address", "") or ""
                pref, city = _extract_pref_and_city(address)
                sekisan = calculate_sekisan_price(prop, pref, city)
                if sekisan > 0:
                    rec.estimated_sekisan_price = sekisan
                    updated_records.append(rec)

        if updated_records:
            PropertyEvaluation.objects.bulk_update(
                updated_records,
                fields=["estimated_sekisan_price"],
                batch_size=len(updated_records),
            )
            return len(updated_records)
        return 0
    except Exception as e:
        logger.error("Error processing chunk: %s", e)
        return 0
    finally:
        close_old_connections()


def run_recovery(property_types: List[str] = None, passed_only: bool = False, max_records: int = None):
    """未設定レコードを抽出し、16スレッド並列でバッチリカバリを実行する"""
    logger.info("Starting sekisan price recovery...")
    query = PropertyEvaluation.objects.filter(
        Q(estimated_sekisan_price__isnull=True) | Q(estimated_sekisan_price=0)
    )

    if property_types:
        query = query.filter(property_type__in=property_types)
    else:
        query = query.exclude(property_type="mansion")

    if passed_only:
        query = query.filter(is_first_stage_passed=True)

    total_target = query.count()
    if max_records and total_target > max_records:
        total_target = max_records

    logger.info(
        "Total target records: %d (Types: %s, PassedOnly: %s)",
        total_target, property_types or "All non-mansion", passed_only
    )

    if total_target == 0:
        logger.info("No records to recover.")
        return

    id_queryset = query.values_list("id", flat=True)
    if max_records:
        id_queryset = id_queryset[:max_records]
    all_ids = list(id_queryset)

    chunks = [all_ids[i:i + BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
    logger.info("Total chunks: %d (Batch size: %d, Workers: %d)", len(chunks), BATCH_SIZE, MAX_WORKERS)

    start_time = time.time()
    total_updated = 0
    completed_chunks = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="SekisanWorker") as executor:
        future_to_chunk = {executor.submit(process_eval_chunk, chunk): chunk for chunk in chunks}
        for future in as_completed(future_to_chunk):
            count = future.result()
            total_updated += count
            completed_chunks += 1
            if completed_chunks % 50 == 0 or completed_chunks == len(chunks):
                elapsed = time.time() - start_time
                rps = total_updated / elapsed if elapsed > 0 else 0
                logger.info(
                    "Progress: %d/%d chunks (%.1f%%) | Updated: %d records | Speed: %.1f rec/s",
                    completed_chunks, len(chunks), (completed_chunks / len(chunks)) * 100,
                    total_updated, rps
                )

    elapsed = time.time() - start_time
    logger.info(
        "Recovery finished in %.2f seconds. Total records updated: %d",
        elapsed, total_updated
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Recover estimated_sekisan_price in PropertyEvaluation")
    parser.add_argument("--types", nargs="*", help="Property types to filter (e.g. tochi kodate)")
    parser.add_argument("--passed-only", action="store_true", help="Only recover for is_first_stage_passed=True")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records to process")
    args = parser.parse_args()

    run_recovery(property_types=args.types, passed_only=args.passed_only, max_records=args.limit)
