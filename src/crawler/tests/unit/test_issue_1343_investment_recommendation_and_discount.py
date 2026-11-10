# -*- coding: utf-8 -*-
"""
Issue #1343: アパート・投資物件の割安判定通知未達バグ修正・リーク排除・ディスカウント率カット緩和の単体テスト
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from django.utils import timezone

from package.ml.features.feature_sets import FEATURE_SETS
from package.ml.features.appraisal import calculate_income_approach_value, _resolve_cap_rate
from package.ml.training.data_loader import collect_model_classes_by_type
from package.utils.batch_metrics import BatchMetrics
from scripts.ops.send_recommendations import (
    _evaluate_candidate,
    _fetch_recommendation_candidates,
    _get_target_slack_channel,
    _select_two_stage_recommendations,
    batch_resolve_properties,
    get_property_record,
)


def test_apartment_feature_sets_exclude_gross_yield_leakage():
    """FEATURE_SETS['apartment'] にターゲットリーク原因となる gross_yield が含まれず、annual_rent は維持されていること"""
    assert "gross_yield" not in FEATURE_SETS["apartment"]["first"]
    assert "gross_yield" not in FEATURE_SETS["apartment"]["second"]
    assert "annual_rent" in FEATURE_SETS["apartment"]["first"]
    assert "annual_rent" in FEATURE_SETS["apartment"]["second"]


def test_income_approach_value_does_not_leak_asking_price_via_gross_yield():
    """
    同じ年間賃料収入・同じ立地の2つの投資物件において、売出価格（＝表面利回り grossYield）が異なっても
    income_approach_value が売出価格に追随せず同一の客観的収益還元価値を返すことを検証。
    """
    # 物件A: 売出1億円、年間家賃800万円 (表面利回り 8.0%)
    prop_expensive = {
        "grossYield": Decimal("8.00"),
        "annualRent": 8000000,
    }
    # 物件B: 売出5000万円（超割安！）、年間家賃800万円 (表面利回り 16.0%)
    prop_bargain = {
        "grossYield": Decimal("16.00"),
        "annualRent": 8000000,
    }

    val_a, _, _ = calculate_income_approach_value(
        prop_expensive,
        property_type="apartment",
        income=5000.0,
        average_land_price=300000.0,
        potential_floor_area=200.0,
        eval_area=200.0,
        tochi_area=150.0,
        scale_discount=1.0,
    )
    val_b, _, _ = calculate_income_approach_value(
        prop_bargain,
        property_type="apartment",
        income=5000.0,
        average_land_price=300000.0,
        potential_floor_area=200.0,
        eval_area=200.0,
        tochi_area=150.0,
        scale_discount=1.0,
    )

    # 従来は val_a = 8500万円, val_b = 4250万円 と売出価格の85%にリークしていた。
    # 修正後は両方とも同じ年間家賃・同じ地域キャップレートから算出されるため完全に一致する。
    assert val_a == pytest.approx(val_b)
    assert val_b > 10000.0  # 年間家賃800万(NOI 680万) / 5% = 13,600万円


def test_collect_model_classes_by_type_includes_all_investment_models():
    """collect_model_classes_by_type() に汎用 *Investment および KenbiyaInvestmentBuilding が含まれること"""
    by_type = collect_model_classes_by_type()
    all_collected = {cls.__name__ for ptype_list in by_type.values() for _, cls in ptype_list}

    expected_investment_models = {
        "ReguideInvestment",
        "OdakyuInvestment",
        "SmtrcInvestment",
        "Sumai1Investment",
        "SumirinInvestment",
        "MizuhoInvestment",
        "KenbiyaInvestmentBuilding",
    }
    missing = expected_investment_models - all_collected
    assert not missing, f"Investment models missing from training collection: {missing}"


def test_relaxed_discount_rate_thresholds_for_investment_and_residential():
    """
    ディスカウント率によるカット緩和の検証:
    - 15.0%〜60.0% の割安率（予測価格が売出価格の約1.18倍〜2.5倍）が推奨対象として通過すること
    - 15.0%未満（例: 10%割安）や 60.0%超（例: 予測が売出の3倍＝66.7%割安）は除外されること
    """
    prop = MagicMock()
    prop.pageUrl = "https://example.com/apt/1"
    prop.price = 40000000  # 4,000万円
    for i in range(1, 6):
        setattr(prop, f"station{i}", "新宿")
        setattr(prop, f"busUse{i}", 0)
        setattr(prop, f"busWalkMinute{i}", 0)

    # 1. 投資物件: 18% 割安 (売出4,000万 / 予測4,878万) -> 緩和により通過!
    eval_18 = MagicMock(
        property_type="investmentapartment",
        first_stage_predicted_price=4878.0,
        second_stage_predicted_price=None,
        total_investment_score=80.0,
        investment_score=80.0,
    )
    is_rec, reason, prio = _evaluate_candidate(eval_18, prop)
    assert is_rec is True
    assert "18.0% 割安" in reason

    # 2. 投資物件: 45% 割安 (売出4,000万 / 予測7,272万 -> 1.82倍) -> 予想価格が高めに出たケースも通過!
    eval_45 = MagicMock(
        property_type="investmentapartment",
        first_stage_predicted_price=7272.0,
        second_stage_predicted_price=None,
        total_investment_score=80.0,
        investment_score=80.0,
    )
    is_rec, reason, prio = _evaluate_candidate(eval_45, prop)
    assert is_rec is True
    assert "45.0% 割安" in reason

    # 3. 住居系物件: 45% 割安 (売出4,000万 / 予測7,272万) -> 従来は35%以上で除外されていたが緩和により通過!
    eval_res_45 = MagicMock(
        property_type="mansion",
        first_stage_predicted_price=7272.0,
        second_stage_predicted_price=None,
    )
    is_rec, reason, prio = _evaluate_candidate(eval_res_45, prop)
    assert is_rec is True
    assert "45.0% 割安" in reason

    # 4. 住居系物件: 17% 割安 (売出4,000万 / 予測4,819万) -> 緩和により通過!
    eval_res_17 = MagicMock(
        property_type="kodate",
        first_stage_predicted_price=4819.0,
        second_stage_predicted_price=None,
    )
    is_rec, reason, prio = _evaluate_candidate(eval_res_17, prop)
    assert is_rec is True

    # 5. 極端な異常乖離 (売出4,000万 / 予測12,000万 = 3.0倍, 66.7%割安 > 60%) -> 除外
    eval_extreme = MagicMock(
        property_type="investmentapartment",
        first_stage_predicted_price=12000.0,
        second_stage_predicted_price=None,
        total_investment_score=80.0,
        investment_score=80.0,
    )
    is_rec, _, _ = _evaluate_candidate(eval_extreme, prop)
    assert is_rec is False


@pytest.mark.django_db
def test_fetch_recommendation_candidates_filters_passed_and_non_duplicate():
    """
    _fetch_recommendation_candidates が is_first_stage_passed=True かつ duplicate_of__isnull=True かつ
    first_stage_predicted_price > 0 のレコードのみを抽出し、不合格レコードに枠を潰されないことを検証。
    """
    from package.models.evaluation import PropertyEvaluation

    now = timezone.now()
    # 合格レコード (古いID)
    passed_rec = PropertyEvaluation.objects.create(
        company="homes",
        property_type="investmentapartment",
        property_id=1,
        property_url="https://example.com/apt-passed",
        is_published=True,
        is_slack_notified=False,
        needs_recrawl=False,
        is_first_stage_passed=True,
        first_stage_predicted_price=5000,
        analyzed_at=now,
    )
    # 不合格レコード (新しいID)
    failed_rec = PropertyEvaluation.objects.create(
        company="homes",
        property_type="investmentapartment",
        property_id=2,
        property_url="https://example.com/apt-failed",
        is_published=True,
        is_slack_notified=False,
        needs_recrawl=False,
        is_first_stage_passed=False,
        first_stage_predicted_price=3000,
        analyzed_at=now,
    )
    # 予測価格0の異常レコード (新しいID)
    zero_rec = PropertyEvaluation.objects.create(
        company="reguide",
        property_type="investment",
        property_id=3,
        property_url="https://example.com/inv-zero",
        is_published=True,
        is_slack_notified=False,
        needs_recrawl=False,
        is_first_stage_passed=True,
        first_stage_predicted_price=0,
        analyzed_at=now,
    )

    cands = _fetch_recommendation_candidates(limit=100)
    urls = {c.property_url for c in cands}
    assert passed_rec.property_url in urls
    assert failed_rec.property_url not in urls
    assert zero_rec.property_url not in urls


@pytest.mark.django_db
def test_batch_resolve_properties_fallback_by_property_id_and_model_aliases():
    """
    URLにクエリパラメータが付与されている場合（athome等）や property_type='apartment' の場合でも
    property_id フォールバックおよびモデル名柔軟一致により実物件が解決できることを検証。
    """
    from package.models.athome import AthomeInvestmentApartment
    from package.models.evaluation import PropertyEvaluation

    apt = AthomeInvestmentApartment.objects.create(
        pageUrl="https://www.athome.co.jp/buy_other/1066689698/",
        propertyName="アットホーム一棟アパート",
        price=45000000,
    )
    # PropertyEvaluation 側はクエリパラメータ付きURLを持つケース
    ev = PropertyEvaluation.objects.create(
        company="athome",
        property_type="investmentapartment",
        property_id=apt.id,
        property_url="https://www.athome.co.jp/buy_other/1066689698/?BKLISTID=001LPC",
        is_published=True,
        is_slack_notified=False,
        is_first_stage_passed=True,
        first_stage_predicted_price=6000,
    )

    resolved = batch_resolve_properties([ev])
    assert ev.property_url in resolved
    assert resolved[ev.property_url].id == apt.id

    single = get_property_record(ev)
    assert single is not None
    assert single.id == apt.id


def test_get_target_slack_channel_routes_generic_investment_accurately(monkeypatch):
    """
    property_type='investment' (ReguideInvestment, OdakyuInvestment, Sumai1Investment 等) や
    property_type='investmentbuilding' において、物件名に『アパート』が含まれなくても
    PropertyTypeDetector の判定に基づき一棟アパート・ビルが goodproperty-invest-apartment へルーティングされること。
    """
    monkeypatch.delenv("SLACK_RECOMMEND_INVEST_APARTMENT", raising=False)
    monkeypatch.delenv("SLACK_RECOMMEND_INVEST_KODATE", raising=False)

    # 1. ReguideInvestment で物件名が建物名のみ（『サンパレス井草』）だが grossYield と延床面積250㎡を持つ一棟物件
    class DummyReguideInvestment:
        propertyName = "サンパレス井草"
        grossYield = Decimal("7.50")
        tatemonoMenseki = Decimal("250.00")
        tochiMenseki = Decimal("180.00")
        senyuMenseki = None

    ev_inv = MagicMock(property_type="investment")
    prop_apt = DummyReguideInvestment()
    ch = _get_target_slack_channel(ev_inv, prop_apt, prop_apt.propertyName)
    assert ch == "goodproperty-invest-apartment"

    # 2. ReguideInvestment で物件名に『戸建賃貸』を含む投資戸建て
    class DummyReguideKodate:
        propertyName = "戸建賃貸 大東市南郷町"
        grossYield = Decimal("9.20")
        tatemonoMenseki = Decimal("65.00")
        tochiMenseki = Decimal("55.00")
        senyuMenseki = None

    prop_kodate = DummyReguideKodate()
    ch_k = _get_target_slack_channel(ev_inv, prop_kodate, prop_kodate.propertyName)
    assert ch_k == "goodproperty-invest-kodate"

    # 3. KenbiyaInvestmentBuilding (property_type='investmentbuilding')
    ev_bldg = MagicMock(property_type="investmentbuilding")
    ch_b = _get_target_slack_channel(ev_bldg, prop_apt, "一棟商業ビル")
    assert ch_b == "goodproperty-invest-apartment"


def test_two_stage_recommendations_balances_invest_apartment_and_kodate():
    """
    investment カテゴリの選抜において、一棟アパート（investmentapartment）と収益戸建て（investmentkodate）の
    双方が候補にある場合、片方だけで5件枠が独占されず両方とも選出されることを検証。
    """
    apt_cands = []
    for i in range(6):
        ev = MagicMock(
            id=f"apt_{i}",
            property_type="investmentapartment",
            investment_rating="AA",
            capital_gain_score=80.0 - i,
        )
        prop = MagicMock(propertyName=f"一棟アパート{i}")
        apt_cands.append((95.0 - i, ev, prop, "割安"))

    kodate_cands = []
    for i in range(3):
        ev = MagicMock(
            id=f"kodate_{i}",
            property_type="investmentkodate",
            investment_rating="AA",
            capital_gain_score=70.0 - i,
        )
        prop = MagicMock(propertyName=f"収益戸建{i}")
        kodate_cands.append((80.0 - i, ev, prop, "割安"))

    candidates_by_category = {
        "mansion": [],
        "kodate": [],
        "tochi": [],
        "investment": apt_cands + kodate_cands,
    }

    selected = _select_two_stage_recommendations(candidates_by_category, quota_per_category=5)
    assert len(selected) == 5
    ptypes = [item[1].property_type for item in selected]
    assert "investmentapartment" in ptypes
    assert "investmentkodate" in ptypes


def test_batch_metrics_recommendation_summary_aggregates_investment_channels():
    """
    build_recommendation_slack_summary において、investmentapartment / apartment / investment 等のキーが重複行にならず、
    投資アパート・投資戸建として正確に集計・出力されることを検証。
    """
    m = BatchMetrics("Slack Recommendation", total_count=100)
    m.record_processed(5)
    m.finish()

    summary = m.build_recommendation_slack_summary(
        channel_counts={
            "mansion": 2,
            "investmentapartment": 1,
            "apartment": 1,
            "investmentkodate": 1,
        },
        matched_count=20,
        quota=5,
    )
    assert "マンション: 2 件" in summary
    assert "投資アパート: 2 件" in summary
    assert "投資戸建: 1 件" in summary
