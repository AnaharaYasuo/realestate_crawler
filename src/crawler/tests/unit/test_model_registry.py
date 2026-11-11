"""ModelRegistry ユニットテスト (Issue #714)"""


import threading
import time

from package.ml.inference import model_registry as mr_module
from package.ml.inference.model_registry import ModelRegistry


class _DummyModel:
    def __init__(self, val: float = 1.0):
        self.val = val

    def predict(self, X):
        return [self.val] * len(X)


def test_model_registry_thread_safety_and_caching(tmp_path):
    reg = ModelRegistry(model_dir=str(tmp_path))
    
    # 手動注入
    reg.set_custom_models("mansion", "first", {"lgb": _DummyModel(10.0)})
    
    results = []

    def worker():
        models = reg.models("mansion", "first")
        results.append(models["lgb"].val)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    assert all(r == 10.0 for r in results)


def test_model_registry_custom_weights_and_smearing(tmp_path):
    reg = ModelRegistry(model_dir=str(tmp_path))
    
    custom_w = {"mansion": {"first": {"lgb": 0.8, "xgb": 0.2}}}
    reg.set_custom_weights(custom_w)
    assert reg.weights("mansion", "first") == {"lgb": 0.8, "xgb": 0.2}

    custom_s = {"mansion": {"first": 1.05}}
    reg.set_custom_smearing_factors(custom_s)
    assert reg.smearing("mansion", "first") == 1.05

    # clear 動作検証
    reg.clear()
    assert reg.smearing("mansion", "first") == 1.0


def test_model_registry_parallel_loading_no_duplicate(tmp_path, monkeypatch):
    # 外部ストレージアクセス防止
    monkeypatch.setattr(mr_module, "ensure_models_available", lambda _: None)

    reg = ModelRegistry(model_dir=str(tmp_path))
    load_counts = 0
    lock = threading.Lock()

    def fake_load_single_model(ptype, stage_key, algo):
        nonlocal load_counts
        time.sleep(0.01)  # 同時実行ウィンドウを確保
        with lock:
            load_counts += 1
        return _DummyModel(42.0)

    monkeypatch.setattr(reg, "_load_single_model", fake_load_single_model)

    barrier = threading.Barrier(10)
    results = []

    def worker():
        barrier.wait()
        m = reg.models("mansion", "first")
        results.append(m["lgb"].val)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 10
    assert all(r == 42.0 for r in results)
    # ALGOS 分 (4 回) のみロードされ、10 スレッド並列でも二重ロードされないこと
    assert load_counts == 4


def test_model_registry_location_encoders_and_disk_artifacts(tmp_path):
    import joblib

    joblib.dump({"tochi": {"first": "enc_first", "second": "enc_second"}}, tmp_path / "location_encoders.joblib")
    joblib.dump({"mansion": {"first": 1.12}}, tmp_path / "smearing_factors.joblib")
    joblib.dump({"mansion": {"first": {"lgb": 1.0}}}, tmp_path / "ensemble_weights.joblib")
    joblib.dump({("東京都", "港区", "mansion", 0): 180.0}, tmp_path / "mkt_comparison_master.joblib")

    reg = ModelRegistry(model_dir=str(tmp_path))
    assert reg.location_encoder("tochi", "first_stage") == "enc_first"
    assert reg.location_encoder("tochi", "second_stage") == "enc_second"
    assert reg.location_encoder("mansion", "first_stage") is None
    assert reg.smearing("mansion", "first_stage") == 1.12
    assert reg.weights("mansion", "first_stage") == {"lgb": 1.0}
    assert ("東京都", "港区", "mansion", 0) in reg.market_master()

    reg.set_custom_location_encoders({"mansion": {"first": "custom_enc"}})
    assert reg.location_encoder("mansion", "first") == "custom_enc"
    reg.clear()
    # clear後は再度ディスクから遅延ロードされる
    assert reg.location_encoder("tochi", "first") == "enc_first"


