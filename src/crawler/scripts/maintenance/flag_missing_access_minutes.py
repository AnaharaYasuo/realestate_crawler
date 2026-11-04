"""
徒歩分・バス分が未取得の物件を再クローリング対象 (PropertyEvaluation.needs_recrawl=True) としてフラグ付けするメンテナンスバッチ

対象: station1 が設定されているにもかかわらず railwayWalkMinute1 / busWalkMinute1 がともに未設定 (NULL/0) の物件。
フラグ付け後は `recrawl_anomalies.py --include-needs-recrawl` で再取得する。

Usage:
    python scripts/maintenance/flag_missing_access_minutes.py [--dry-run] [--model MitsuiMansion]
"""
import argparse
import logging
import os
import sys

_cur = os.path.abspath(__file__)
while True:
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        break
    if os.path.exists(os.path.join(_parent, "setup_env.py")):
        if _parent not in sys.path:
            sys.path.insert(0, _parent)
        import setup_env  # noqa: F401
        break
    _cur = _parent

from django.apps import apps
from django.db.models import Q
from package.models.evaluation import PropertyEvaluation

logger = logging.getLogger(__name__)

ISSUE_TAG = "missing_access_minutes"
REQUIRED_FIELDS = {"station1", "railwayWalkMinute1", "busWalkMinute1", "pageUrl"}


def iter_target_models(model_name: str | None = None):
    for model in apps.get_app_config("package").get_models():
        if model_name and model.__name__ != model_name:
            continue
        if REQUIRED_FIELDS <= {f.name for f in model._meta.fields}:
            yield model


def missing_access_minutes_qs(model):
    return (
        model.objects.exclude(station1__isnull=True)
        .exclude(station1="")
        .filter(Q(railwayWalkMinute1__isnull=True) | Q(railwayWalkMinute1=0))
        .filter(Q(busWalkMinute1__isnull=True) | Q(busWalkMinute1=0))
    )


def _append_issue(current: str) -> str:
    tags = [t for t in (current or "").split(",") if t]
    if ISSUE_TAG not in tags:
        tags.append(ISSUE_TAG)
    return ",".join(tags)


def flag_missing_access_minutes(model_name: str | None = None, dry_run: bool = False) -> dict[str, tuple[int, int]]:
    """モデル別に (未取得件数, フラグ付けした評価レコード件数) を返す"""
    stats: dict[str, tuple[int, int]] = {}
    for model in iter_target_models(model_name):
        urls = list(missing_access_minutes_qs(model).values_list("pageUrl", flat=True))
        if not urls:
            continue
        evals = PropertyEvaluation.objects.filter(property_url__in=urls, is_published=True)
        flagged = 0
        for ev in evals.only("id", "needs_recrawl", "data_quality_issue"):
            flagged += 1
            if dry_run:
                continue
            ev.needs_recrawl = True
            ev.data_quality_issue = _append_issue(ev.data_quality_issue)
            ev.save(update_fields=["needs_recrawl", "data_quality_issue"])
        stats[model.__name__] = (len(urls), flagged)
        logger.info("%s: missing=%d flagged=%d (dry_run=%s)", model.__name__, len(urls), flagged, dry_run)
    return stats


def main():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Flag properties missing walk/bus minutes as needs_recrawl")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()
    stats = flag_missing_access_minutes(model_name=args.model, dry_run=args.dry_run)
    total_missing = sum(v[0] for v in stats.values())
    total_flagged = sum(v[1] for v in stats.values())
    print(f"TOTAL missing={total_missing} flagged={total_flagged}")
    for name, (m, f) in sorted(stats.items(), key=lambda kv: -kv[1][0]):
        print(f"{name:32s} missing={m:6d} flagged={f:6d}")


if __name__ == "__main__":
    main()
