# -*- coding: utf-8 -*-
import os
import pytest
from package.ml.train import train_and_compare, generate_dummy_data
from package.ml.predict import predict_first_stage, predict_second_stage
import joblib

def test_ml_pipeline():
    # 1. テスト用の極小ダミーデータでモデルを簡易学習・保存する
    print("Testing ML model training with tiny dummy data...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    model_dir = os.path.join(project_root, "src", "crawler", "package", "ml", "models")
    os.makedirs(model_dir, exist_ok=True)
    
    # ダミーデータを生成してモデル保存
    feature_sets = {
        "mansion": {
            "first": [
                "area", "chikunen", "walk_min", "kanrihi", "syuzen",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei"
            ],
            "second": [
                "area", "chikunen", "walk_min", "kanrihi", "syuzen",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei", "interior_score", "layout_score"
            ]
        }
    }
    
    # 50件のダミーデータで学習
    df_mansion = generate_dummy_data('mansion', num_records=50)
    
    trained_first = train_and_compare(df_mansion, feature_sets["mansion"]["first"], "mansion - First Stage")
    trained_second = train_and_compare(df_mansion, feature_sets["mansion"]["second"], "mansion - Second Stage")
    
    # モデルの保存
    for algo in ['lgb', 'xgb', 'cat']:
        joblib.dump(trained_first[algo], os.path.join(model_dir, f"mansion_first_stage_{algo}.joblib"))
        joblib.dump(trained_second[algo], os.path.join(model_dir, f"mansion_second_stage_{algo}.joblib"))
        
    # 他の物件種別（kodate, apartment）もダミー学習させておく（predictで利用するため）
    for ptype in ['kodate', 'apartment']:
        df_ptype = generate_dummy_data(ptype, num_records=50)
        if ptype == 'apartment':
            feats_first = [
                "area", "tochi_menseki", "chikunen", "walk_min",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
                "gross_yield", "annual_rent",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei",
                "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
                "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value"
            ]
        else:
            feats_first = [
                "area", "tochi_menseki", "chikunen", "walk_min",
                "pop_growth", "income", "passenger_volume", "average_land_price",
                "estimated_rosenka_price", "estimated_fixed_asset_price",
                "digest_volume_ratio", "surplus_volume_potential", "non_conforming_flag",
                "cost_approach_value", "mkt_comparison_value", "income_approach_value",
                "is_shin_taishin", "flood_risk_level", "landslide_risk_level",
                "max_youseki", "max_kenpei",
                "maguchi", "road_width", "setback_ratio", "actual_volume_limit",
                "volume_digest_factor", "road_condition_factor", "frontage_penalty_factor", "residual_land_value"
            ]
            
        feats_second = feats_first + ["interior_score", "layout_score"]
        
        trained_f = train_and_compare(df_ptype, feats_first, f"{ptype} - First Stage")
        trained_s = train_and_compare(df_ptype, feats_second, f"{ptype} - Second Stage")
        
        for algo in ['lgb', 'xgb', 'cat']:
            joblib.dump(trained_f[algo], os.path.join(model_dir, f"{ptype}_first_stage_{algo}.joblib"))
            joblib.dump(trained_s[algo], os.path.join(model_dir, f"{ptype}_second_stage_{algo}.joblib"))

    # マーケット比較マスタも保存
    mkt_master = {"mansion": {}, "kodate": {}, "apartment": {}}
    joblib.dump(mkt_master, os.path.join(model_dir, "mkt_comparison_master.joblib"))

    # モデルファイルの存在チェック
    assert os.path.exists(os.path.join(model_dir, "mansion_first_stage_lgb.joblib")) is True
    assert os.path.exists(os.path.join(model_dir, "mansion_second_stage_lgb.joblib")) is True

    # 2. ダミーの物件データを用いた推論の実行テスト
    dummy_property = {
        "propertyName": "テストマンション",
        "pageUrl": "http://example.com/test-prop-ml-1",
        "price": 4500,
        "address1": "東京都",
        "address2": "千代田区",
        "station1": "飯田橋駅",
        "senyuMenseki": 75.5,
        "chikunengetsu": "2015-04-01",
        "railwayWalkMinute1": 6,
        "kanrihi": 15000,
        "syuzenTsumitate": 12000
    }

    # 一次理論価格（画像なし）の予測実行
    print("Testing Stage 1 prediction...")
    price_stage1 = predict_first_stage(dummy_property)
    assert isinstance(price_stage1, int)
    assert price_stage1 > 0
    print(f"Predicted Stage 1 Price: {price_stage1}万円")

    # 二次理論価格（画像スコアあり）の予測実行
    print("Testing Stage 2 prediction...")
    price_stage2 = predict_second_stage(dummy_property, interior_score=4.5, layout_score=3.8)
    assert isinstance(price_stage2, int)
    assert price_stage2 > 0
    print(f"Predicted Stage 2 Price: {price_stage2}万円")


@pytest.mark.django_db
def test_investment_evaluator():
    from django.utils import timezone
    from package.ml.investment_evaluator import evaluate_investment_property
    from package.models.evaluation import PropertyEvaluation
    
    eval_rec = PropertyEvaluation(
        company="mitsui",
        property_type="invest_apartment",
        property_id=1,
        property_url="http://example.com/test-eval-1",
        first_stage_predicted_price=5000,
        second_stage_predicted_price=6000
    )
    
    class DummyProperty:
        def __init__(self):
            self.price = 50000000  # 5000万円
            self.address = "東京都千代田区飯田橋1-1-1"
            self.annualRent = 4000000  # 400万円
            self.tochiMenseki = 150.0
            self.tatemonoMenseki = 250.0
            self.kouzou = "RC造"
            self.chikunengetsu = timezone.now().date()
            self.pageUrl = "http://example.com/test-eval-1"
            
    prop = DummyProperty()
    
    res_eval = evaluate_investment_property(prop, eval_rec)
    
    assert res_eval.estimated_sekisan_price > 0
    assert res_eval.net_operating_income == 320  # 400 * 0.8
    assert res_eval.debt_service > 0
    assert res_eval.dscr > 0
    assert res_eval.total_investment_score > 0
    print("Investment Evaluator Test Passed!")


@pytest.mark.django_db
def test_address_normalization():
    from package.ml.features import build_features
    # 1. address2 has extra town info
    prop1 = {
        "propertyName": "テスト物件1",
        "pageUrl": "http://example.com/test-addr-1",
        "address1": "東京都",
        "address2": "港区赤坂9丁目",
    }
    # 2. Kyoto address with street name in address2
    prop2 = {
        "propertyName": "テスト物件2",
        "pageUrl": "http://example.com/test-addr-2",
        "address1": "京都府",
        "address2": "京都市中京区烏丸通下る",
    }
    # 3. Kyoto address with street name in full address
    prop3 = {
        "propertyName": "テスト物件3",
        "pageUrl": "http://example.com/test-addr-3",
        "address": "京都府京都市中京区烏丸通下る",
    }

    features1 = build_features(prop1, 'mansion')
    features2 = build_features(prop2, 'mansion')
    features3 = build_features(prop3, 'mansion')

    assert features1 is not None
    assert features2 is not None
    assert features3 is not None

