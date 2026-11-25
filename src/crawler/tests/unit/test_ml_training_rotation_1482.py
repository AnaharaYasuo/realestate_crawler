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


def test_sync_existing_metadata_from_storage_preserves_other_types(tmp_path):
    """エフェメラルコンテナ(空model_dir)でもGCSから既存メタデータ4点を事前同期し、他種別キーを保持すること (Issue #1841)"""
    import joblib
    from package.ml.training.artifacts import (
        SHARED_METADATA_FILES,
        sync_existing_metadata_from_storage,
    )

    remote_dir = tmp_path / "remote"
    remote_dir.mkdir()
    local_dir = tmp_path / "local"
    local_dir.mkdir()

    # リモートに既存3種別(mansion, kodate, tochi)が保存されている状態を構築
    joblib.dump(
        {"mansion": {"first": {"lgb": 0.9}}, "kodate": {"first": {"lgb": 0.8}}, "tochi": {"first": {"lgb": 0.7}}},
        remote_dir / "ensemble_weights.joblib",
    )
    joblib.dump(
        {"mansion": {"first": 1.02}, "kodate": {"first": 1.03}, "tochi": {"first": 1.04}},
        remote_dir / "smearing_factors.joblib",
    )
    joblib.dump(
        {"mansion": {"first": "enc_m"}, "kodate": {"first": "enc_k"}, "tochi": {"first": "enc_t"}},
        remote_dir / "location_encoders.joblib",
    )
    joblib.dump(
        {"mansion": {"first": 0.01}, "kodate": {"first": 0.02}, "tochi": {"first": 0.03}},
        remote_dir / "p10_conformal.joblib",
    )

    class DummyStorage:
        def list_files(self, prefix: str):
            return [f"{prefix}{fname}" for fname in SHARED_METADATA_FILES]

        def download_file(self, key: str, local_path: str):
            fname = os.path.basename(key)
            src = remote_dir / fname
            if not src.exists():
                raise FileNotFoundError(key)
            with open(src, "rb") as rf, open(local_path, "wb") as wf:
                wf.write(rf.read())

    synced = sync_existing_metadata_from_storage(
        str(local_dir), storage_manager_getter=lambda: DummyStorage()
    )
    assert synced == len(SHARED_METADATA_FILES)

    # apartment のみ単独ローテーション学習して保存
    save_metadata(
        str(local_dir),
        {"apartment": {"first": {"lgb": 0.85}}},
        {"apartment": {"first": 1.02}},
        location_encoders={"apartment": {"first": "enc_a"}},
        p10_conformal={"apartment": {"first": 0.025}},
    )

    for fname in SHARED_METADATA_FILES:
        merged = joblib.load(local_dir / fname)
        assert set(merged.keys()) == {"mansion", "kodate", "tochi", "apartment"}, f"Lost keys in {fname}"


def test_sync_existing_metadata_handles_missing_remote_gracefully(tmp_path):
    """リモートに既存メタデータが存在しない初回実行でも例外で落ちずに継続すること"""
    from package.ml.training.artifacts import sync_existing_metadata_from_storage

    class EmptyStorage:
        def list_files(self, prefix: str):
            return []

        def download_file(self, key: str, local_path: str):
            raise RuntimeError("404 not found")

    synced = sync_existing_metadata_from_storage(
        str(tmp_path), storage_manager_getter=lambda: EmptyStorage()
    )
    assert synced == 0


def test_run_training_syncs_metadata_before_save(monkeypatch, tmp_path):
    """run_training() が save_metadata() の直前に sync_existing_metadata_from_storage() を呼ぶこと (Issue #1841)"""
    from package.ml.training import pipeline

    call_order: list[str] = []

    monkeypatch.setattr(pipeline, "get_evaluation_and_duplicate_caches", lambda: ({}, set()))
    monkeypatch.setattr(pipeline, "collect_model_classes_by_type", lambda: {"apartment": []})
    monkeypatch.setattr(pipeline, "build_market_master_from_models", lambda *a, **kw: {})
    monkeypatch.setattr(pipeline, "stream_training_feature_chunks", lambda *a, **kw: iter([]))
    monkeypatch.setattr(
        pipeline,
        "train_property_type",
        lambda *a, **kw: {
            "ptype": "apartment",
            "input_count": 10,
            "valid_count": 10,
            "outliers_count": 0,
            "duration_sec": 0.1,
            "used_dummy": False,
            "mem_start_mb": 100.0,
            "mem_end_mb": 110.0,
            "proc_cpu_pct": 10.0,
            "sys_cpu_pct": 10.0,
        },
    )
    monkeypatch.setattr(
        pipeline,
        "sync_existing_metadata_from_storage",
        lambda model_dir, **kw: call_order.append("sync") or 4,
    )
    monkeypatch.setattr(
        pipeline,
        "save_metadata",
        lambda *a, **kw: call_order.append("save"),
    )
    monkeypatch.setattr(
        pipeline,
        "upload_models_to_storage",
        lambda *a, **kw: call_order.append("upload") or 1,
    )

    pipeline.run_training(target_property_types=["apartment"])
    assert call_order == ["sync", "save", "upload"]
