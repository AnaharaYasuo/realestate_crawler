# -*- coding: utf-8 -*-
"""
ML リファクタリング安全網: 特徴量・推論・学習のゴールデン(特性化)テスト (Issue #711, Epic #710)

現行実装の出力を JSON に固定し、以降の純粋リファクタ PR で出力が変わらないことを検証する。
ゴールデン再生成: UPDATE_ML_GOLDEN=1 pytest src/crawler/tests/unit/test_ml_golden_baseline.py
(挙動変更 PR で再生成する場合は、差分理由を PR 本文に明記すること)
"""
import json
import math
import os
import tempfile
from decimal import Decimal

import joblib
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

import package.ml.features as feat_mod
import package.ml.predict as predict_mod
import package.ml.train as train_mod
from package.ml.features import FEATURE_SETS, build_features_batch
from package.ml.train import generate_dummy_data, train_and_compare
from package.models.evaluation import (
    HazardMapPotential,
    LandPricePotential,
    MacroEconomicIndex,
    MunicipalPotential,
    StationPotential,
    UrbanPlanningZonePotential,
)

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden", "ml_golden_baseline.json")
UPDATE_GOLDEN = os.getenv("UPDATE_ML_GOLDEN") == "1"
PTYPES = ["mansion", "kodate", "apartment", "tochi"]
REFERENCE_MODELS = [
    MunicipalPotential, LandPricePotential, StationPotential,
    HazardMapPotential, UrbanPlanningZonePotential, MacroEconomicIndex,
]
CACHE_NAMES = [
    "_muni_cache", "_muni_pref_cache", "_station_cache", "_lp_cache", "_lp_pref_res_cache",
    "_lp_pref_comm_cache", "_hazard_cache", "_zone_cache", "_macro_cache",
]


