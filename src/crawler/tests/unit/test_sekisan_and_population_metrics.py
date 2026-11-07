# -*- coding: utf-8 -*-
import pytest
from package.models.evaluation import PropertyEvaluation, LandPricePotential, MunicipalPotential, MunicipalFuturePotential
from package.ml.investment_evaluator import calculate_sekisan_price
from scripts.data_import.sync_estat_municipalities import sync_municipalities
from scripts.maintenance.recover_sekisan_prices import resolve_model_for_eval


class DummyProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.django_db
def test_calculate_sekisan_price_supports_land_area_and_building_area():
    """土地・戸建等で landArea / buildingArea プロパティ名から積算価格が算出できることを検証 (Issue #1242)"""
    LandPricePotential.objects.create(
        prefecture="東京都",
        city="練馬区",
        average_land_price=443806,
        land_use="residential",
    )

    prop = DummyProperty(
        id=999991,
        company="nomu",
        pageUrl="https://www.nomu.com/land/id/test1/",
        address="東京都練馬区三原台3丁目",
        price=178000000,
        landArea=352.0,
        buildingArea=None,
        buildYear=None,
        construction=None,
    )

    sekisan = calculate_sekisan_price(prop, "東京都", "練馬区")
    assert sekisan > 0
    # 練馬区三原台3丁目の積算公示地価約44万/㎡ * 352㎡ ≒ 15,622万円
    assert 10000 <= sekisan <= 20000


@pytest.mark.django_db
def test_sync_estat_municipalities_links_future_potential():
    """社人研将来推計人口（2025年）の pop_change_rate_from_2020 が population_growth_rate に反映されることを検証 (Issue #1242)"""
    MunicipalFuturePotential.objects.create(
        prefecture="東京都",
        city="千代田区",
        target_year=2025,
        projected_population=68000,
        pop_change_rate_from_2020=3.25,
        working_age_ratio=65.0,
        elderly_ratio=18.0,
    )

    sample_csv = "prefecture,city,average_income,total_population,population_growth_rate,income_growth_rate,population_density\n東京都,千代田区,10000000,67000,0.0,1.2,5000\n"
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8") as f:
        f.write(sample_csv)
        tmp_path = f.name

    try:
        sync_municipalities(csv_path=tmp_path)
        muni = MunicipalPotential.objects.get(prefecture="東京都", city="千代田区")
        assert muni.population_growth_rate == pytest.approx(3.25, abs=1e-2)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@pytest.mark.django_db
def test_recover_sekisan_prices_resolve_model():
    """recover_sekisan_prices の resolve_model_for_eval が各モデルを正しく解決できることを検証"""
    rec = PropertyEvaluation(
        company="nomu",
        property_type="tochi",
        property_id=1,
    )
    model_cls = resolve_model_for_eval(rec)
    assert model_cls is not None
    assert model_cls.__name__ == "NomuraTochi"
