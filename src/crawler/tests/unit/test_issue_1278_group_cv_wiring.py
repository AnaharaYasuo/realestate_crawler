# -*- coding: utf-8 -*-
"""Issue #1278: build_features が CV 用グループ列を出力し、学習で GroupKFold が選択されることの保証。"""
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from package.ml.features import FEATURE_SETS, build_features
from package.ml.training.ensemble import _resolve_group_labels, get_cv_strategy
from package.ml.training.tuning import tune_hyperparameters
from sklearn.model_selection import GroupKFold


class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _mansion(name: str, address: str) -> MockProperty:
    return MockProperty(
        propertyName=name,
        senyuMenseki=60.0,
        address=address,
        chikunengetsu="2010-05",
        structure="RC",
    )


@pytest.mark.parametrize("ptype", ["mansion", "kodate", "apartment", "tochi"])
def test_build_features_emits_group_columns(ptype):
    prop = MockProperty(
        propertyName="パークハウス 101号室",
        tochiMenseki=100.0,
        tatemonoMenseki=90.0,
        senyuMenseki=60.0,
        address="東京都港区赤坂1丁目2-3",
    )
    feats = build_features(prop, ptype, building_master_lookup={})
    assert feats["building_group"], "building_group must be non-empty when name/address exist"
    assert feats["chome_group"], "chome_group must be non-empty when address exists"
    assert "港区" in feats["chome_group"]


def test_same_building_gets_same_group_label():
    a = build_features(_mansion("パークハウス　赤坂", "東京都港区赤坂1丁目2-3"), "mansion", building_master_lookup={})
    b = build_features(_mansion("パークハウス赤坂 ", "東京都港区赤坂1丁目2-3"), "mansion", building_master_lookup={})
    c = build_features(_mansion("別マンション", "東京都港区赤坂1丁目9-9"), "mansion", building_master_lookup={})
    assert a["building_group"] == b["building_group"]
    assert a["building_group"] != c["building_group"]


def test_building_group_falls_back_to_address_without_property_name():
    feats = build_features(MockProperty(tochiMenseki=100.0, address="北海道札幌市中央区北1条西2丁目"), "tochi", building_master_lookup={})
    assert feats["building_group"]
    assert "札幌市" in feats["building_group"]


def test_group_columns_are_not_training_features():
    for ptype, stages in FEATURE_SETS.items():
        for stage, cols in stages.items():
            assert "building_group" not in cols and "chome_group" not in cols, (ptype, stage)


def test_get_cv_strategy_selects_group_kfold_on_build_features_output():
    """本番相当: build_features 出力から DataFrame を作ると GroupKFold が選ばれる（ランダムKFoldに落ちない）。"""
    rows = []
    for i in range(60):
        bldg = f"棟{i % 12}"
        rows.append(build_features(_mansion(bldg, f"東京都港区赤坂{i % 12 + 1}丁目1-1"), "mansion", building_master_lookup={}))
    df = pd.DataFrame(rows)
    groups = _resolve_group_labels(df)
    assert groups is not None
    cv, desc = get_cv_strategy(df, groups=groups)
    assert isinstance(cv, GroupKFold), desc


def test_resolve_group_labels_tolerates_some_empty_labels():
    df = pd.DataFrame({"building_group": ["A", "A", "", "B", "", "B", "C", "C"]})
    groups = _resolve_group_labels(df)
    assert groups is not None
    assert len(groups) == len(df)
    # 空ラベルは行ごとに一意な単独グループ（他と衝突しない）
    assert groups[2] != groups[4]
    assert groups[2] not in {"A", "B", "C", ""}


def test_resolve_group_labels_all_empty_returns_none():
    df = pd.DataFrame({"building_group": [""] * 5, "chome_group": [""] * 5})
    assert _resolve_group_labels(df) is None


def test_tune_hyperparameters_uses_group_kfold_when_groups_given():
    rng = np.random.default_rng(0)
    n = 120
    X = pd.DataFrame({"area": rng.uniform(30, 90, n), "chikunen": rng.uniform(0, 40, n)})
    y = pd.Series(np.log1p(rng.uniform(40, 120, n)))
    groups = np.array([f"g{i % 10}" for i in range(n)])
    seen_splits = []
    real_split = GroupKFold.split

    def spy(self, X_, y_=None, groups_=None):
        for tr, va in real_split(self, X_, y_, groups_):
            assert not set(groups_[tr]) & set(groups_[va]), "group leaked across folds"
            seen_splits.append(1)
            yield tr, va

    with patch.object(GroupKFold, "split", spy):
        tune_hyperparameters(X, y, "lgb", groups=groups)
    assert seen_splits, "GroupKFold was not used for tuning"

