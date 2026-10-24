"""
東急リバブル パーサー不整合データ クレンジングスクリプト (Issue #1097)

東急リバブル（tokyu）の物件において、間取りや構造等のフィールドに辞書の文字列表現
（例: "{'value': ..."）が誤って格納されてしまったレコードを検出し、
横断管理テーブル PropertyEvaluation 上で `needs_recrawl=True` を立てる。

これにより、MLモデルの学習対象から即座に除外され、ピンポイント再クローリングバッチ
（recrawl_anomalies.py）または次回クローラー実行時に正常な値で再取得・上書きされる。
"""
from __future__ import annotations

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

from django.db import transaction
from django.db.models import Q
from package.models.evaluation import PropertyEvaluation
from package.models.tokyu import (
    TokyuInvestmentApartment,
    TokyuInvestmentKodate,
    TokyuKodate,
    TokyuMansion,
    TokyuTochi,
)

logger = logging.getLogger(__name__)


def find_anomaly_urls() -> set[str]:
    """辞書文字列表現が混入している東急リバブル物件の URL を収集する。"""
    anomaly_urls: set[str] = set()

    # 1. tokyu_kodate
    kodate_urls = TokyuKodate.objects.filter(
        Q(madori__startswith="{'value'")
        | Q(kouzou__startswith="{'value'")
        | Q(youtoChiiki__startswith="{'value'")
        | Q(tochikenri__startswith="{'value'")
    ).values_list("pageUrl", flat=True)
    anomaly_urls.update(kodate_urls)

    # 2. tokyu_mansion
    mansion_urls = TokyuMansion.objects.filter(
        Q(madori__startswith="{'value'")
        | Q(kouzou__startswith="{'value'")
        | Q(kaisuStr__startswith="{'value'")
        | Q(tochikenri__startswith="{'value'")
    ).values_list("pageUrl", flat=True)
    anomaly_urls.update(mansion_urls)

    # 3. tokyu_tochi
    tochi_urls = TokyuTochi.objects.filter(
        Q(chimoku__startswith="{'value'")
        | Q(youtoChiiki__startswith="{'value'")
        | Q(tochikenri__startswith="{'value'")
    ).values_list("pageUrl", flat=True)
    anomaly_urls.update(tochi_urls)

    # 4. tokyu_investment_kodate
    inv_kodate_urls = TokyuInvestmentKodate.objects.filter(
        Q(kouzou__startswith="{'value'")
        | Q(youtoChiiki__startswith="{'value'")
        | Q(tochikenri__startswith="{'value'")
    ).values_list("pageUrl", flat=True)
    anomaly_urls.update(inv_kodate_urls)

    return anomaly_urls


def cleanse_tokyu_anomalies(dry_run: bool = False) -> int:
    """不整合レコードの PropertyEvaluation.needs_recrawl を True に更新する。"""
    anomaly_urls = find_anomaly_urls()
    logger.info("Found %d anomaly properties with dict strings across tokyu models.", len(anomaly_urls))

    if not anomaly_urls:
        logger.info("No anomaly records detected.")
        return 0

    qs = PropertyEvaluation.objects.filter(
        company="tokyu",
        property_url__in=anomaly_urls,
    )
    target_count = qs.count()
    logger.info("Target PropertyEvaluation records to update: %d", target_count)

    if dry_run:
        logger.info("[DRY RUN] Would update %d records to needs_recrawl=True", target_count)
        return target_count

    with transaction.atomic():
        updated_count = qs.update(
            needs_recrawl=True,
            data_quality_issue="tokyu_madori_dict_bug",
        )
        logger.info("Successfully marked %d PropertyEvaluation records as needs_recrawl=True.", updated_count)

    return updated_count


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Cleanse tokyu anomaly data by setting needs_recrawl=True")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without modifying database")
    args = parser.parse_args()

    cleanse_tokyu_anomalies(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