class Prop:
    """ORM 互換の属性アクセス用オブジェクト"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_BASE = {"inputDate": "2026-01-15", "company": "mitsui"}

PROPERTY_FIXTURES = {
    "mansion": [
        dict(_BASE, address="東京都世田谷区玉川2丁目", station1="二子玉川", railwayWalkMinute1=5,
             senyuMenseki=72.5, chikunengetsu="2008-03-01", kouzou="RC造14階建", kanrihi=18000,
             syuzenTsumitate=15000, price=89800000, madori="3LDK", kai="7階", chijo="14",
             youtoChiiki="第一種住居地域", biko="角部屋 ディスポーザー 内廊下 免震"),
        dict(_BASE, address="東京都世田谷区上野毛1丁目", station1="上野毛", railwayWalkMinute1=8,
             senyuMenseki=55.0, chikunengetsu="1979-05-01", kouzou="SRC造", kanrihi=93000000,
             syuzenTsumitate=200000000, price=32000000, madori="2DK", kai="1階", chijo="5",
             tochikenri="旧法借地権", chidaiStr="地代 月額12,000円", biko="借地権 告知事項あり"),
        dict(_BASE, address="愛知県知多郡南知多町", traffic="名鉄河和線 / 河和駅 【バス】28分 北大井 停歩7分",
             busUse1=1, railwayWalkMinute1=7, senyuMenseki=73.75, chikunengetsu="1996-06-01",
             kanrihi=12000, price=9800000, inputDate="2024-11-20"),
        dict(_BASE, address="新潟県新発田市中央町", senyuMenseki=600.0, price=5000000),
    ],
    "kodate": [
        dict(_BASE, address="東京都世田谷区玉川3丁目", station1="二子玉川", railwayWalkMinute1=12,
             tochiMenseki=120.5, tatemonoMenseki=98.3, chikunengetsu="2015-09-01", kouzou="木造2階建",
             youseki=150.0, kenpei=60.0, setsudou="南側 公道 幅員4.5m 間口8.0m", maguchi=8.0, roadWidth=4.5,
             price=128000000, madori="4LDK", youtoChiiki="第一種低層住居専用地域"),
        dict(_BASE, address="新潟県新発田市中央町", tochiMenseki=150.38, tatemonoMenseki=279.16,
             railwayWalkMinute1=10, kouzou="RC造", youseki=60.0, kenpei=60.0, chikunengetsu="1975-01-01",
             price=8000000),
        dict(_BASE, address="神奈川県横浜市青葉区", tochiMenseki=88.0, tatemonoMenseki=70.0,
             chikunengetsu="1968-04-01", kouzou="木造", youseki=80.0, kenpei=40.0,
             setsudou="北側 私道 幅員2.0m 間口2.5m 旗竿地", price=12000000,
             biko="再建築不可 古家あり 現況渡し セットバック要 約5.2㎡"),
        dict(_BASE, address="千葉県市川市", tochiMenseki=0, tatemonoMenseki=0, price=0),
    ],
    "apartment": [
        dict(_BASE, address="東京都世田谷区上野毛2丁目", station1="上野毛", railwayWalkMinute1=6,
             tochiMenseki=165.0, tatemonoMenseki=210.0, chikunengetsu="1992-02-01", kouzou="軽量鉄骨造2階建",
             youseki=200.0, kenpei=60.0, grossYield=7.8, annualRent=9360000, price=120000000,
             setsudou="東側 公道 幅員6.0m 間口12.0m", youtoChiiki="第一種住居地域"),
        dict(_BASE, address="埼玉県川口市", tochiMenseki=99.0, tatemonoMenseki=140.0,
             chikunengetsu="1988-07-01", kouzou="木造", grossYield=11.5, annualRent=4140000, price=36000000,
             inputDate="2023-05-01"),
    ],
    "tochi": [
        dict(_BASE, address="東京都世田谷区玉川1丁目", station1="二子玉川", railwayWalkMinute1=9,
             tochiMenseki=132.2, youseki=200.0, kenpei=60.0, setsudou="南東角地 公道 幅員6.0m 間口11.0m",
             maguchi=11.0, roadWidth=6.0, chimoku="宅地", price=150000000, youtoChiiki="第一種住居地域"),
        dict(_BASE, address="千葉県市原市", tochiMenseki=520.0, chimoku="山林",
             youtoChiiki="市街化調整区域", price=3000000, biko="市街化調整区域 建築不可"),
        dict(_BASE, address="新潟県新発田市", tochiMenseki=210.0, setsudou="西側 私道 幅員3.0m 間口3.0m",
             price=4000000, biko="不整形地 古家あり 更地渡し"),
    ],
}


def _normalize(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    if hasattr(value, "item"):  # numpy スカラー
        return _normalize(value.item())
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def _normalize_features(feats):
    return {k: _normalize(v) for k, v in sorted(feats.items())}


def _seed_reference_data():
    MunicipalPotential.objects.create(
        prefecture="東京都", city="世田谷区", population_growth_rate=Decimal("0.45"), average_income=5200,
        total_population=940000, income_growth_rate=Decimal("1.20"), population_density=Decimal("16200.00"))
    MunicipalPotential.objects.create(
        prefecture="新潟県", city="新発田市", population_growth_rate=Decimal("-1.10"), average_income=2900,
        total_population=94000, income_growth_rate=Decimal("-0.30"), population_density=Decimal("176.00"))
    for land_use, price in (("residential", 680000), ("commercial", 1450000)):
        LandPricePotential.objects.create(
            prefecture="東京都", city="世田谷区", average_land_price=price, estimated_rosenka_price=int(price * 0.8),
            estimated_fixed_asset_price=int(price * 0.7), land_price_growth_rate=Decimal("3.10"), land_use=land_use)
    StationPotential.objects.create(station_name="二子玉川", railway_line="東急田園都市線", passenger_volume=168000)
    StationPotential.objects.create(station_name="上野毛", railway_line="東急大井町線", passenger_volume=21000)
    HazardMapPotential.objects.create(prefecture="東京都", city="世田谷区", flood_risk_level=2, landslide_risk_level=1)
    UrbanPlanningZonePotential.objects.create(zone_name="第一種低層住居専用地域", max_kenpei=50, max_youseki=100)
    UrbanPlanningZonePotential.objects.create(zone_name="第一種住居地域", max_kenpei=60, max_youseki=200)
    for ym, repi in (("2024-11", 128.0), ("2026-01", 135.5)):
        MacroEconomicIndex.objects.create(
            year_month=ym, repi_mansion=repi, repi_kodate=repi - 20, repi_tochi=repi - 15, jgb_10y_yield=1.1,
            nikkei_225=38000.0, tse_reit_index=1750.0, construction_cost_index=126.0)


def _clear_reference_state():
    for model in REFERENCE_MODELS:
        model.objects.all().delete()
    for name in CACHE_NAMES:
        getattr(feat_mod, name).clear()


@pytest.fixture
def reference_data():
    """参照マスタを固定データで初期化し、モジュールキャッシュを分離する"""
    saved = {name: dict(getattr(feat_mod, name)) for name in CACHE_NAMES}
    _clear_reference_state()
    _seed_reference_data()
    yield
    _clear_reference_state()
    for name, data in saved.items():
        getattr(feat_mod, name).update(data)


def _fixture_props(ptype, as_object):
    items = PROPERTY_FIXTURES[ptype]
    return [Prop(**d) for d in items] if as_object else [dict(d) for d in items]


def _load_golden():
    if not os.path.exists(GOLDEN_PATH):
        return {}
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def _check_golden(section, actual):
    """section 単位でゴールデンと比較（UPDATE 時は書き込み）"""
    golden = _load_golden()
    if UPDATE_GOLDEN:
        golden[section] = actual
        os.makedirs(os.path.dirname(GOLDEN_PATH), exist_ok=True)
        with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
            json.dump(golden, f, ensure_ascii=False, indent=1, sort_keys=True)
        return golden[section]
    assert section in golden, f"golden section '{section}' missing. Run with UPDATE_ML_GOLDEN=1"
    return golden[section]


# 許容誤差: 厳密一致は求めない（元モデル精度に対して十分小さい揺らぎは許容）
FEATURE_REL_TOL = 1e-6      # 特徴量: 浮動小数の演算順序変更程度の差のみ許容
PREDICT_REL_TOL = 0.05      # 推論価格: ±5%
WEIGHT_ABS_TOL = 0.10       # アンサンブル重み: ±0.10
SMEARING_REL_TOL = 0.05     # スミアリング係数: ±5%


def _approx(expected, rel, abs_tol=1e-9):
    """数値は pytest.approx、文字列等は完全一致で比較できる形に変換する"""
    if isinstance(expected, dict):
        return {k: _approx(v, rel, abs_tol) for k, v in expected.items()}
    if isinstance(expected, list):
        return [_approx(v, rel, abs_tol) for v in expected]
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return pytest.approx(expected, rel=rel, abs=abs_tol)
    return expected


@pytest.mark.parametrize("ptype", PTYPES)
@pytest.mark.parametrize("as_object", [False, True], ids=["dict", "object"])
def test_build_features_golden(reference_data, ptype, as_object):
    feats = build_features_batch(_fixture_props(ptype, as_object), ptype)
    actual = [_normalize_features(f) for f in feats]
    # dict 入力と属性オブジェクト入力は同一ゴールデンを共有（入力形式に依存しないことも同時に担保）
    expected = _check_golden(f"features/{ptype}", actual) if not as_object else _load_golden().get(f"features/{ptype}")
    assert expected is not None
    assert actual == _approx(expected, FEATURE_REL_TOL)


def test_build_features_covers_all_feature_set_columns(reference_data):
    for ptype in PTYPES:
        feats = build_features_batch(_fixture_props(ptype, False), ptype)
        required = set(FEATURE_SETS[ptype]["second"]) - {"interior_score", "layout_score"}
        for f in feats:
            missing = required - set(f.keys())
            assert not missing, f"{ptype}: missing feature columns {sorted(missing)}"


def test_feature_query_count_characterization(reference_data):
    """特徴量生成 N 件あたりの DB クエリ数を記録（Phase 1 で件数非依存の定数化を目指す）"""
    counts = {}
    for n in (1, 4):
        props = (_fixture_props("mansion", False) * 4)[:n]
        build_features_batch(props[:1], "mansion")  # ウォームアップ（初回キャッシュロード分を除外）
        with CaptureQueriesContext(connection) as ctx:
            build_features_batch(props, "mansion")
        counts[str(n)] = len(ctx.captured_queries)
    expected = _check_golden("query_counts/mansion", counts)
    assert counts == expected


# ---------------- 学習・推論ゴールデン ----------------

def _train_tiny_ensembles():
    """固定ダミーデータで種別×ステージの小型アンサンブルを学習（シングルスレッドで決定的）"""
    ensembles = {}
    for ptype in PTYPES:
        df = generate_dummy_data(ptype, num_records=40)
        df["interior_score"] = 3.0
        df["layout_score"] = 3.0
        for stage in ("first", "second"):
            ensembles[(ptype, stage)] = train_and_compare(df.copy(), FEATURE_SETS[ptype][stage], f"golden-{ptype}-{stage}")
    return ensembles


# テスト高速化用の木の本数（CV/重み最適化/スミアリングのロジック検証には十分）
_TINY_TREE_PARAMS = {"lgb": {"n_estimators": 20}, "xgb": {"n_estimators": 20},
                     "cat": {"iterations": 20}, "rf": {"n_estimators": 10}}


@pytest.fixture(scope="module")
def tiny_ensembles():
    original = train_mod._get_regressor

    def _tiny_regressor(name, params):
        return original(name, params).set_params(**_TINY_TREE_PARAMS[name])

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ML_NUM_THREADS", "1")
        mp.setattr(train_mod, "_get_regressor", _tiny_regressor)
        yield _train_tiny_ensembles()


def test_train_and_compare_golden(tiny_ensembles):
    actual = {
        f"{ptype}/{stage}": {
            "weights": {k: round(v, 6) for k, v in sorted(ens.weights.items())},
            "smearing_factor": round(ens.smearing_factor, 6),
        }
        for (ptype, stage), ens in sorted(tiny_ensembles.items())
    }
    expected = _check_golden("train_and_compare", actual)
    for key, exp in expected.items():
        assert actual[key]["weights"] == _approx(exp["weights"], rel=0, abs_tol=WEIGHT_ABS_TOL), key
        assert actual[key]["smearing_factor"] == pytest.approx(exp["smearing_factor"], rel=SMEARING_REL_TOL), key


@pytest.fixture
def patched_registry(tiny_ensembles, monkeypatch):
    """推論側のモデル/重み/スミアリング取得を小型アンサンブルに差し替える（joblib 往復で永続化経路も通す）"""
    with tempfile.TemporaryDirectory() as tmp:
        models = {}
        for (ptype, stage), ens in tiny_ensembles.items():
            loaded = {}
            for algo, model in ens.items():
                path = os.path.join(tmp, f"{ptype}_{stage}_stage_{algo}.joblib")
                joblib.dump(model, path)
                loaded[algo] = joblib.load(path)
            models[(ptype, stage)] = loaded
        weights = {p: {s: tiny_ensembles[(p, s)].weights for s in ("first", "second")} for p in PTYPES}
        smearing = {p: {s: tiny_ensembles[(p, s)].smearing_factor for s in ("first", "second")} for p in PTYPES}
        monkeypatch.setattr(predict_mod, "_get_models_and_master",
                            lambda ptype: (models[(ptype, "first")], models[(ptype, "second")], {}))
        monkeypatch.setattr(predict_mod, "_load_ensemble_weights", lambda _d: weights)
        monkeypatch.setattr(predict_mod, "_load_smearing_factors", lambda _d: smearing)
        yield


def _props_with_type(ptype):
    return [dict(d, propertyType=ptype) for d in PROPERTY_FIXTURES[ptype]]


def test_bulk_predict_golden(reference_data, patched_registry):
    actual = {}
    for ptype in PTYPES:
        props = _props_with_type(ptype)
        n = len(props)
        actual[f"{ptype}/first"] = predict_mod.bulk_predict_first_stage(props)
        actual[f"{ptype}/second"] = predict_mod.bulk_predict_second_stage(
            props, [4.0] * n, [2.5] * n)
    expected = _check_golden("bulk_predict", actual)
    assert actual == _approx(expected, PREDICT_REL_TOL, abs_tol=1)


def test_bulk_predict_mixed_types_preserves_order(reference_data, patched_registry):
    """種別混在入力でも元の順序で結果が返ること"""
    mixed = [p for pair in zip(_props_with_type("mansion"), _props_with_type("tochi")) for p in pair]
    preds = predict_mod.bulk_predict_first_stage(mixed)
    by_type = {
        "mansion": predict_mod.bulk_predict_first_stage(_props_with_type("mansion")),
        "tochi": predict_mod.bulk_predict_first_stage(_props_with_type("tochi")),
    }
    expected = [v for pair in zip(by_type["mansion"], by_type["tochi"]) for v in pair]
    assert preds == expected
