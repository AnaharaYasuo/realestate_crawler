"""
Issue #1370: 市街化調整区域の土地評価例外規定（倍率方式・3段階しんしゃく割合・雑種地農地比準）およびお宝通知DCF自動補完の単体テスト
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from package.ml.dcf_valuation import evaluate_dcf_and_yields
from package.ml.evaluation.targets import _should_skip_item
from package.ml.features.builder import build_features
from package.ml.features.legal_furuya import (
    compute_shigaika_land_unit_price,
    extract_combined_text_for_prop,
    resolve_chimoku_valuation_multiplier,
    resolve_shigaika_shinshaku_rate,
)
from package.ml.investment_evaluator import calculate_sekisan_price
from package.ml.report_generator import _format_dcf_context_line
from scripts.ops.send_recommendations import _build_recommendation_msg, _format_dcf_slack_lines


class TestShigaikaChouseiAndChimokuValuation:
    """市街化調整区域の倍率方式・3段階しんしゃく割合・雑種地/農地比準の検証"""

    def test_extract_combined_text_includes_urban_planning_and_chimoku(self):
        prop = {
            "urbanPlanning": "市街化調整区域",
            "chimoku": "雑種地",
            "biko": "ロードサイド店舗用地",
        }
        text = extract_combined_text_for_prop(prop)
        assert "市街化調整区域" in text
        assert "雑種地" in text
        assert "ロードサイド店舗用地" in text

    def test_resolve_shigaika_shinshaku_rate_three_tiers(self):
        # 1. 原則利用制限・建築制限ありの市街化調整区域 -> しんしゃく割合 50% (0.50)
        prop_restricted = {
            "kuiki": "市街化調整区域",
            "biko": "原則建築不可・資材置場適す",
            "roadWidth": 4.0,
        }
        is_shigaika, rate = resolve_shigaika_shinshaku_rate(
            prop_restricted, extract_combined_text_for_prop(prop_restricted), road_width_val=4.0
        )
        assert is_shigaika == 1.0
        assert rate == pytest.approx(0.50)

        # 2. 店舗・事務所建築可能な幹線道路沿い -> しんしゃく割合 30% (0.30)
        prop_arterial = {
            "urbanPlanning": "市街化調整区域",
            "biko": "国道4号バイパス沿い・沿道サービス店舗・事務所建築可",
            "roadWidth": 12.0,
        }
        is_shigaika_30, rate_30 = resolve_shigaika_shinshaku_rate(
            prop_arterial, extract_combined_text_for_prop(prop_arterial), road_width_val=12.0
        )
        assert is_shigaika_30 == 1.0
        assert rate_30 == pytest.approx(0.30)

        # 3. 既存宅地・開発許可済・34条11号/12号など宅地と同等の取引実態 -> しんしゃく割合 0% (0.00)
        prop_existing_takuchi = {
            "kuiki": "市街化調整区域",
            "biko": "都市計画法34条11号区域・既存宅地につきどなたでも住宅建築可（開発許可済）",
            "roadWidth": 6.0,
        }
        is_shigaika_0, rate_0 = resolve_shigaika_shinshaku_rate(
            prop_existing_takuchi, extract_combined_text_for_prop(prop_existing_takuchi), road_width_val=6.0
        )
        assert is_shigaika_0 == 1.0
        assert rate_0 == pytest.approx(0.00)

        # 4. 市街化区域 -> is_shigaika=0.0, rate=0.0
        prop_normal = {"kuiki": "市街化区域", "biko": "閑静な住宅街"}
        is_shigaika_norm, rate_norm = resolve_shigaika_shinshaku_rate(
            prop_normal, extract_combined_text_for_prop(prop_normal), road_width_val=6.0
        )
        assert is_shigaika_norm == 0.0
        assert rate_norm == pytest.approx(0.00)

    def test_compute_shigaika_land_unit_price_adopts_min_of_two_methods(self):
        # 1. 宅地（しんしゃく割合 0%）：
        #    方式① 固定資産税評価額(70,000) × 宅地倍率(1.1) = 77,000
        #    方式② 近傍標準宅地単価(100,000) × 宅地倍率(1.1) × 画地調整率(1.0) × (1 - 0.0) = 110,000
        #    -> 低い方の 77,000円/㎡ が採用されること
        unit_0 = compute_shigaika_land_unit_price(
            nearby_standard_price=100_000.0,
            estimated_fixed_asset_price=70_000.0,
            plot_adjustment_factor=1.0,
            shinshaku_rate=0.0,
            takuchi_bairitsu=1.10,
        )
        assert unit_0 == pytest.approx(77_000.0)

        # 2. 宅地（しんしゃく割合 50%）：
        #    方式① 固定資産税評価額(70,000) × 宅地倍率(1.1) = 77,000
        #    方式② 近傍標準宅地単価(100,000) × 宅地倍率(1.1) × 画地調整率(1.0) × (1 - 0.50) = 55,000
        #    -> 低い方の 55,000円/㎡ が採用されること
        unit_50 = compute_shigaika_land_unit_price(
            nearby_standard_price=100_000.0,
            estimated_fixed_asset_price=70_000.0,
            plot_adjustment_factor=1.0,
            shinshaku_rate=0.50,
            takuchi_bairitsu=1.10,
        )
        assert unit_50 == pytest.approx(55_000.0)

        # 3. 宅地（しんしゃく割合 30%）：
        #    方式① = 77,000
        #    方式② = 100,000 × 1.1 × 0.90 × (1 - 0.30) = 69,300
        #    -> 低い方の 69,300円/㎡ が採用されること
        unit_30 = compute_shigaika_land_unit_price(
            nearby_standard_price=100_000.0,
            estimated_fixed_asset_price=70_000.0,
            plot_adjustment_factor=0.90,
            shinshaku_rate=0.30,
            takuchi_bairitsu=1.10,
        )
        assert unit_30 == pytest.approx(69_300.0)

    def test_resolve_chimoku_valuation_multiplier_for_zasshuchi_and_farmland(self):
        # 宅地は 1.0
        assert resolve_chimoku_valuation_multiplier("宅地", is_shigaika_chousei=0.0, shinshaku_rate=0.0) == pytest.approx(1.0)

        # 雑種地（資材置き場・駐車場）：市街化区域よりも市街化調整区域でしんしゃく減価が効くこと
        zasshu_urban = resolve_chimoku_valuation_multiplier(
            "雑種地", is_shigaika_chousei=0.0, shinshaku_rate=0.0, combined_text="駐車場用地"
        )
        zasshu_chousei = resolve_chimoku_valuation_multiplier(
            "雑種地", is_shigaika_chousei=1.0, shinshaku_rate=0.50, combined_text="市街化調整区域・資材置場"
        )
        assert 0.80 <= zasshu_urban < 1.0
        assert zasshu_chousei < zasshu_urban

        # 農地（田・畑）：純農地（調整区域の農地）は市街化区域内の宅地介在農地より大幅に低く評価されること
        hatake_urban = resolve_chimoku_valuation_multiplier(
            "畑", is_shigaika_chousei=0.0, shinshaku_rate=0.0
        )
        ta_urban = resolve_chimoku_valuation_multiplier(
            "田", is_shigaika_chousei=0.0, shinshaku_rate=0.0
        )
        pure_farmland_chousei = resolve_chimoku_valuation_multiplier(
            "田", is_shigaika_chousei=1.0, shinshaku_rate=0.50, combined_text="市街化調整区域 純農地"
        )
        assert pure_farmland_chousei < ta_urban < hatake_urban < 1.0

    def test_end_to_end_valuations_reflect_shinshaku_and_chimoku(self):
        base_prop = {
            "address": "宮城県仙台市青葉区下愛子字町",
            "address1": "宮城県",
            "address2": "仙台市青葉区",
            "station1": "愛子",
            "toho1": 4,
            "tochiMenseki": 272.88,
            "kenpei": 60,
            "youseki": 200,
            "roadWidth": 4.0,
            "maguchi": 12.0,
            "chimoku": "宅地",
            "kuiki": "市街化区域",
        }
        prop_shigaika_50 = {
            **base_prop,
            "kuiki": "市街化調整区域",
            "biko": "市街化調整区域・原則建築制限あり",
        }
        prop_shigaika_30 = {
            **base_prop,
            "kuiki": "市街化調整区域",
            "roadWidth": 10.0,
            "biko": "市街化調整区域・幹線道路沿い店舗・事務所建築可",
        }
        prop_shigaika_0 = {
            **base_prop,
            "kuiki": "市街化調整区域",
            "biko": "市街化調整区域・都市計画法34条11号・既存宅地につき一般住宅建築可",
        }
        prop_farmland = {
            **base_prop,
            "kuiki": "市街化調整区域",
            "chimoku": "田",
            "biko": "市街化調整区域・純農地",
        }

        f_normal = build_features(base_prop, "tochi")
        f_50 = build_features(prop_shigaika_50, "tochi")
        f_30 = build_features(prop_shigaika_30, "tochi")
        f_0 = build_features(prop_shigaika_0, "tochi")
        f_farm = build_features(prop_farmland, "tochi")

        # 原価法・残余法・正味土地アンカーすべてで: 純農地 < 調整区域(50%減) < 調整区域(30%減) < 調整区域(0%減・倍率方式min) < 市街化区域
        assert f_farm["cost_approach_value"] < f_50["cost_approach_value"] < f_30["cost_approach_value"] < f_0["cost_approach_value"] < f_normal["cost_approach_value"]
        assert f_farm["net_land_component_man"] < f_50["net_land_component_man"] < f_30["net_land_component_man"] < f_0["net_land_component_man"] < f_normal["net_land_component_man"]
        assert f_farm["anchor_log_unit_price"] < f_50["anchor_log_unit_price"] < f_30["anchor_log_unit_price"] < f_0["anchor_log_unit_price"] < f_normal["anchor_log_unit_price"]

        # 積算価格 (calculate_sekisan_price) でも同じ順序関係が成り立つこと
        sek_normal = calculate_sekisan_price(SimpleNamespace(**base_prop), "宮城県", "仙台市青葉区")
        sek_0 = calculate_sekisan_price(SimpleNamespace(**prop_shigaika_0), "宮城県", "仙台市青葉区")
        sek_30 = calculate_sekisan_price(SimpleNamespace(**prop_shigaika_30), "宮城県", "仙台市青葉区")
        sek_50 = calculate_sekisan_price(SimpleNamespace(**prop_shigaika_50), "宮城県", "仙台市青葉区")
        sek_farm = calculate_sekisan_price(SimpleNamespace(**prop_farmland), "宮城県", "仙台市青葉区")
        assert sek_farm < sek_50 < sek_30 < sek_0 < sek_normal

        # 10年DCF理論価格でも同じ順序関係が成り立つこと
        dcf_normal = evaluate_dcf_and_yields(base_prop, "tochi").dcf_theoretical_price
        dcf_50 = evaluate_dcf_and_yields(prop_shigaika_50, "tochi").dcf_theoretical_price
        dcf_farm = evaluate_dcf_and_yields(prop_farmland, "tochi").dcf_theoretical_price
        assert 0 < dcf_farm <= dcf_50 < dcf_normal


class TestMissingDcfPriceBackfillAndNotification:
    """青葉区下愛子字町土地などでDCF理論価格が欠落していた問題の再発防止テスト"""

    def test_should_skip_item_returns_false_when_dcf_theoretical_price_is_none(self):
        # 一次予測価格は算出済みだが dcf_theoretical_price が None の旧評価レコードはスキップせず再評価対象にする
        legacy_eval = SimpleNamespace(
            is_published=True,
            needs_recrawl=False,
            first_stage_predicted_price=5560,
            dcf_theoretical_price=None,
            estimated_sekisan_price=6193,
            analyzed_at=None,
        )
        assert _should_skip_item(legacy_eval, force=False) is False

        # dcf_theoretical_price が正の整数で入っている場合はスキップする
        complete_eval = SimpleNamespace(
            is_published=True,
            needs_recrawl=False,
            first_stage_predicted_price=5560,
            dcf_theoretical_price=4120,
            estimated_sekisan_price=6193,
            analyzed_at=None,
        )
        assert _should_skip_item(complete_eval, force=False) is True

    def test_build_recommendation_msg_backfills_missing_dcf_price_for_shimoayashi_tochi(self):
        # ユーザー報告の「青葉区下愛子字町土地」ケースを再現:
        # eval_rec.dcf_theoretical_price が None の状態でお宝通知が呼ばれた場合でも、
        # オンデマンドで DCF理論価格と期待利回りが算出・表示されること
        prop = SimpleNamespace(
            propertyName="青葉区下愛子字町土地",
            pageUrl="https://www.stepon.co.jp/tochi/detail_96611118/",
            price=27800000,
            address="宮城県仙台市青葉区下愛子字町",
            address1="宮城県",
            address2="仙台市青葉区",
            address3="下愛子字町",
            railway1="仙山線",
            station1="愛子",
            toho1=4,
            tochiMenseki=Decimal("272.88"),
            tochiMensekiStr="272.88m2(約82.54坪)※公簿",
            kenpei=60,
            youseki=200,
            roadWidth=Decimal("4.0"),
            maguchi=Decimal("12.0"),
            chimoku="宅地",
        )
        eval_rec = SimpleNamespace(
            property_url="https://www.stepon.co.jp/tochi/detail_96611118/",
            property_type="tochi",
            first_stage_predicted_price=5560,
            second_stage_predicted_price=5560,
            estimated_sekisan_price=6193,
            dcf_theoretical_price=None,
            expected_gross_yield=None,
            expected_net_yield=None,
            estimated_annual_rent=None,
            cash_flow=None,
            dscr=None,
        )
        dummy_report = {
            "investment_rating": "A",
            "area_evaluation": "地域評価テスト",
            "station_evaluation": "駅評価テスト",
            "hazard_evaluation": "ハザード評価テスト",
            "property_evaluation": "物件スペック評価テスト",
            "capital_gain_score": 75.0,
            "ai_fair_price_man": 3200,
            "capital_gain_perspective": "キャピタルゲイン講評",
            "highest_and_best_use": "戸建用地",
            "danchou_comment": "団長コメント",
            "ai_positive_points": "高評価ポイント",
            "ai_negative_points": "留意点",
        }
        msg = _build_recommendation_msg(
            eval_rec=eval_rec,
            prop=prop,
            reason="【市場予測価格より 50.0% 割安（超お宝物件！）】",
            p_name="青葉区下愛子字町土地",
            report_data=dummy_report,
        )
        assert "・10年DCF理論価格:" in msg
        assert "・期待利回り(表面/実質):" in msg
        assert eval_rec.dcf_theoretical_price is not None and eval_rec.dcf_theoretical_price > 0
        assert eval_rec.expected_gross_yield is not None and float(eval_rec.expected_gross_yield) > 0
        assert eval_rec.expected_net_yield is not None and float(eval_rec.expected_net_yield) > 0

    def test_format_dcf_context_line_backfills_when_missing(self):
        prop = SimpleNamespace(
            address="宮城県仙台市青葉区下愛子字町",
            address1="宮城県",
            address2="仙台市青葉区",
            station1="愛子",
            toho1=4,
            tochiMenseki=272.88,
            kenpei=60,
            youseki=200,
        )
        eval_rec = SimpleNamespace(
            property_type="tochi",
            dcf_theoretical_price=None,
            expected_gross_yield=None,
            expected_net_yield=None,
            estimated_annual_rent=None,
        )
        line = _format_dcf_context_line(eval_rec, prop=prop)
        assert "10年DCF理論価格(AI不使用):" in line
        assert eval_rec.dcf_theoretical_price is not None and eval_rec.dcf_theoretical_price > 0
