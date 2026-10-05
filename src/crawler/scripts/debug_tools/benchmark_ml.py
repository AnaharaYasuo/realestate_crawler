# -*- coding: utf-8 -*-
"""
ML パイプライン性能ベンチマーク (Issue #711, Epic #710)

実DBの物件を対象に、特徴量生成・一括推論のスループット、DB クエリ数/件、メモリを計測する。
リファクタ各フェーズの Before/After 比較に使用する（コンテナ内で実行）。

例:
  python src/crawler/scripts/debug_tools/benchmark_ml.py --model mitsuimansion --limit 1000
  python src/crawler/scripts/debug_tools/benchmark_ml.py --model mitsuimansion --limit 1000 --json out.json
"""
import argparse
import json
import os
import resource
import sys
import time
import tracemalloc

_crawler_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import setup_env  # noqa: F401,E402

from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from package.ml.features import build_features_batch  # noqa: E402
from package.ml.predict import bulk_predict_first_stage, preload_all_models  # noqa: E402
from package.utils.property_type_detector import PropertyTypeDetector  # noqa: E402


def _rss_mb() -> float:
    # Linux の ru_maxrss は KB 単位（プロセス生存中のピーク値）
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _load_properties(model_name: str, limit: int) -> list:
    model = apps.get_model("package", model_name)
    return list(model.objects.order_by("pk")[:limit])


def _measure(label: str, func):
    tracemalloc.start()
    with CaptureQueriesContext(connection) as ctx:
        start = time.perf_counter()
        result = func()
        elapsed = time.perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {
        "label": label,
        "seconds": round(elapsed, 3),
        "queries": len(ctx.captured_queries),
        "tracemalloc_peak_mb": round(peak / 1024 / 1024, 2),
    }


def run(model_name: str, limit: int) -> dict:
    props = _load_properties(model_name, limit)
    if not props:
        raise SystemExit(f"No properties found for model '{model_name}'")
    n = len(props)
    ptype = PropertyTypeDetector.detect_from_object(props[0])

    # ウォームアップ: 参照マスタのキャッシュロードとモデルロードを計測対象から除外
    build_features_batch(props[:1], ptype)
    preload_all_models()

    _, feat_stats = _measure("build_features_batch", lambda: build_features_batch(props, ptype))
    _, pred_stats = _measure("bulk_predict_first_stage", lambda: bulk_predict_first_stage(props))

    for stats in (feat_stats, pred_stats):
        stats["items"] = n
        stats["items_per_sec"] = round(n / stats["seconds"], 1) if stats["seconds"] > 0 else None
        stats["queries_per_item"] = round(stats["queries"] / n, 3)

    return {
        "model": model_name,
        "property_type": ptype,
        "items": n,
        "results": [feat_stats, pred_stats],
        "peak_rss_mb": round(_rss_mb(), 1),
    }


def main():
    parser = argparse.ArgumentParser(description="ML pipeline benchmark")
    parser.add_argument("--model", default="mitsuimansion", help="Django model name (e.g. mitsuimansion)")
    parser.add_argument("--limit", type=int, default=1000, help="Number of properties to benchmark")
    parser.add_argument("--json", default=None, help="Write result JSON to this path")
    args = parser.parse_args()

    report = run(args.model, args.limit)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
