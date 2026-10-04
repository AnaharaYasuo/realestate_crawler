# -*- coding: utf-8 -*-
from datetime import datetime
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from package.models.evaluation import PropertyEvaluation
from package.utils.data_validator import PropertyDataValidator


class DummyMansion:
    def __init__(self, **kwargs):
        self.pageUrl = kwargs.get("pageUrl", "https://example.com/mansion/1")
        self.propertyName = kwargs.get("propertyName", "テストマンション 101号室")
        self.price = kwargs.get("price", 50000000)
        self.senyuMenseki = kwargs.get("senyuMenseki", 70.5)
        self.shozaikai = kwargs.get("shozaikai", "5階")
        self.kaisu = kwargs.get("kaisu", "5階")
        self.chikunengetsu = kwargs.get("chikunengetsu", datetime(2015, 5, 1))
        self.biko = kwargs.get("biko", "")


class DummyKodate:
    def __init__(self, **kwargs):
        self.pageUrl = kwargs.get("pageUrl", "https://example.com/kodate/1")
        self.propertyName = kwargs.get("propertyName", "テスト一戸建て")
        self.price = kwargs.get("price", 45000000)
        self.tochiMenseki = kwargs.get("tochiMenseki", 120.0)
        self.tatemonoMenseki = kwargs.get("tatemonoMenseki", 95.0)
        self.chikunengetsu = kwargs.get("chikunengetsu", datetime(2018, 3, 1))
        self.biko = kwargs.get("biko", "")


class DummyTochi:
    def __init__(self, **kwargs):
        self.pageUrl = kwargs.get("pageUrl", "https://example.com/tochi/1")
        self.propertyName = kwargs.get("propertyName", "テスト売地")
        self.price = kwargs.get("price", 30000000)
        self.tochiMenseki = kwargs.get("tochiMenseki", 150.0)
        self.biko = kwargs.get("biko", "")


class DummyInvestmentApartment:
    def __init__(self, **kwargs):
        self.pageUrl = kwargs.get("pageUrl", "https://example.com/invest/1")
        self.propertyName = kwargs.get("propertyName", "テスト一棟アパート")
        self.price = kwargs.get("price", 80000000)
        self.tatemonoMenseki = kwargs.get("tatemonoMenseki", 200.0)
        self.annualRent = kwargs.get("annualRent", 6400000)
        self.yieldRate = kwargs.get("yieldRate", 8.0)
        self.biko = kwargs.get("biko", "")


def test_validator_normal_mansion():
    item = DummyMansion()
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is True
    assert len(reasons) == 0


def test_validator_mansion_missing_senyumenseki():
    item = DummyMansion(senyuMenseki=None)
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("専有面積" in r for r in reasons)


def test_validator_mansion_missing_floor():
    item = DummyMansion(shozaikai="", kaisu="")
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("所在階" in r for r in reasons)


def test_validator_price_too_low():
    item = DummyMansion(price=500000)  # 50万円
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("価格異常" in r for r in reasons)


def test_validator_price_too_high():
    item = DummyMansion(price=3000000000)  # 30億円
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("価格異常" in r for r in reasons)


def test_validator_unit_price_abnormal():
    # 専有面積70㎡で価格100万円（平米単価約1.4万円は通るが、平米500円等の異常）
    item = DummyMansion(price=1000000, senyuMenseki=2000.0)  # 500円/㎡
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("単価異常" in r for r in reasons)


def test_validator_future_building_year():
    item = DummyMansion(chikunengetsu=datetime(2099, 1, 1))
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("築年数異常" in r for r in reasons)


def test_validator_ancient_building_year():
    item = DummyMansion(chikunengetsu=datetime(1850, 1, 1))
    is_valid, reasons = PropertyDataValidator.validate_property(item, "mansion")
    assert is_valid is False
    assert any("築年数異常" in r for r in reasons)


def test_validator_kodate_missing_menseki():
    item = DummyKodate(tatemonoMenseki=None)
    is_valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
    assert is_valid is False
    assert any("建物面積" in r for r in reasons)


def test_validator_tochi_missing_menseki():
    item = DummyTochi(tochiMenseki=0)
    is_valid, reasons = PropertyDataValidator.validate_property(item, "tochi")
    assert is_valid is False
    assert any("土地面積" in r for r in reasons)


def test_validator_invest_abnormal_yield():
    item = DummyInvestmentApartment(yieldRate=120.0)  # 利回り120%
    is_valid, reasons = PropertyDataValidator.validate_property(item, "apartment")
    assert is_valid is False
    assert any("利回り" in r for r in reasons)


def test_validator_saikenchiku_fuka_is_not_invalid():
    # 再建築不可は物件仕様でありデータ不正ではない
    item = DummyKodate(biko="再建築不可物件につき現状渡し")
    is_valid, reasons = PropertyDataValidator.validate_property(item, "kodate")
    assert is_valid is True
    assert len(reasons) == 0


@pytest.mark.asyncio
async def test_delisted_property_handling():
    """URL生存確認で404/掲載終了判定された場合、is_published=False, delisted_at がセットされ、needs_recrawl=False となること"""
    from scripts.maintenance.validate_data import process_property_validation

    mock_item = DummyMansion(pageUrl="https://example.com/delisted/1")
    eval_rec = PropertyEvaluation(
        company="mitsui",
        property_type="mansion",
        property_id=1,
        property_url=mock_item.pageUrl,
        is_published=True,
    )

    with patch("scripts.maintenance.validate_data.verify_url_active", new_callable=AsyncMock) as mock_active:
        mock_active.return_value = False  # 掲載終了
        res = await process_property_validation(mock_item, "mansion", "mitsui", eval_rec)
        assert res["status"] == "delisted"
        assert eval_rec.is_published is False
        assert eval_rec.delisted_at is not None
        assert eval_rec.needs_recrawl is False


@pytest.mark.asyncio
async def test_invalid_property_sets_recrawl_flag():
    """データ不正物件が検知された場合、needs_parser_fix=True, needs_recrawl=False, data_quality_issue が記録されること"""
    from scripts.maintenance.validate_data import process_property_validation

    mock_item = DummyMansion(price=0, pageUrl="https://example.com/invalid/1")
    eval_rec = PropertyEvaluation(
        company="mitsui",
        property_type="mansion",
        property_id=2,
        property_url=mock_item.pageUrl,
        is_published=True,
    )

    with patch("scripts.maintenance.validate_data.verify_url_active", new_callable=AsyncMock) as mock_active:
        mock_active.return_value = True  # 公開中
        res = await process_property_validation(mock_item, "mansion", "mitsui", eval_rec)
        assert res["status"] == "invalid"
        assert eval_rec.needs_parser_fix is True
        assert eval_rec.needs_recrawl is False
        assert "価格異常" in eval_rec.data_quality_issue
        assert eval_rec.first_stage_predicted_price == 0
