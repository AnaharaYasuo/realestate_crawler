# -*- coding: utf-8 -*-
"""
1物件1リクエスト完結型 AI属性抽出器 (SingleUnifiedPropertyExtractor) 単体テスト
"""
import pytest
import json
from unittest.mock import MagicMock, patch

from package.ml.unified_property_extractor import SingleUnifiedPropertyExtractor, UnifiedPropertyAttributes


class MockGeminiModel:
    def __init__(self, response_text):
        self.response_text = response_text
        self.call_count = 0

    def generate_content(self, prompt):
        self.call_count += 1
        mock_resp = MagicMock()
        mock_resp.text = self.response_text
        return mock_resp


@pytest.fixture
def sample_mansion_input():
    return {
        "title": "パークコート浜離宮 ザ タワー 29階",
        "site": "mitsui",
        "property_type": "mansion",
        "price_str": "64,800万円",
        "specs": {
            "所在地": "東京都港区浜松町１丁目",
            "交通": "ＪＲ山手線「浜松町」駅 徒歩5分",
            "専有面積": "87.56㎡",
            "間取り": "2LDK",
            "所在階": "29階 / 地上37階",
            "築年月": "2019年1月",
            "総戸数": "100戸",
            "管理形態": "全部委託",
            "管理費": "42,000円/月",
            "修繕積立金": "25,000円/月",
            "土地権利": "所有権"
        },
        "features": ["ディスポーザー", "食洗機", "床暖房", "内廊下", "免震構造", "24時間ゴミ出し可"],
        "appeals": ["三井不動産レジデンシャル旧分譲、清水建設施工。高層階角住戸につき眺望日照良好。"],
        "snippets": ["浴室乾燥機内蔵", "エレベーター複数基", "日勤管理"]
    }


@pytest.fixture
def mock_mansion_json_response():
    return json.dumps({
        "property_overview": {
            "price_man_yen": 64800,
            "property_type": "mansion",
            "transaction_type": "仲介",
            "occupancy_status": "居住中"
        },
        "building_master": {
            "developer_brand": "三井不動産レジデンシャル（パークコート）",
            "developer_tier": "major_reputable",
            "contractor_name": "清水建設",
            "contractor_tier": "super_general",
            "structure_type": "RC",
            "earthquake_resistance": "免震",
            "total_units": 100,
            "elevator_available": True,
            "hallway_type": "内廊下",
            "garbage_disposal_24h": True,
            "management_type": "全部委託",
            "manager_working_style": "日勤",
            "shared_facilities": ["宅配ボックス", "ラウンジ"]
        },
        "unit_specs": {
            "floor_number": 29,
            "total_floors": 37,
            "is_top_floor": False,
            "is_basement": False,
            "is_corner_unit": True,
            "main_orientation": "南西",
            "has_disposer": True,
            "has_dishwasher": True,
            "has_floor_heating": True,
            "has_bath_dryer": True,
            "has_water_purifier": True,
            "renovation_status": "未実施",
            "renovation_year_month": None,
            "renovation_details": [],
            "piping_replaced": False,
            "special_notes_psychological_defect": False
        },
        "land_kodate_specs": {},
        "rights_economic_conditions": {
            "land_rights_type": "所有権",
            "ground_rent_monthly_yen": None,
            "lease_expiry_year_month": None,
            "management_fee_monthly_yen": 42000,
            "repair_reserve_fund_monthly_yen": 25000,
            "other_monthly_expenses_yen": 0
        }
    })


def test_single_call_guarantee(sample_mansion_input, mock_mansion_json_response, monkeypatch):
    """最重要要件: 1物件につきAI呼び出しが厳格に最大1回であること"""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
    extractor = SingleUnifiedPropertyExtractor()

    mock_model = MockGeminiModel(mock_mansion_json_response)
    with patch.object(extractor, "_get_generative_model", return_value=mock_model):
        res = extractor.extract(sample_mansion_input)

        # 呼び出し回数が厳格に1回であること
        assert mock_model.call_count == 1
        assert isinstance(res, UnifiedPropertyAttributes)
        assert res.building_master.developer_brand == "三井不動産レジデンシャル（パークコート）"
        assert res.building_master.elevator_available is True
        assert res.building_master.hallway_type == "内廊下"
        assert res.unit_specs.has_disposer is True
        assert res.unit_specs.is_corner_unit is True
        assert res.unit_specs.floor_number == 29


def test_fallback_on_llm_failure(sample_mansion_input, monkeypatch):
    """LLMが異常終了または壊れたJSONを返してもフォールバックすること"""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
    extractor = SingleUnifiedPropertyExtractor()

    mock_model = MockGeminiModel("This is not valid JSON string!")
    with patch.object(extractor, "_get_generative_model", return_value=mock_model):
        res = extractor.extract(sample_mansion_input)
        assert mock_model.call_count == 1
        assert isinstance(res, UnifiedPropertyAttributes)
        # フォールバックしてもクラッシュせず基本構造を返す
        assert res.property_overview.price_man_yen == 64800 or res.property_overview.property_type == "mansion"


def test_missing_api_key_safe_fallback(sample_mansion_input, monkeypatch):
    """APIキーが存在しない場合はLLMを呼ばずルールベースで安全に返す"""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    extractor = SingleUnifiedPropertyExtractor()
    res = extractor.extract(sample_mansion_input)
    assert isinstance(res, UnifiedPropertyAttributes)
    # ルールベースから一部基本スペックが取れていること
    assert res.property_overview.price_man_yen == 64800
    assert res.building_master.elevator_available is None or res.building_master.elevator_available is True


def test_multimodal_single_call_with_images(sample_mansion_input, mock_mansion_json_response, monkeypatch):
    """画像が複数枚ある場合でも、画像群を一括同梱して1リクエストで完結すること"""
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
    extractor = SingleUnifiedPropertyExtractor()

    # ダミー画像オブジェクト（バイト列またはモック画像）
    mock_images = [MagicMock(), MagicMock(), MagicMock()] # 間取り、外観、内装
    sample_mansion_input["images"] = mock_images

    mock_model = MockGeminiModel(mock_mansion_json_response)
    with patch.object(extractor, "_get_generative_model", return_value=mock_model):
        res = extractor.extract(sample_mansion_input)

        # 画像が何枚あろうと呼び出し回数は厳格に1回
        assert mock_model.call_count == 1
        assert isinstance(res, UnifiedPropertyAttributes)