def test_model_registry_stage_normalization_and_legacy_fallback(tmp_path, monkeypatch):
    import joblib

    monkeypatch.setattr(mr_module, "ensure_models_available", lambda _: None)
    reg = ModelRegistry(model_dir=str(tmp_path))
    assert reg._normalize_stage("First") == "first_stage"
    assert reg._normalize_stage("SECOND") == "second_stage"
    assert reg._normalize_stage("custom") == "custom"

    # first と second が別キャッシュキーとして独立管理されること
    reg.set_custom_models("tochi", "first", {"lgb": _DummyModel(1.0)})
    reg.set_custom_models("tochi", "second", {"lgb": _DummyModel(2.0)})
    reg.set_custom_models("tochi", "custom", {"lgb": _DummyModel(3.0)})
    assert reg.models("tochi", "first_stage")["lgb"].val == 1.0
    assert reg.models("tochi", "second_stage")["lgb"].val == 2.0
    assert reg.models("tochi", "custom")["lgb"].val == 3.0

    # レガシーモデルファイル (`*_model.joblib`) は lgb のみフォールバックロードされ、他 algo ではロードされないこと
    joblib.dump(_DummyModel(99.0), tmp_path / "kodate_first_stage_model.joblib")
    loaded = reg.models("kodate", "first")
    assert set(loaded.keys()) == {"lgb"}
    assert loaded["lgb"].val == 99.0


def test_default_registry_singleton_and_ensure_models_available(tmp_path, monkeypatch, caplog):
    import logging

    orig = mr_module._DEFAULT_REGISTRY
    try:
        mr_module.set_default_registry(None)
        r1 = mr_module.get_default_registry()
        assert isinstance(r1, ModelRegistry)
        custom = ModelRegistry(model_dir=str(tmp_path))
        mr_module.set_default_registry(custom)
        assert mr_module.get_default_registry() is custom
    finally:
        mr_module.set_default_registry(orig)

    # 1) model_dir=None の既定パス分岐（既存joblibあり相当で早期リターンさせる）
    monkeypatch.setattr(mr_module.os, "makedirs", lambda *_a, **_k: None)
    seen_dirs = []

    def fake_listdir_nonempty(d):
        seen_dirs.append(d)
        return ["existing.joblib"]

    monkeypatch.setattr(mr_module.os, "listdir", fake_listdir_nonempty)
    mr_module.ensure_models_available(model_dir=None)
    assert len(seen_dirs) == 1 and seen_dirs[0].endswith("models")
    monkeypatch.undo()

    # 2) 空ディレクトリからのダウンロード成功ログ ("Successfully downloaded") と 0件警告ログ ("No models found")
    dl_dir = tmp_path / "dl1"
    downloaded_pairs = []

    class _FakeStorage:
        def __init__(self, files):
            self._files = files

        def list_files(self, prefix):
            assert prefix == "ml_models/"
            return self._files

        def download_file(self, key, dest):
            downloaded_pairs.append((key, dest))

    monkeypatch.setattr(
        mr_module,
        "get_storage_manager",
        lambda: (_ for _ in ()).throw(AssertionError("default getter must not be called when custom getter is passed")),
    )
    with caplog.at_level(logging.INFO):
        mr_module.ensure_models_available(
            model_dir=str(dl_dir),
            storage_manager_getter=lambda: _FakeStorage(["ml_models/a.joblib", "ml_models/readme.txt"]),
        )
    assert len(downloaded_pairs) == 1
    assert "Successfully downloaded 1 models" in caplog.text

    caplog.clear()
    dl_dir2 = tmp_path / "dl2"
    with caplog.at_level(logging.WARNING):
        mr_module.ensure_models_available(
            model_dir=str(dl_dir2),
            storage_manager_getter=lambda: _FakeStorage([]),
        )
    assert "No models found in storage prefix" in caplog.text

