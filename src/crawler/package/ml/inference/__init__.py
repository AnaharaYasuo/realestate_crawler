"""ML 推論パッケージ (Issue #714)"""

from package.ml.inference.api_client import (
    call_predict_api,
    get_api_base_url,
    serialize_property,
)
from package.ml.inference.ensemble import (
    align_features,
    apply_smearing_and_ensemble,
    extract_expected_feature_names,
)
from package.ml.inference.model_registry import (
    ModelRegistry,
    ensure_models_available,
    get_default_registry,
    set_default_registry,
)
from package.ml.inference.predictor import (
    bulk_predict,
    detect_property_type,
    log_prediction_error,
)

__all__ = [
    "ModelRegistry",
    "align_features",
    "apply_smearing_and_ensemble",
    "bulk_predict",
    "call_predict_api",
    "detect_property_type",
    "ensure_models_available",
    "extract_expected_feature_names",
    "get_api_base_url",
    "get_default_registry",
    "log_prediction_error",
    "serialize_property",
    "set_default_registry",
]
