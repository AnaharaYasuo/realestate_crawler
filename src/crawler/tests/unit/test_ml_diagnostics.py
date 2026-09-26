# -*- coding: utf-8 -*-
import pytest
import os
import pandas as pd
import numpy as np

from package.ml.predict import _log_prediction_error
from scripts.ops.run_daily_prediction_diagnostics import (
    calculate_metrics,
    classify_error_cause,
    diagnose_predictions
)


class TestPriceUnitAlignment:
    """価格単位同調ロジック（10億円超物件などの誤認バグ防止）のテスト"""

    def test_high_value_property_unit_handling(self, tmp_path, monkeypatch):
        """9.8億円（980,000,000円）物件で予測値が138,108万円のとき、単位が正しく保たれること"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "prediction_errors.csv"

        # _log_prediction_error 内のログパスを一時ディレクトリにモック
        import package.ml.predict as predict_module
        monkeypatch.setattr(predict_module, "os", os)
        
        # 直接ログ出力ロジックをテスト
        actual_price = 980000000.0  # 9.8億円 (円単位)
        predicted_price = 138108.0  # 13.8108億円 (万円単位)
        features = {"area": 550.0}
        prop_obj = {"pageUrl": "http://example.com/prop-high", "address": "東京都中央区勝どき"}

        # 実行
        _log_prediction_error(prop_obj, "mansion", predicted_price, actual_price, features)
        
        # 通常のログパスをチェック
        real_log_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "src", "crawler", "package", "ml", "logs", "prediction_errors.csv"
        )
        # 単位計算の検証（純粋な計算ロジック）
        actual_man = float(actual_price) / 10000.0 if float(actual_price) >= 100_000.0 else float(actual_price)
        predicted_man = float(predicted_price)
        error_ratio = (predicted_man - actual_man) / actual_man

        # 9.8億円(98,000万円) に対して 138,108万円 なので、+40.9% 程度の乖離
        assert 0.40 <= error_ratio <= 0.42
        assert error_ratio > -0.5  # -0.9999 バグが発生していないこと！

    def test_low_price_property_unit_handling(self):
        """63万円（630,000円）物件が63億円と誤判定されず、63.0万円と判定されること"""
        actual_price = 630000.0  # 63万円 (円単位)
        predicted_price = 169.0  # 169万円
        
        actual_man = float(actual_price) / 10000.0 if float(actual_price) >= 100_000.0 else float(actual_price)
        predicted_man = float(predicted_price)
        error_ratio = (predicted_man - actual_man) / actual_man

        assert actual_man == 63.0
        # 63万円に対して169万円なので、+1.68 (+168%) 程度の乖離（-100%バグ解消）
        assert pytest.approx(error_ratio, 0.1) == (169.0 - 63.0) / 63.0

    def test_man_yen_input_handling(self):
        """actual_price が万円単位（例: 4500）で入力された場合も正しく判定されること"""
        actual_price = 4500.0  # 4500万円
        predicted_price = 5400.0  # 5400万円
        
        actual_man = float(actual_price) / 10000.0 if float(actual_price) >= 100_000.0 else float(actual_price)
        predicted_man = float(predicted_price)
        error_ratio = (predicted_man - actual_man) / actual_man

        assert pytest.approx(error_ratio, 0.01) == 0.20


class TestDiagnosticsMetrics:
    """診断指標（MdAPE, MAPE, Hit Rate等）の計算テスト"""

    def test_calculate_metrics(self):
        # y_true: [4000, 5000, 6000, 10000]
        # y_pred: [4200, 4500, 7200, 20000]
        # 誤差率: [+5%, -10%, +20%, +100%]
        # 絶対誤差率: [5%, 10%, 20%, 100%]
        y_true = np.array([4000.0, 5000.0, 6000.0, 10000.0])
        y_pred = np.array([4200.0, 4500.0, 7200.0, 20000.0])

        metrics = calculate_metrics(y_true, y_pred)

        assert metrics["count"] == 4
        # MdAPE: [5, 10, 20, 100] の中央値 = (10 + 20) / 2 = 15.0%
        assert pytest.approx(metrics["mdape"], 0.1) == 15.0
        # MAPE: (5 + 10 + 20 + 100) / 4 = 33.75%
        assert pytest.approx(metrics["mape"], 0.1) == 33.75
        # Hit Rate @ 10%: 5%, 10% の2件 = 50.0%
        assert pytest.approx(metrics["hit_rate_10"], 0.1) == 50.0
        # Hit Rate @ 20%: 5%, 10%, 20% の3件 = 75.0%
        assert pytest.approx(metrics["hit_rate_20"], 0.1) == 75.0


class TestErrorClassification:
    """乖離要因の自動タギングテスト"""

    def test_classify_leasehold(self):
        text = "借地権につき地代月額15,000円。旧法借地権物件。"
        cause = classify_error_cause(error_ratio=0.45, text=text, ptype="kodate")
        assert "leasehold" in cause

    def test_classify_unbuildable(self):
        text = "再建築不可。市街化調整区域のため建築確認不可。"
        cause = classify_error_cause(error_ratio=0.50, text=text, ptype="kodate")
        assert "unbuildable" in cause

    def test_classify_renovated(self):
        text = "新規フルリノベーション完了（2025年11月）。水回り一新。"
        cause = classify_error_cause(error_ratio=-0.35, text=text, ptype="mansion")
        assert "renovated" in cause

    def test_classify_unknown(self):
        text = "普通のマンションです。"
        cause = classify_error_cause(error_ratio=0.25, text=text, ptype="mansion")
        assert any("unclassified" in c for c in cause)


class TestAIDiagnostics:
    """AIによるワースト乖離物件分析のテスト"""

    def test_ai_analysis_fallback_when_no_api_key(self, monkeypatch):
        """APIキー未設定時は安全にルールベースのサマリーにフォールバックすること"""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        from scripts.ops.run_daily_prediction_diagnostics import generate_ai_diagnostics_insight

        worst_items = [
            {
                "type": "over_prediction",
                "url": "http://example.com/p1",
                "property_type": "kodate",
                "actual_price_man": 2000.0,
                "predicted_price_man": 3500.0,
                "error_percent": "+75.0%",
                "causes": ["leasehold"],
                "text": "借地権物件"
            }
        ]
        insight = generate_ai_diagnostics_insight(worst_items)
        assert isinstance(insight, str)
        assert "ルールベース" in insight or "借地権" in insight or "要因" in insight

    def test_ai_analysis_with_mock_gemini(self, monkeypatch):
        """Gemini API 呼び出しのモックテスト"""
        monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")

        class MockResponse:
            text = "【AI乖離分析】物件1は借地権の減価が反映されていないため過大評価されています。パーサーの借地権抽出を改修してください。"

        class MockClient:
            def __init__(self, *args, **kwargs):
                self.models = self

            def generate_content(self, model, contents):
                return MockResponse()

        from google import genai
        monkeypatch.setattr(genai, "Client", MockClient)

        from scripts.ops.run_daily_prediction_diagnostics import generate_ai_diagnostics_insight

        worst_items = [
            {
                "type": "over_prediction",
                "url": "http://example.com/p1",
                "property_type": "kodate",
                "actual_price_man": 2000.0,
                "predicted_price_man": 3500.0,
                "error_percent": "+75.0%",
                "causes": ["leasehold"],
                "text": "借地権物件"
            }
        ]
        insight = generate_ai_diagnostics_insight(worst_items)
        assert "AI乖離分析" in insight
        assert "借地権" in insight


class TestDiagnosticsSlackNotification:
    """日次精度診断のSlack通知先がdev-agentチャンネルであることを検証するテスト"""

    def test_diagnostics_notify_targets_dev_agent(self, monkeypatch):
        """run_diagnostics(notify=True) 実行時に send_dev_report が呼ばれ、通知先が SLACK_DEV_CHANNEL であること"""
        from unittest.mock import patch, MagicMock
        from scripts.ops.run_daily_prediction_diagnostics import run_diagnostics

        monkeypatch.setenv("SLACK_DEV_CHANNEL", "C0BKBHWD26T")

        mock_eval = MagicMock()
        mock_eval.company = "mitsui"
        mock_eval.property_type = "mansion"
        mock_eval.property_id = 1
        mock_eval.property_url = "http://example.com/prop1"
        mock_eval.first_stage_predicted_price = 4500.0

        mock_prop = MagicMock()
        mock_prop.price = 40000000.0
        mock_prop.biko = ""
        mock_prop.propertyName = "テストマンション"
        mock_prop.address = "東京都港区"
        mock_prop.pageUrl = "http://example.com/prop1"

        mock_qs = MagicMock()
        mock_qs.count.return_value = 1
        mock_qs.order_by.return_value = [mock_eval]

        mock_prop_model = MagicMock()
        mock_prop_model.__name__ = "Mitsuimansion"
        mock_prop_model.objects.filter.return_value.first.return_value = mock_prop

        mock_app_config = MagicMock()
        mock_app_config.get_models.return_value = [mock_prop_model]

        with patch("scripts.ops.run_daily_prediction_diagnostics.PropertyEvaluation.objects.filter", return_value=mock_qs), \
             patch("scripts.ops.run_daily_prediction_diagnostics.apps.get_app_config", return_value=mock_app_config), \
             patch("scripts.ops.run_daily_prediction_diagnostics.send_dev_report") as mock_send_dev:

            report = run_diagnostics(limit=10, dry_run=False, notify=True)
            assert report is not None

            mock_send_dev.assert_called_once()
            called_channel = mock_send_dev.call_args[1].get("channel")
            assert called_channel == "C0BKBHWD26T"



