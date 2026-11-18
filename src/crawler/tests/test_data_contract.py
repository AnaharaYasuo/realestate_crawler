from package.validation.data_contract import DataContractConfig, validate_property_batch


def test_data_contract_passes_valid_batch():
    records = [
        {"price": 30000000, "area_sqm": 60.0, "station_name": "新宿"},
        {"price": 45000000, "area_sqm": 75.5, "station_name": "渋谷"},
    ]
    res = validate_property_batch(records, DataContractConfig())
    assert res.passed is True
    assert res.violations == []


def test_data_contract_detects_low_fill_rate():
    records = [
        {"price": None, "area_sqm": None, "station_name": None},
        {"price": 30000000, "area_sqm": None, "station_name": "新宿"},
    ]
    res = validate_property_batch(records, DataContractConfig(min_fill_rate=0.8))
    assert res.passed is False
    assert any("fill_rate" in v for v in res.violations)


def test_data_contract_detects_outlier_ratio():
    records = [
        {"price": -100, "area_sqm": 60.0, "station_name": "新宿"},
        {"price": 30000000, "area_sqm": 0.0, "station_name": "渋谷"},
    ]
    res = validate_property_batch(records, DataContractConfig(max_outlier_ratio=0.1))
    assert res.passed is False
    assert any("outlier" in v for v in res.violations)


def test_data_contract_detects_unknown_station_drift():
    records = [
        {"price": 30000000, "area_sqm": 60.0, "station_name": ""},
        {"price": 40000000, "area_sqm": 70.0, "station_name": None},
    ]
    res = validate_property_batch(records, DataContractConfig(max_unknown_station_ratio=0.2))
    assert res.passed is False
    assert any("unknown_station" in v for v in res.violations)
