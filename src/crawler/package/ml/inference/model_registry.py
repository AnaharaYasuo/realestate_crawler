"""スレッドセーフな機械学習モデルおよびマスタ管理レジストリ (Issue #714)"""

import logging
import os
import threading
from typing import Any

import joblib

from package.ml.constants import ALGOS, DEFAULT_ENSEMBLE_WEIGHTS, PROPERTY_TYPES
from package.utils.storage import get_storage_manager

logger = logging.getLogger(__name__)


def ensure_models_available(model_dir: str | None = None) -> None:

    """ローカルモデルディレクトリにjoblibが存在しない場合、オブジェクトストレージからダウンロード"""
    if model_dir is None:
        model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
    os.makedirs(model_dir, exist_ok=True)

    existing_joblibs = [f for f in os.listdir(model_dir) if f.endswith(".joblib")]
    if existing_joblibs:
        return

    try:
        storage = get_storage_manager()
        files = storage.list_files("ml_models/")
        downloaded = 0
        for key in files:
            if key.endswith(".joblib"):
                fname = os.path.basename(key)
                local_dest = os.path.join(model_dir, fname)
                storage.download_file(key, local_dest)
                downloaded += 1
        if downloaded > 0:
            logger.info("ML: Successfully downloaded %d models from storage to %s", downloaded, model_dir)
        else:
            logger.warning("ML: No models found in storage prefix 'ml_models/'")
    except Exception as e:
        logger.warning("ML: Failed to download models from storage: %s", e)



