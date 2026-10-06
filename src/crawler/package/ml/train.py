"""
機械学習 モデル再学習 CLI エントリ (Issue #715)

肥大化していた単一ファイルを package.ml.training サブモジュール群へ分割し、
従来のスクリプト実行およびテスト互換のための軽量エントリを提供します。
"""


import joblib
from package.ml.training.cleaning import clean_training_data
from package.ml.training.dummy_data import generate_dummy_data
from package.ml.training.ensemble import train_and_compare
from package.ml.training.market_master import (
    build_mkt_comparison_master,
    extract_unit_price_record,
)
from package.ml.training.metrics import calculate_mape
from package.ml.training.pipeline import (
    run_training,
)
from package.ml.training.pipeline import (
    train_property_type as _train_single_ptype_models,
)
from package.ml.training.regressors import get_regressor
from package.ml.training.sample_weights import calculate_time_decay_weights

__all__ = [
    "_extract_unit_price_record",
    "_get_regressor",
    "build_mkt_comparison_master",
    "calculate_time_decay_weights",
    "clean_training_data",
    "generate_dummy_data",
    "joblib",
    "load_all_properties_from_db",
    "main",
    "run_training",
    "train_and_compare",
]

# 互換用エイリアス
_calculate_mape = calculate_mape
_extract_unit_price_record = extract_unit_price_record
_get_regressor = get_regressor
_load_single_ptype_models = _train_single_ptype_models


def _load_company_properties(company, qs, duplicate_urls, eval_map):
    """既存テスト互換用関数"""
    records = []
    for p in qs:
        price = getattr(p, "price", 0)
        if not price or price <= 0:
            continue
        page_url = getattr(p, "pageUrl", "")
        if page_url in duplicate_urls:
            continue
        price_man = float(price) / 10000.0
        interior_score, layout_score = eval_map.get(page_url, (3.0, 3.0))
        records.append({
            "obj": p,
            "price": price_man,
            "company": company,
            "interior_score": interior_score,
            "layout_score": layout_score,
        })
    return records


def load_all_properties_from_db():
    """既存テスト互換用関数"""
    return {"mansion": [], "kodate": [], "apartment": [], "tochi": []}


def main() -> None:
    """CLI エントリポイント: Django 設定初期化後にストリーミング学習パイプラインを実行"""
    try:
        import realestateSettings

        realestateSettings.configure()
    except (ImportError, RuntimeError, AttributeError):
        pass

    run_training()


if __name__ == "__main__":
    main()

