# -*- coding: utf-8 -*-
"""
ML リファクタリング安全網: 値に依存しない不変条件テスト (Issue #711, Epic #710)

元モデル精度が高くないため出力値の固定(ゴールデン)は行わず、以下のみ検証する:
- 特徴量: 全 FEATURE_SETS 列が揃い、数値が有限であること / dict 入力と属性オブジェクト入力で同一結果
- 推論: ダミーモデルで正の有限値が返ること / 種別混在入力でも元の順序を保つこと
精度劣化は学習時の CV MAPE ゲート(+2.0pt 以内)で別途担保する。
"""
import math
from decimal import Decimal

import numpy as np
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

import package.ml.features as feat_mod
import package.ml.predict as predict_mod
from package.ml.features import FEATURE_SETS, build_features_batch
from package.models.evaluation import (
    HazardMapPotential,
    LandPricePotential,
    MacroEconomicIndex,
    MunicipalPotential,
    StationPotential,
    UrbanPlanningZonePotential,
)

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


@pytest.mark.parametrize("ptype", PTYPES)
def test_features_complete_and_finite(reference_data, ptype):
    required = set(FEATURE_SETS[ptype]["second"]) - {"interior_score", "layout_score"}
    for f in build_features_batch(_fixture_props(ptype, False), ptype):
        missing = required - set(f.keys())
        assert not missing, f"{ptype}: missing feature columns {sorted(missing)}"
        for col in required:
            v = f[col]
            if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                assert not math.isinf(float(v)), f"{ptype}.{col} is inf"


@pytest.mark.parametrize("ptype", PTYPES)
def test_features_same_for_dict_and_object_input(reference_data, ptype):
    as_dict = build_features_batch(_fixture_props(ptype, False), ptype)
    as_obj = build_features_batch(_fixture_props(ptype, True), ptype)
    assert len(as_dict) == len(as_obj)
    for d, o in zip(as_dict, as_obj):
        assert d.keys() == o.keys()
        for k in d:
            dv, ov = d[k], o[k]
            if isinstance(dv, float) and math.isnan(dv):
                assert isinstance(ov, float) and math.isnan(ov), k
            else:
                assert dv == ov, k


def test_feature_query_count_independent_of_batch_size(reference_data):
    """N+1 回帰防止: 特徴量生成のクエリ数が件数に依存しないこと (#712)"""
    counts = {}
    for n in (1, 4):
        props = (_fixture_props("mansion", False) * 4)[:n]
        build_features_batch(props[:1], "mansion")  # 参照マスタのロード分を除外
        with CaptureQueriesContext(connection) as ctx:
            build_features_batch(props, "mansion")
        counts[n] = len(ctx.captured_queries)
    assert counts[1] == counts[4], counts


class _RowModel:
    """行内容に依存する決定的なダミーモデル（log 価格空間で 15〜17 程度を返す）"""
    def predict(self, X):
        arr = np.nan_to_num(np.asarray(X, dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        return 15.0 + (np.abs(arr).sum(axis=1) % 2.0)


@pytest.fixture
def dummy_registry(monkeypatch):
    """推論側のモデル/重み/スミアリング取得をダミーに差し替える（学習不要で高速）"""
    algos = ("lgb", "xgb", "cat", "rf")
    models = {algo: _RowModel() for algo in algos}
    weights = {p: {s: {a: 0.25 for a in algos} for s in ("first", "second")} for p in PTYPES}
    smearing = {p: {s: 1.0 for s in ("first", "second")} for p in PTYPES}
    monkeypatch.setattr(predict_mod, "_get_models_and_master", lambda ptype: (models, models, {}))
    monkeypatch.setattr(predict_mod, "_load_ensemble_weights", lambda _d: weights)
    monkeypatch.setattr(predict_mod, "_load_smearing_factors", lambda _d: smearing)


def _props_with_type(ptype):
    return [dict(d, propertyType=ptype) for d in PROPERTY_FIXTURES[ptype]]


@pytest.mark.parametrize("ptype", PTYPES)
def test_bulk_predict_returns_positive_finite(reference_data, dummy_registry, ptype):
    props = _props_with_type(ptype)
    n = len(props)
    for preds in (predict_mod.bulk_predict_first_stage(props),
                  predict_mod.bulk_predict_second_stage(props, [4.0] * n, [2.5] * n)):
        assert len(preds) == n
        for p in preds:
            assert p is not None and math.isfinite(p) and p > 0, f"{ptype}: invalid prediction {p}"


def test_bulk_predict_mixed_types_preserves_order(reference_data, dummy_registry):
    """種別混在入力でも元の順序で結果が返ること"""
    mixed = [p for pair in zip(_props_with_type("mansion"), _props_with_type("tochi")) for p in pair]
    preds = predict_mod.bulk_predict_first_stage(mixed)
    by_type = {
        "mansion": predict_mod.bulk_predict_first_stage(_props_with_type("mansion")),
        "tochi": predict_mod.bulk_predict_first_stage(_props_with_type("tochi")),
    }
    expected = [v for pair in zip(by_type["mansion"], by_type["tochi"]) for v in pair]
    assert preds == expected
