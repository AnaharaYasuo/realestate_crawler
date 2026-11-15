import datetime
import os

from package.ml.constants import PROPERTY_TYPES
from package.ml.training.artifacts import save_metadata
from package.ml.training.pipeline import resolve_target_property_types


def test_resolve_target_property_types_explicit_cli():
    """CLI で明示的に指定された場合"""
    res = resolve_target_property_types(["mansion"])
    assert res == ["mansion"]

    res_multi = resolve_target_property_types(["mansion,kodate"])
    assert res_multi == ["mansion", "kodate"]


def test_resolve_target_property_types_env(monkeypatch):
    """環境変数 ML_TRAIN_PROPERTY_TYPES が指定された場合"""
    monkeypatch.setenv("ML_TRAIN_PROPERTY_TYPES", "apartment")
    res = resolve_target_property_types(None)
    assert res == ["apartment"]


def test_resolve_target_property_types_default():
    """指定がない場合は全種別（互換性維持）"""
    res = resolve_target_property_types(None)
    assert res == list(PROPERTY_TYPES)


def test_save_metadata_merges_with_existing(tmp_path):
    """save_metadata が既存のメタデータを破壊せず、指定種別のみマージすること"""
    model_dir = str(tmp_path)
    import joblib

    existing_weights = {"mansion": {"first": {"lgb": 1.0}}}
    joblib.dump(existing_weights, os.path.join(model_dir, "ensemble_weights.joblib"))

    new_weights = {"kodate": {"first": {"xgb": 1.0}}}
    save_metadata(model_dir, new_weights, {"kodate": {"first": 1.05}})

    merged_weights = joblib.load(os.path.join(model_dir, "ensemble_weights.joblib"))
    assert "mansion" in merged_weights
    assert "kodate" in merged_weights
    assert merged_weights["mansion"] == {"first": {"lgb": 1.0}}
    assert merged_weights["kodate"] == {"first": {"xgb": 1.0}}


def test_weekday_rotation_target_type():
    """曜日ごとのローテーション種別マッピングの検証"""
    from scripts.ops.run_ml_pipeline import get_rotation_property_type_for_date

    # 木曜 (weekday() == 3) -> mansion
    thursday = datetime.date(2026, 11, 19)
    assert thursday.weekday() == 3
    assert get_rotation_property_type_for_date(thursday) == "mansion"

    # 金曜 (weekday() == 4) -> kodate
    friday = datetime.date(2026, 11, 20)
    assert friday.weekday() == 4
    assert get_rotation_property_type_for_date(friday) == "kodate"

    # 土曜 (weekday() == 5) -> apartment
    saturday = datetime.date(2026, 11, 21)
    assert saturday.weekday() == 5
    assert get_rotation_property_type_for_date(saturday) == "apartment"

    # 日曜 (weekday() == 6) -> tochi
    sunday = datetime.date(2026, 11, 22)
    assert sunday.weekday() == 6
    assert get_rotation_property_type_for_date(sunday) == "tochi"

    # 月曜 (weekday() == 0) -> None (スキップ)
    monday = datetime.date(2026, 11, 16)
    assert monday.weekday() == 0
    assert get_rotation_property_type_for_date(monday) is None
