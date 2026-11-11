# -*- coding: utf-8 -*-
"""
Unit tests for deterministic (Zero-AI) market rent estimation,
expected gross/net yield calculation, and 10-year DCF theoretical price valuation (Issue #1349).
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from package.ml.dcf_valuation import (
    DCFValuationResult,
    calculate_dcf_theoretical_price,
    calculate_expected_yields,
    estimate_market_rent,
    evaluate_dcf_and_yields,
)
from package.ml.features.reference_records import CapRateBenchmarkRecord


class DummyProp:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ==============================================================================
# 1. Zero Target Leakage & Zero AI Invariance Tests
# ==============================================================================
def test_dcf_valuation_zero_price_and_gross_yield_leakage():
    """
    売出価格 (price) や売主主張の表面利回り (grossYield) を極端に変えても、
    estimated_annual_rent / expected_gross_yield / expected_net_yield / dcf_theoretical_price が
    1円・0.01%たりとも変化しない（ターゲットリーク完全ゼロ）ことを検証する。
    """
    base_kwargs = {
        "address": "東京都世田谷区桜丘1-1-1",
        "address1": "東京都",
        "address2": "世田谷区",
        "station1": "経堂",
        "railwayWalkMinute1": 7,
        "senyuMenseki": 60.0,
        "madori": "2LDK",
        "kouzou": "RC造",
        "chikunengetsuStr": "2012年4月",
        "kaisu": "5階",
        "chijoKaisu": "10階建",
        "kanrihi": 12000,
        "syuzenTsumitate": 11000,
        "tochikenri": "所有権",
        "biko": "南向き・角部屋",
    }
    prop_cheap = DummyProp(price=10_000_000, grossYield=15.0, **base_kwargs)
    prop_expensive = DummyProp(price=800_000_000, grossYield=1.2, **base_kwargs)

    res_cheap = evaluate_dcf_and_yields(prop_cheap, "mansion", interior_score=3.8, layout_score=3.6)
    res_exp = evaluate_dcf_and_yields(prop_expensive, "mansion", interior_score=3.8, layout_score=3.6)

    assert isinstance(res_cheap, DCFValuationResult)
    assert res_cheap.estimated_annual_rent > 0
    assert res_cheap.expected_net_yield > 0
    assert res_cheap.expected_gross_yield > res_cheap.expected_net_yield
    assert res_cheap.dcf_theoretical_price > 0

    assert res_cheap.estimated_annual_rent == res_exp.estimated_annual_rent
    assert res_cheap.expected_gross_yield == res_exp.expected_gross_yield
    assert res_cheap.expected_net_yield == res_exp.expected_net_yield
    assert res_cheap.dcf_theoretical_price == res_exp.dcf_theoretical_price


def test_dcf_valuation_uses_no_ai_network_or_gemini_calls():
    """
    DCF・期待利回り・賃料推定の内部で urllib.request.urlopen や外部AI SDK が一切呼ばれないことを検証。
    """
    prop = DummyProp(
        price=45_000_000,
        address="東京都港区芝浦2-1",
        station1="田町",
        railwayWalkMinute1=6,
        senyuMenseki=55.0,
        kouzou="SRC",
        chikunengetsuStr="2016-05",
    )
    with patch("urllib.request.urlopen", side_effect=AssertionError("External HTTP/AI call is forbidden!")):
        res = evaluate_dcf_and_yields(prop, "mansion")
    assert res.dcf_theoretical_price > 2000
    assert res.estimated_annual_rent > 1_000_000


# ==============================================================================
# 2. Market Rent Estimation (RentMarketPotential + Spec Flavoring)
# ==============================================================================
def test_estimate_market_rent_reflects_rent_market_potential_and_specs():
    """
    RentMarketPotential の駅別相場単価が最優先でアンカーとして使われ、
    面積・築年数・徒歩分数・構造・階数・南向き/角部屋・内装スコアで単調性をもって味付けされること。
    """
    with patch("package.ml.dcf_valuation.query_rent_market_potential") as mock_rent_q:
        mock_rent_q.return_value = (4200, "suumo_soba")

        prime_unit = {
            "address": "東京都渋谷区恵比寿1-1",
            "station1": "恵比寿",
            "railwayWalkMinute1": 4,
            "senyuMenseki": 50.0,
            "madori": "1LDK",
            "kouzou": "RC",
            "chikunen": 3.0,
            "kaisu": "8階",
            "chijoKaisu": "12階建",
            "saikou": "南",
            "kadobeya": "角部屋",
        }
        old_far_unit = {
            "address": "東京都渋谷区恵比寿1-1",
            "station1": "恵比寿",
            "railwayWalkMinute1": 19,
            "senyuMenseki": 50.0,
            "madori": "1LDK",
            "kouzou": "木造",
            "chikunen": 36.0,
            "kaisu": "1階",
            "chijoKaisu": "2階建",
            "saikou": "北",
            "kadobeya": "",
        }

        rent_prime = estimate_market_rent(prime_unit, "mansion", interior_score=4.8, layout_score=4.5)
        rent_old_far = estimate_market_rent(old_far_unit, "mansion", interior_score=2.0, layout_score=2.2)

        assert rent_prime > 2_400_000
        assert rent_old_far > 800_000
        assert rent_prime > int(rent_old_far * 1.45)

        # Higher market rent baseline strictly increases estimated rent
        mock_rent_q.return_value = (5500, "suumo_soba")
        rent_higher_market = estimate_market_rent(prime_unit, "mansion", interior_score=4.8, layout_score=4.5)
        assert rent_higher_market > int(rent_prime * 1.20)


def test_estimate_market_rent_regional_fallback_when_no_rent_potential():
    """
    RentMarketPotential が未ヒットの場合でも、地価・所得・駅乗降客数から合理的な地域別賃料を推計できること。
    """
    with patch("package.ml.dcf_valuation.query_rent_market_potential", return_value=None):
        tokyo_prop = {"address": "東京都千代田区一番町1-1", "senyuMenseki": 60.0, "kouzou": "RC", "chikunen": 5.0, "railwayWalkMinute1": 5}
        rural_prop = {"address": "秋田県能代市柳町1-1", "senyuMenseki": 60.0, "kouzou": "RC", "chikunen": 5.0, "railwayWalkMinute1": 5}

        tokyo_rent = estimate_market_rent(tokyo_prop, "mansion")
        rural_rent = estimate_market_rent(rural_prop, "mansion")

        assert tokyo_rent > rural_rent * 2.0
        assert rural_rent >= 400_000


# ==============================================================================
# 3. Expected Gross & Net Yield Calculation (CapRateBenchmarkPotential + Risks)
# ==============================================================================
def test_calculate_expected_yields_reflects_benchmark_and_risk_factors():
    """
    CapRateBenchmarkPotential のアンカーに加え、築年・構造・旧耐震・借地権・再建築不可・管理費修繕積立金で
    期待実質利回り (expected_net_yield) と期待表面利回り (expected_gross_yield) が合理的に変動すること。
    """
    bench = CapRateBenchmarkRecord(
        prefecture="東京都",
        city="港区",
        station_name="品川",
        asset_type="mansion",
        expected_gross_yield=4.50,
        expected_net_cap_rate=3.40,
        standard_opex_ratio=18.0,
        rental_vacancy_rate=4.2,
        total_vacancy_rate=8.0,
        jgb_spread_bps=240,
        demand_supply_score=1.15,
        sample_count=120,
        survey_period="2026-11",
        source="jrei_survey",
    )

    with patch("package.ml.dcf_valuation.query_cap_rate_benchmark", return_value=bench):
        clean_rc = {
            "address": "東京都港区港南2-1",
            "station1": "品川",
            "railwayWalkMinute1": 5,
            "senyuMenseki": 65.0,
            "kouzou": "RC",
            "chikunen": 4.0,
            "tochikenri": "所有権",
            "biko": "",
            "kanrihi": 14000,
            "syuzenTsumitate": 9000,
        }
        risky_prop = {
            "address": "東京都港区港南2-1",
            "station1": "品川",
            "railwayWalkMinute1": 22,
            "tatemonoMenseki": 90.0,
            "tochiMenseki": 80.0,
            "kouzou": "木造",
            "chikunen": 48.0,  # 旧耐震 & 法定耐用年数超過
            "tochikenri": "借地権",
            "chidai": 25000,
            "biko": "再建築不可 心理的瑕疵あり 私道負担あり",
        }

        gross_clean, net_clean, vac_clean, opex_clean = calculate_expected_yields(
            clean_rc, "mansion", estimated_annual_rent=3_600_000, interior_score=4.2
        )
        gross_risky, net_risky, vac_risky, opex_risky = calculate_expected_yields(
            risky_prop, "kodate", estimated_annual_rent=1_800_000, interior_score=2.0
        )

        assert 2.8 <= net_clean <= 4.5
        assert gross_clean > net_clean
        assert net_risky >= net_clean + 3.0
        assert gross_risky > net_risky
        assert gross_risky > gross_clean + 3.5
        assert vac_risky > vac_clean
        assert 0.05 <= opex_clean <= 0.45
        assert 0.05 <= opex_risky <= 0.55


def test_mansion_actual_hoa_fees_increase_gross_to_net_spread():
    """
    区分マンションで管理費・修繕積立金が高額な物件は、同じ期待実質利回りでも必要な期待表面利回りが高くなり、
    結果として10年DCF理論価格が適切にディスカウントされること。
    """
    low_fee = {
        "address": "東京都目黒区中目黒1-1",
        "station1": "中目黒",
        "railwayWalkMinute1": 6,
        "senyuMenseki": 60.0,
        "kouzou": "RC",
        "chikunen": 15.0,
        "kanrihi": 8000,
        "syuzenTsumitate": 7000,
    }
    high_fee = {
        **low_fee,
        "kanrihi": 38000,
        "syuzenTsumitate": 35000,
    }

    res_low = evaluate_dcf_and_yields(low_fee, "mansion")
    res_high = evaluate_dcf_and_yields(high_fee, "mansion")

    assert res_low.estimated_annual_rent == res_high.estimated_annual_rent
    assert res_high.expected_gross_yield > res_low.expected_gross_yield
    assert res_low.dcf_theoretical_price > res_high.dcf_theoretical_price


# ==============================================================================
# 4. All Property Types Coverage (Mansion, Kodate, Apartment/Invest, Tochi)
# ==============================================================================
@pytest.mark.parametrize(
    ("ptype", "payload"),
    [
        (
            "mansion",
            {
                "address": "東京都文京区本郷3-1",
                "station1": "本郷三丁目",
                "railwayWalkMinute1": 6,
                "senyuMenseki": 58.0,
                "madori": "2LDK",
                "kouzou": "SRC",
                "chikunen": 12.0,
            },
        ),
        (
            "kodate",
            {
                "address": "神奈川県横浜市青葉区美しが丘2-1",
                "station1": "たまプラーザ",
                "railwayWalkMinute1": 11,
                "tatemonoMenseki": 102.0,
                "tochiMenseki": 125.0,
                "madori": "4LDK",
                "kouzou": "木造",
                "chikunen": 10.0,
            },
        ),
        (
            "apartment",
            {
                "address": "大阪府大阪市北区中崎1-1",
                "station1": "中崎町",
                "railwayWalkMinute1": 5,
                "tatemonoMenseki": 240.0,
                "tochiMenseki": 160.0,
                "soukosu": 8,
                "kouzou": "鉄骨造",
                "chikunen": 14.0,
            },
        ),
        (
            "invest_kodate",
            {
                "address": "千葉県船橋市本町4-1",
                "station1": "船橋",
                "railwayWalkMinute1": 9,
                "tatemonoMenseki": 82.0,
                "tochiMenseki": 95.0,
                "kouzou": "木造",
                "chikunen": 22.0,
            },
        ),
        (
            "tochi",
            {
                "address": "東京都品川区小山3-1",
                "station1": "武蔵小山",
                "railwayWalkMinute1": 6,
                "tochiMenseki": 120.0,
                "youseki": 300,
                "kenpei": 80,
                "roadWidth": 6.0,
                "maguchi": 8.0,
                "youtoChiiki": "近隣商業地域",
            },
        ),
    ],
)
def test_evaluate_dcf_all_property_types_positive_and_consistent(ptype, payload):
    res = evaluate_dcf_and_yields(payload, ptype)
    assert res.estimated_annual_rent > 0
    assert 2.0 <= res.expected_net_yield <= 18.0
    assert res.expected_gross_yield > res.expected_net_yield
    assert res.dcf_theoretical_price > 0


def test_tochi_development_dcf_scales_with_far_and_deducts_construction_cost():
    """
    土地 (tochi) の開発型10年DCFでは、同じ土地面積でも容積率が高い土地ほど開発レンタブル床面積が増え、
    想定年間賃料が高く算出されること、また再建築不可の土地は開発不可ペナルティが反映されること。
    """
    low_far_land = {
        "address": "東京都中野区中野5-1",
        "station1": "中野",
        "railwayWalkMinute1": 7,
        "tochiMenseki": 150.0,
        "youseki": 100,
        "kenpei": 50,
        "roadWidth": 5.0,
        "maguchi": 9.0,
        "youtoChiiki": "第一種低層住居専用地域",
    }
    high_far_land = {
        **low_far_land,
        "youseki": 400,
        "kenpei": 80,
        "roadWidth": 8.0,
        "youtoChiiki": "商業地域",
    }
    unbuildable_land = {
        **low_far_land,
        "biko": "再建築不可",
    }

    res_low = evaluate_dcf_and_yields(low_far_land, "tochi")
    res_high = evaluate_dcf_and_yields(high_far_land, "tochi")
    res_unb = evaluate_dcf_and_yields(unbuildable_land, "tochi")

    assert res_high.estimated_annual_rent > res_low.estimated_annual_rent * 2
    assert res_high.dcf_theoretical_price > res_low.dcf_theoretical_price
    assert res_unb.dcf_theoretical_price < res_low.dcf_theoretical_price


def test_dcf_direct_math_monotonicity():
    """
    calculate_dcf_theoretical_price 単体の数理単調性検証:
    - 賃料増加 -> DCF価格増加
    - 期待実質利回り(割引率)上昇 -> DCF価格低下
    - 地代負担・初期CapEx増加 -> DCF価格低下
    """
    base_dcf = calculate_dcf_theoretical_price(
        estimated_annual_rent=6_000_000,
        expected_net_yield=4.5,
        vacancy_rate=0.05,
        opex_ratio=0.18,
        annual_land_rent_yen=0,
        land_residual_man=4000.0,
        bldg_residual_y10_man=1500.0,
        initial_capex_man=0.0,
        rent_decay_rate=0.006,
        capex_ratio=0.04,
        exit_spread_pct=0.6,
    )
    higher_rent_dcf = calculate_dcf_theoretical_price(
        estimated_annual_rent=8_000_000,
        expected_net_yield=4.5,
        vacancy_rate=0.05,
        opex_ratio=0.18,
        annual_land_rent_yen=0,
        land_residual_man=4000.0,
        bldg_residual_y10_man=1500.0,
        initial_capex_man=0.0,
        rent_decay_rate=0.006,
        capex_ratio=0.04,
        exit_spread_pct=0.6,
    )
    higher_cap_dcf = calculate_dcf_theoretical_price(
        estimated_annual_rent=6_000_000,
        expected_net_yield=6.5,
        vacancy_rate=0.05,
        opex_ratio=0.18,
        annual_land_rent_yen=0,
        land_residual_man=4000.0,
        bldg_residual_y10_man=1500.0,
        initial_capex_man=0.0,
        rent_decay_rate=0.006,
        capex_ratio=0.04,
        exit_spread_pct=0.6,
    )
    with_capex_and_ground_rent_dcf = calculate_dcf_theoretical_price(
        estimated_annual_rent=6_000_000,
        expected_net_yield=4.5,
        vacancy_rate=0.05,
        opex_ratio=0.18,
        annual_land_rent_yen=600_000,
        land_residual_man=2500.0,
        bldg_residual_y10_man=1500.0,
        initial_capex_man=500.0,
        rent_decay_rate=0.006,
        capex_ratio=0.04,
        exit_spread_pct=0.6,
    )

    assert higher_rent_dcf > base_dcf
    assert higher_cap_dcf < base_dcf
    assert with_capex_and_ground_rent_dcf < base_dcf - 500


def test_object_attribute_lookup_fallback_ptype_and_layout_bucket():
    """
    オブジェクト属性取得(_get_val)、未知の種別指定時のデフォルト種別正規化、および
    madori未指定・70㎡以上時の3LDKバケット解決を検証しミュータント残存を防ぐ。
    """
    obj_prop = DummyProp(
        address="東京都世田谷区桜丘1-1",
        station1="経堂",
        railwayWalkMinute1=4,
        senyuMenseki=78.0,  # madori未指定かつ >= 68.0 -> "3LDK" バケット
        kouzou="SRC",
        chikunen=2.0,
        saikou="南",
        kadobeya="角部屋",
    )
    obj_older_distant = DummyProp(
        address="東京都世田谷区桜丘1-1",
        station1="経堂",
        railwayWalkMinute1=22,
        senyuMenseki=78.0,
        kouzou="木造",
        chikunen=35.0,
    )
    with patch("package.ml.dcf_valuation.query_rent_market_potential") as mock_rent_q:
        mock_rent_q.side_effect = lambda prefecture, city, station_name, building_type, layout_type: (
            (3800.0, 190000, 12, "station") if layout_type == "3LDK" and building_type == "mansion" else None
        )
        res_prime = evaluate_dcf_and_yields(obj_prop, "")
        res_old = evaluate_dcf_and_yields(obj_older_distant, "unknown_custom_type")

    assert res_prime.estimated_annual_rent > res_old.estimated_annual_rent
    assert res_prime.dcf_theoretical_price > res_old.dcf_theoretical_price
    mock_rent_q.assert_any_call(
        prefecture="東京都",
        city="世田谷区",
        station_name="経堂",
        building_type="mansion",
        layout_type="3LDK",
    )


# ==============================================================================
# 5. Pipeline Integration Tests (record_builder, API routes, Slack msg)
# ==============================================================================
def test_record_builder_populates_dcf_and_expected_yields():
    from package.ml.evaluation.persistence import BASE_UPDATE_FIELDS
    from package.ml.evaluation.record_builder import build_or_update_eval_record

    for col in ("expected_gross_yield", "expected_net_yield", "estimated_annual_rent", "dcf_theoretical_price"):
        assert col in BASE_UPDATE_FIELDS

    item = DummyProp(
        id=101,
        pageUrl="https://example.com/mansion/101",
        price=42_000_000,
        propertyName="テストレジデンス経堂",
        address="東京都世田谷区桜丘1-1",
        station1="経堂",
        railwayWalkMinute1=8,
        senyuMenseki=62.0,
        kouzou="RC",
        chikunengetsuStr="2014年3月",
    )
    rec, is_new = build_or_update_eval_record(
        item=item,
        price_stage1=4600.0,
        existing=None,
        company="mitsui",
        property_type="mansion",
        skip_duplicate_check=True,
    )
    assert is_new is True
    assert rec.expected_gross_yield is not None and Decimal(rec.expected_gross_yield) > Decimal(0)
    assert rec.expected_net_yield is not None and Decimal(rec.expected_net_yield) > Decimal(0)
    assert rec.estimated_annual_rent is not None and rec.estimated_annual_rent > 0
    assert rec.dcf_theoretical_price is not None and rec.dcf_theoretical_price > 0


def test_evaluation_api_returns_dcf_and_expected_yields():
    from main import app

    app.config["TESTING"] = True
    payload = {
        "property_data": {
            "price": 45_000_000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "senyuMenseki": 60.0,
            "chikunengetsuStr": "平成22年5月",
            "railwayWalkMinute1": 8,
            "kouzou": "RC",
        },
        "interior_score": 4.0,
        "layout_score": 3.5,
    }
    with patch("routes.evaluation_routes.predict_first_stage_local", return_value=4700), \
         patch("routes.evaluation_routes.predict_second_stage_local", return_value=4850), \
         app.test_client() as client:
        resp = client.post(
            "/api/evaluation/predict/mansion",
            data=json.dumps(payload),
            content_type="application/json",
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["expected_gross_yield"] > body["expected_net_yield"] > 0
    assert body["estimated_annual_rent"] > 0
    assert body["dcf_theoretical_price"] > 0


def test_send_recommendations_message_includes_dcf_and_yields():
    from scripts.ops.send_recommendations import _build_recommendation_msg

    eval_rec = MagicMock()
    eval_rec.property_type = "mansion"
    eval_rec.property_url = "https://example.com/mansion/999"
    eval_rec.first_stage_predicted_price = Decimal(5200)
    eval_rec.second_stage_predicted_price = Decimal(5400)
    eval_rec.estimated_sekisan_price = Decimal(3800)
    eval_rec.expected_gross_yield = Decimal("5.40")
    eval_rec.expected_net_yield = Decimal("4.10")
    eval_rec.estimated_annual_rent = 2_400_000
    eval_rec.dcf_theoretical_price = 4950
    eval_rec.cash_flow = None
    eval_rec.dscr = None

    prop = DummyProp(
        price=42_000_000,
        propertyName="パークホームズ世田谷",
        address="東京都世田谷区桜丘1-1",
        railway1="小田急線",
        station1="経堂",
        railwayWalkMinute1=7,
        senyuMensekiStr="65.0㎡",
        madori="3LDK",
        chikunengetsuStr="2015年4月",
    )

    msg = _build_recommendation_msg(
        eval_rec=eval_rec,
        prop=prop,
        reason="【市場予測価格より 22.2% 割安】",
        p_name="パークホームズ世田谷",
        report_data={},
    )
    assert "4,950万円" in msg or "4950万円" in msg
    assert "5.40%" in msg
    assert "4.10%" in msg


# ==============================================================================
# 6. Market Calibration & Anti-Double-Counting Regression Tests (Issue #1361)
# ==============================================================================
def test_cap_rate_benchmark_prefers_exact_asset_type_and_filters_tiny_sample_outliers():
    """
    Issue #1361:
    1) 同一地域に homes_toushi(asset_type='all', 高利回り混合) と jrei_survey(asset_type='mansion') がある場合、
       mansion 検索時は asset_type 完全一致の jrei_survey を優先し、空室率は同地域のドナーから補完できること。
    2) internal_db の極端な少数サンプル外れ値 (sample_count < 3 かつ net > 7.5%) は除外され、
       健全なベンチマークへフォールバックすること。
    """
    from package.ml.features import reference_data

    mixed_homes_high_prio = CapRateBenchmarkRecord(
        prefecture="東京都",
        city="港区",
        station_name="",
        asset_type="all",
        expected_gross_yield=7.90,
        expected_net_cap_rate=6.30,
        standard_opex_ratio=20.0,
        rental_vacancy_rate=19.3,
        total_vacancy_rate=19.3,
        jgb_spread_bps=515,
        demand_supply_score=1.1,
        sample_count=50,
        survey_period="2026-11",
        source="homes_toushi",
    )
    mansion_reit_exact = CapRateBenchmarkRecord(
        prefecture="東京都",
        city="港区",
        station_name="",
        asset_type="mansion",
        expected_gross_yield=4.20,
        expected_net_cap_rate=3.45,
        standard_opex_ratio=18.0,
        rental_vacancy_rate=None,
        total_vacancy_rate=None,
        jgb_spread_bps=230,
        demand_supply_score=None,
        sample_count=None,
        survey_period="2026-H2",
        source="japan_reit",
    )
    outlier_internal = CapRateBenchmarkRecord(
        prefecture="神奈川県",
        city="川崎市麻生区",
        station_name="百合ヶ丘",
        asset_type="kodate",
        expected_gross_yield=12.40,
        expected_net_cap_rate=9.92,
        standard_opex_ratio=20.0,
        rental_vacancy_rate=None,
        total_vacancy_rate=None,
        jgb_spread_bps=877,
        demand_supply_score=None,
        sample_count=1,
        survey_period="",
        source="internal_db",
    )
    pref_kodate_jrei = CapRateBenchmarkRecord(
        prefecture="神奈川県",
        city="",
        station_name="",
        asset_type="kodate",
        expected_gross_yield=6.31,
        expected_net_cap_rate=5.05,
        standard_opex_ratio=20.0,
        rental_vacancy_rate=None,
        total_vacancy_rate=None,
        jgb_spread_bps=390,
        demand_supply_score=None,
        sample_count=None,
        survey_period="2026-H2",
        source="jrei_survey",
    )

    fake_cache = {
        ("東京都", "港区", "", "mansion"): [mansion_reit_exact],
        ("東京都", "港区", "", "all"): [mixed_homes_high_prio],
        ("神奈川県", "川崎市麻生区", "百合ヶ丘", "kodate"): [outlier_internal],
        ("神奈川県", "", "", "kodate"): [pref_kodate_jrei],
    }
    with (
        patch.object(reference_data, "_init_global_caches"),
        patch.object(reference_data, "_cap_rate_cache", fake_cache),
    ):
        picked_mansion = reference_data.query_cap_rate_benchmark("東京都", "港区", "麻布十番", "mansion")
        assert picked_mansion is not None
        assert picked_mansion.asset_type == "mansion"
        assert picked_mansion.source == "japan_reit"
        assert picked_mansion.expected_net_cap_rate == pytest.approx(3.45)
        assert picked_mansion.rental_vacancy_rate == pytest.approx(19.3)

        picked_kodate = reference_data.query_cap_rate_benchmark("神奈川県", "川崎市麻生区", "百合ヶ丘", "kodate")
        assert picked_kodate is not None
        assert picked_kodate.source == "jrei_survey"
        assert picked_kodate.expected_net_cap_rate == pytest.approx(5.05)


def test_calibrated_expected_gross_yields_match_market_reality():
    """
    Issue #1361:
    - 都心標準的な築12年RC区分マンションで統計上の総空室率(19.3%)が高くても、期待表面利回りが4.2%〜6.2%の実勢帯に収まること。
    - 超コンパクトまたは管理費高めのヴィンテージ区分マンションでも、期待表面利回りが15%超に暴発せず11.5%以下に収まること。
    - 首都圏郊外の一般的な木造戸建（再建築可・所有権）で構造スプレッド二重計上が起きず、期待表面利回りが6.5%〜10.5%の実勢帯に収まること。
    """
    minato_bench = CapRateBenchmarkRecord(
        prefecture="東京都",
        city="港区",
        station_name="",
        asset_type="mansion",
        expected_gross_yield=4.20,
        expected_net_cap_rate=3.45,
        standard_opex_ratio=18.0,
        rental_vacancy_rate=19.3,  # 総務省総住宅空室率相当の高い生値
        total_vacancy_rate=19.3,
        jgb_spread_bps=230,
        demand_supply_score=1.1,
        sample_count=50,
        survey_period="2026-H2",
        source="jrei_survey",
    )
    with patch("package.ml.dcf_valuation.query_cap_rate_benchmark", return_value=minato_bench):
        std_mansion = {
            "address": "東京都港区芝浦3-1",
            "address1": "東京都",
            "address2": "港区",
            "station1": "田町",
            "railwayWalkMinute1": 7,
            "senyuMenseki": 58.0,
            "madori": "2LDK",
            "kouzou": "RC",
            "chikunen": 12.0,
            "kanrihi": 13500,
            "syuzenTsumitate": 11500,
            "tochikenri": "所有権",
        }
        gy_std, ny_std, vac_std, _ = calculate_expected_yields(
            std_mansion, "mansion", estimated_annual_rent=3_000_000, interior_score=3.2
        )
        assert 3.2 <= ny_std <= 4.3
        assert 4.2 <= gy_std <= 6.2
        assert 0.03 <= vac_std <= 0.08

        vintage_high_hoa_mansion = {
            "address": "東京都港区元麻布2-1",
            "address1": "東京都",
            "address2": "港区",
            "station1": "麻布十番",
            "railwayWalkMinute1": 9,
            "senyuMenseki": 18.0,
            "madori": "1R",
            "kouzou": "RC",
            "chikunen": 46.0,
            "kanrihi": 14000,
            "syuzenTsumitate": 13000,
            "tochikenri": "所有権",
        }
        gy_vint, ny_vint, _, _ = calculate_expected_yields(
            vintage_high_hoa_mansion, "mansion", estimated_annual_rent=960_000, interior_score=3.0
        )
        assert ny_vint > ny_std
        assert gy_vint < 11.5

    kanagawa_kodate_bench = CapRateBenchmarkRecord(
        prefecture="神奈川県",
        city="横浜市青葉区",
        station_name="",
        asset_type="kodate",
        expected_gross_yield=6.40,
        expected_net_cap_rate=5.10,
        standard_opex_ratio=20.0,
        rental_vacancy_rate=13.5,
        total_vacancy_rate=13.5,
        jgb_spread_bps=395,
        demand_supply_score=1.0,
        sample_count=20,
        survey_period="2026-H2",
        source="jrei_survey",
    )
    with patch("package.ml.dcf_valuation.query_cap_rate_benchmark", return_value=kanagawa_kodate_bench):
        suburban_kodate = {
            "address": "神奈川県横浜市青葉区美しが丘2-1",
            "address1": "神奈川県",
            "address2": "横浜市青葉区",
            "station1": "たまプラーザ",
            "railwayWalkMinute1": 12,
            "tatemonoMenseki": 98.0,
            "tochiMenseki": 120.0,
            "kouzou": "木造",
            "chikunen": 18.0,
            "tochikenri": "所有権",
        }
        gy_kod, ny_kod, _, _ = calculate_expected_yields(
            suburban_kodate, "kodate", estimated_annual_rent=1_920_000, interior_score=3.0
        )
        assert 4.8 <= ny_kod <= 6.8
        assert 6.5 <= gy_kod <= 9.8

