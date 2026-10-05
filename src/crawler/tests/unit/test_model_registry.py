# -*- coding: utf-8 -*-
"""ModelRegistry ユニットテスト (Issue #714)"""

import threading

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
    reg = ModelRegistry(model_dir=str(tmp_path))
    load_counts = 0
    lock = threading.Lock()

    def fake_load_single_model(ptype, stage_key, algo):
        nonlocal load_counts
        with lock:
            load_counts += 1
        return _DummyModel(42.0)

    monkeypatch.setattr(reg, "_load_single_model", fake_load_single_model)

    results = []

    def worker():
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