class ModelRegistry:
    """スレッド安全・遅延ロード対応の ML モデル & マスタ管理レジストリ"""

    def __init__(self, model_dir: str | None = None) -> None:
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
        self.model_dir = os.path.abspath(model_dir)
        self._lock = threading.Lock()
        self._models: dict[tuple[str, str], dict[str, Any]] = {}
        self._market_master: dict[str, Any] | None = None
        self._smearing_factors: dict[str, Any] | None = None
        self._ensemble_weights: dict[str, Any] | None = None

    def _normalize_stage(self, stage: str) -> str:
        s = stage.lower()
        if "first" in s:
            return "first_stage"
        if "second" in s:
            return "second_stage"
        return s

    def _load_single_model(self, ptype: str, stage_key: str, algo: str) -> Any:
        path = os.path.join(self.model_dir, f"{ptype}_{stage_key}_{algo}.joblib")
        if os.path.exists(path):
            try:
                model = joblib.load(path)
                if hasattr(model, "set_params") and hasattr(model, "n_jobs"):
                    try:
                        model.set_params(n_jobs=1)
                    except Exception:
                        pass
                logger.info("ML: Loaded %s %s %s model.", ptype, stage_key, algo)
                return model
            except Exception as e:
                logger.exception("ML: Failed to load %s %s %s model: %s", ptype, stage_key, algo, e)

        # Legacy fallback
        if algo == "lgb":
            legacy_path = os.path.join(self.model_dir, f"{ptype}_{stage_key}_model.joblib")
            if os.path.exists(legacy_path):
                try:
                    model = joblib.load(legacy_path)
                    logger.info("ML: Loaded %s %s legacy model as lgb.", ptype, stage_key)
                    return model
                except Exception:
                    pass
        return None

    def models(self, ptype: str, stage: str) -> dict[str, Any]:
        """指定された種別とステージのモデル辞書を取得（初回時自動ロード）"""
        stage_key = self._normalize_stage(stage)
        cache_key = (ptype, stage_key)

        with self._lock:
            if cache_key in self._models and self._models[cache_key]:
                return self._models[cache_key]

            ensure_models_available(self.model_dir)
            loaded_dict: dict[str, Any] = {}
            for algo in ALGOS:
                m = self._load_single_model(ptype, stage_key, algo)
                if m is not None:
                    loaded_dict[algo] = m

            self._models[cache_key] = loaded_dict
            return self._models[cache_key]

    def market_master(self) -> dict[str, Any]:
        """取引事例比準マスタを取得"""
        with self._lock:
            if self._market_master is not None:
                return self._market_master

            ensure_models_available(self.model_dir)
            master_path = os.path.join(self.model_dir, "mkt_comparison_master.joblib")
            if os.path.exists(master_path):
                try:
                    self._market_master = joblib.load(master_path)
                    logger.info("ML: Loaded market comparison master.")
                except Exception as e:
                    logger.exception("ML: Failed to load market comparison master: %s", e)
                    self._market_master = {}
            else:
                logger.warning("ML: Market comparison master not found. Run train.py first.")
                self._market_master = {}
            return self._market_master

    def smearing(self, ptype: str, stage: str) -> float:
        """スミアリング補正係数を取得 (既定 1.0)"""
        s_key = "first" if "first" in stage.lower() else "second"
        with self._lock:
            if self._smearing_factors is None:
                path = os.path.join(self.model_dir, "smearing_factors.joblib")
                if os.path.exists(path):
                    try:
                        self._smearing_factors = joblib.load(path)
                        logger.info("ML: Loaded smearing factors.")
                    except Exception as e:
                        logger.exception("ML: Failed to load smearing factors: %s", e)
                        self._smearing_factors = {}
                else:
                    self._smearing_factors = {}
            
            factors = self._smearing_factors.get(ptype, {})
            val = factors.get(s_key, 1.0)
            return float(val) if val and float(val) > 0 else 1.0

    def weights(self, ptype: str, stage: str) -> dict[str, float]:
        """アンサンブル重みを取得（未設定時は既定値）"""
        s_key = "first" if "first" in stage.lower() else "second"
        with self._lock:
            if self._ensemble_weights is None:
                path = os.path.join(self.model_dir, "ensemble_weights.joblib")
                if os.path.exists(path):
                    try:
                        self._ensemble_weights = joblib.load(path)
                        logger.info("ML: Loaded dynamic ensemble weights.")
                    except Exception as e:
                        logger.exception("ML: Failed to load ensemble weights: %s", e)
                        self._ensemble_weights = {}
                else:
                    self._ensemble_weights = {}


            dynamic = self._ensemble_weights.get(ptype, {}).get(s_key)
            if dynamic:
                return dict(dynamic)
            return dict(DEFAULT_ENSEMBLE_WEIGHTS.get(ptype, DEFAULT_ENSEMBLE_WEIGHTS["tochi"]))

    def set_custom_models(self, ptype: str, stage: str, models: dict[str, Any]) -> None:
        """テスト等でインメモリのモックモデル辞書を明示的に注入"""
        stage_key = self._normalize_stage(stage)
        with self._lock:
            self._models[(ptype, stage_key)] = dict(models)

    def set_custom_weights(self, weights: dict[str, Any]) -> None:
        """テスト等で動的重み辞書を注入"""
        with self._lock:
            self._ensemble_weights = weights

    def set_custom_smearing_factors(self, factors: dict[str, Any]) -> None:
        """テスト等でスミアリング係数辞書を注入"""
        with self._lock:
            self._smearing_factors = factors

    def set_custom_market_master(self, master: dict[str, Any]) -> None:
        """テスト等で取引事例比準マスタを注入"""
        with self._lock:
            self._market_master = master

    def preload(self) -> None:
        """全モデルおよびマスタを事前ウォームアップ"""
        self.market_master()
        for ptype in PROPERTY_TYPES:
            self.models(ptype, "first_stage")
            self.models(ptype, "second_stage")

    def clear(self) -> None:
        """キャッシュクリア（テストまたはモデル再学習時）"""
        with self._lock:
            self._models.clear()
            self._market_master = None
            self._smearing_factors = None
            self._ensemble_weights = None


_DEFAULT_REGISTRY: ModelRegistry | None = None
_DEFAULT_LOCK = threading.Lock()


def get_default_registry() -> ModelRegistry:
    """シングルトン既定レジストリを取得"""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        with _DEFAULT_LOCK:
            if _DEFAULT_REGISTRY is None:
                _DEFAULT_REGISTRY = ModelRegistry()
    return _DEFAULT_REGISTRY


def set_default_registry(registry: ModelRegistry | None) -> None:
    """テスト用に既定レジストリを差し替え"""
    global _DEFAULT_REGISTRY
    with _DEFAULT_LOCK:
        _DEFAULT_REGISTRY = registry
