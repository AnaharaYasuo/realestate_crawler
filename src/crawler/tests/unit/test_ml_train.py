# -*- coding: utf-8 -*-
import pytest
from unittest.mock import MagicMock
from package.ml.train import (
    _load_company_properties,
    _extract_unit_price_record,
    build_mkt_comparison_master,
    _get_regressor,
    clean_training_data
)
import pandas as pd
import numpy as np

class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def test_extract_unit_price_record():
    # Test mansion
    p_mansion = MockProperty(
        address1="東京都",
        address2="港区",
        chikunengetsu="2016-04-01",
        senyuMenseki=50.0
    )
    rec = _extract_unit_price_record(p_mansion, 50000000.0, "mansion")
    assert rec is not None
    assert rec["pref"] == "東京都"
    assert rec["city"] == "港区"
    assert rec["ptype"] == "mansion"
    assert rec["unit_price"] == 1000000.0

    # Test tochi
    p_tochi = MockProperty(
        address1="神奈川県",
        address2="横浜市",
        chikunengetsu="2000-01-01",
        tochiMenseki=100.0
    )
    rec_tochi = _extract_unit_price_record(p_tochi, 30000000.0, "tochi")
    assert rec_tochi is not None
    assert rec_tochi["pref"] == "神奈川県"
    assert rec_tochi["unit_price"] == 300000.0

    # Test invalid area
    p_invalid = MockProperty(
        address1="東京都",
        senyuMenseki=0.0
    )
    assert _extract_unit_price_record(p_invalid, 50000000.0, "mansion") is None

def test_load_company_properties():
    p1 = MockProperty(price=30000000, pageUrl="http://example.com/1")
    p2 = MockProperty(price=0, pageUrl="http://example.com/2") # Invalid price
    p3 = MockProperty(price=40000000, pageUrl="http://example.com/3") # Duplicate URL
    
    qs = MagicMock()
    qs.count.return_value = 3
    qs.__iter__.return_value = [p1, p2, p3]
    duplicate_urls = {"http://example.com/3"}
    eval_map = {"http://example.com/1": (4.5, 4.0)}
    
    records = _load_company_properties("mitsui", qs, duplicate_urls, eval_map)
    
    assert len(records) == 1
    assert records[0]["company"] == "mitsui"
    assert records[0]["price"] == 3000.0 # 30000000 / 10000
    assert records[0]["interior_score"] == 4.5
    assert records[0]["layout_score"] == 4.0

def test_build_mkt_comparison_master():
    p1 = MockProperty(
        address1="東京都",
        address2="渋谷区",
        chikunengetsu="2020-01-01",
        senyuMenseki=60.0
    )
    data_by_type = {
        "mansion": [
            {"obj": p1, "price": 6000.0} # price is already converted (divided by 10000) in _load_company_properties
        ],
        "kodate": [],
        "apartment": [],
        "tochi": []
    }
    
    mkt_master = build_mkt_comparison_master(data_by_type)
    
    # Key format: (pref, city, ptype, age_band)
    # 2020 to 2026 is 6 years -> age_band = 0
    key = ("東京都", "渋谷区", "mansion", 0)
    assert key in mkt_master
    assert mkt_master[key] == 100.0 # 6000.0 / 60.0

def test_get_regressor_invalid():
    with pytest.raises(ValueError):
        _get_regressor("invalid_algo", {})

def test_clean_training_data():
    # 1. Empty DataFrame
    df_empty = pd.DataFrame()
    assert clean_training_data(df_empty, "mansion").empty

    # 2. Less than 20 records
    df_small = pd.DataFrame([
        {"price": 1000.0, "area": 50.0, "chikunen": 10.0}
    ])
    res_small = clean_training_data(df_small, "mansion")
    assert len(res_small) == 1

    # 3. More than 20 records (IQR check)
    records = []
    for _ in range(30):
        records.append({"price": 5000.0, "area": 70.0, "chikunen": 15.0})
    # Add outlier
    records.append({"price": 500000.0, "area": 70.0, "chikunen": 15.0})
    df_medium = pd.DataFrame(records)
    res_medium = clean_training_data(df_medium, "mansion")
    assert len(res_medium) == 30

    # 4. More than 100 records (IsolationForest check)
    records_large = []
    for _ in range(120):
        records_large.append({"price": 5000.0, "area": 70.0, "chikunen": 15.0, "tochi_menseki": 100.0})
    # Add outlier
    records_large.append({"price": 999999.0, "area": 70.0, "chikunen": 95.0, "tochi_menseki": 500.0})
    df_large = pd.DataFrame(records_large)
    res_large = clean_training_data(df_large, "kodate")
    assert len(res_large) < 121
