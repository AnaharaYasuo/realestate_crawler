# -*- coding: utf-8 -*-
"""Issue #1782: 全Gemini呼び出しの gemini-flash-lite-latest プライマリ＋段階的フォールバック統一テスト"""
from unittest.mock import MagicMock, patch

import pytest

from package.ml import report_generator as rg
from package.ml.unified_property_extractor import SingleUnifiedPropertyExtractor
from package.utils import gemini_rate_limiter as grl


def test_default_gemini_model_chain_and_deprecated_filtering():
    assert grl.DEFAULT_GEMINI_PRIMARY_MODEL == "gemini-flash-lite-latest"
    assert grl.DEFAULT_GEMINI_FALLBACK_MODELS == (
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-3.8-flash",
    )
    # 廃止モデルが渡されても自動除外され、gemini-flash-lite-latest から開始する
    chain = grl.resolve_gemini_model_chain("gemini-2.5-flash")
    assert chain[0] == "gemini-flash-lite-latest"
    assert "gemini-2.5-flash" not in chain
    assert "gemini-2.5-flash-lite" not in chain
    assert chain == [
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-3.8-flash",
    ]


def test_generate_content_with_fallback_steps_down_on_error():
    """プライマリ失敗時に段階的フォールバックチェーンに沿って次モデルへ切り替わること"""
    called_models: list[str] = []

    class FakeModels:
        def generate_content(self, *, model, contents, **kwargs):
            called_models.append(model)
            if model == "gemini-flash-lite-latest":
                raise RuntimeError("503 UNAVAILABLE")
            if model == "gemini-3.5-flash-lite":
                raise RuntimeError("503 UNAVAILABLE")
            resp = MagicMock()
            resp.text = '{"ok": true}'
            return resp

    fake_client = MagicMock()
    fake_client.models = FakeModels()
    resp, used_model = grl.generate_content_with_fallback(
        fake_client,
        "hello",
        primary_model="gemini-flash-lite-latest",
    )
    assert resp.text == '{"ok": true}'
    assert used_model == "gemini-3.1-flash-lite"
    assert called_models == [
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]


def test_generate_content_with_fallback_raises_last_error_when_all_fail():
    class AlwaysFailModels:
        def generate_content(self, *, model, contents, **kwargs):
            raise RuntimeError(f"failed on {model}")

    fake_client = MagicMock()
    fake_client.models = AlwaysFailModels()
    with pytest.raises(RuntimeError, match="failed on gemini-3.8-flash"):
        grl.generate_content_with_fallback(fake_client, "hello")


def test_report_generator_uses_unified_primary_and_fallback_and_filters_deprecated():
    assert rg.DEFAULT_RECOMMEND_MODEL == "gemini-flash-lite-latest"
    assert rg.FALLBACK_MODELS == grl.DEFAULT_GEMINI_FALLBACK_MODELS
    called: list[str] = []

    def fake_call(model_name, api_key, prompt):
        called.append(model_name)
        if model_name == "gemini-3.5-flash-lite":
            return {"investment_rating": "AA"}
        return None

    with patch.object(rg, "_call_gemini_api", side_effect=fake_call):
        res = rg._execute_gemini_report_call("prompt", "key", "gemini-2.5-flash")
    assert res == {"investment_rating": "AA"}
    assert called == ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"]


def test_unified_property_extractor_defaults_to_flash_lite_latest_and_falls_back():
    ext = SingleUnifiedPropertyExtractor()
    assert ext.model_name == "gemini-flash-lite-latest"
    called: list[str] = []

    class FakeModels:
        def generate_content(self, *, model, contents, **kwargs):
            called.append(model)
            if model == "gemini-flash-lite-latest":
                raise RuntimeError("503 UNAVAILABLE")
            resp = MagicMock()
            resp.text = '{"property_overview": {"property_type": "mansion"}}'
            resp.usage_metadata = None
            return resp

    fake_client = MagicMock()
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = False
    fake_client.models = FakeModels()

    with (
        patch.object(ext, "_get_genai_client", return_value=fake_client),
        patch("package.ml.unified_property_extractor.record_llm_event"),
    ):
        res = ext.extract({"title": "テストマンション", "property_type": "mansion"})
    assert res.property_overview.property_type == "mansion"
    assert called == ["gemini-flash-lite-latest", "gemini-3.5-flash-lite"]
