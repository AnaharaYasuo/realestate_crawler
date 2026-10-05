"""
機械学習 推論互換ファサードモジュール (Issue #714)


肥大化していた単一ファイルを package.ml.inference サブモジュール群へ分割し、
外部・API・テスト互換のためのインターフェースを提供します。
"""

import os
from typing import Any

from package.ml.inference.api_client import (
    call_predict_api as _call_predict_api,
)
from package.ml.inference.api_client import (
    get_api_base_url,
    serialize_property,
)
from package.ml.inference.ensemble import (
    apply_smearing_and_ensemble as _apply_smearing_and_ensemble,
)
from package.ml.inference.model_registry import (
    ensure_models_available,
    get_default_registry,
)
from package.ml.inference.predictor import (
    bulk_predict,
)
from package.ml.inference.predictor import (
    detect_property_type as _detect_property_type,
)
from package.ml.inference.predictor import (
    log_prediction_error as _log_prediction_error,
)

# 外部呼び出し元への互換性エイリアス
_serialize_property = serialize_property
log_prediction_error = _log_prediction_error
_apply_smearing_and_ensemble = _apply_smearing_and_ensemble


def _get_models_and_master(property_type: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """既存テスト・互換用: 指定種別の一次/二次モデルおよび取引事例マスタを取得"""
    reg = get_default_registry()
    first = reg.models(property_type, "first_stage")
    second = reg.models(property_type, "second_stage")
    master = reg.market_master()
    return first, second, master


def _load_ensemble_weights(model_dir: str | None = None) -> dict[str, Any]:
    """既存テスト互換用: 重み辞書取得・注入インターフェース"""
    reg = get_default_registry()
    if reg._ensemble_weights is not None:
        return reg._ensemble_weights
    return {}


def _load_smearing_factors(model_dir: str | None = None) -> dict[str, Any]:
    """既存テスト互換用: スミアリング係数辞書取得・注入インターフェース"""
    reg = get_default_registry()
    if reg._smearing_factors is not None:
        return reg._smearing_factors
    return {}


def preload_all_models() -> None:
    """全物件種別のモデルおよびマスタをメモリへ事前ロード"""
    get_default_registry().preload()


def bulk_predict_first_stage(properties_list: list[Any]) -> list[int]:
    """複数物件に対する一括ベクトル化推論 (一次理論価格)"""
    return bulk_predict(
        properties_list,
        stage="first",
        models_provider=_get_models_and_master,
        weights_provider=_load_ensemble_weights,
        smearing_provider=_load_smearing_factors,
    )


def bulk_predict_second_stage(
    properties_list: list[Any],
    interior_scores: list[float] | None = None,
    layout_scores: list[float] | None = None,
) -> list[int]:
    """複数物件に対する一括ベクトル化推論 (二次理論価格)"""
    return bulk_predict(
        properties_list,
        stage="second",
        interior_scores=interior_scores,
        layout_scores=layout_scores,
        models_provider=_get_models_and_master,
        weights_provider=_load_ensemble_weights,
        smearing_provider=_load_smearing_factors,
    )


def predict_first_stage_local(property_obj: Any) -> int:
    """一次理論価格予測 (ローカル直接推論)"""
    preds = bulk_predict([property_obj], stage="first")
    return preds[0] if preds else 0


def predict_second_stage_local(property_obj: Any, interior_score: float, layout_score: float) -> int:
    """二次理論価格予測 (ローカル直接推論)"""
    preds = bulk_predict(
        [property_obj],
        stage="second",
        interior_scores=[interior_score],
        layout_scores=[layout_score],
    )
    return preds[0] if preds else 0


def predict_first_stage(property_obj: Any) -> int:
    """一次理論価格予測 (API経由、接続エラー時はローカルフォールバック)"""
    pred1, _ = _call_predict_api(property_obj)
    if pred1 > 0:
        return pred1
    return predict_first_stage_local(property_obj)


def predict_second_stage(property_obj: Any, interior_score: float, layout_score: float) -> int:
    """二次理論価格予測 (API経由、接続エラー時はローカルフォールバック)"""
    _, pred2 = _call_predict_api(property_obj, interior_score, layout_score)
    if pred2 > 0:
        return pred2
    return predict_second_stage_local(property_obj, interior_score, layout_score)


__all__ = [
    "_call_predict_api",
    "_detect_property_type",
    "_get_models_and_master",
    "_log_prediction_error",
    "_serialize_property",
    "bulk_predict",
    "bulk_predict_first_stage",
    "bulk_predict_second_stage",
    "ensure_models_available",
    "get_api_base_url",
    "log_prediction_error",
    "predict_first_stage",
    "predict_first_stage_local",
    "predict_second_stage",
    "predict_second_stage_local",
    "preload_all_models",
    "serialize_property",
]
