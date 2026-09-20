# -*- coding: utf-8 -*-
"""
アットホーム（Athome） パーサー ユニットテスト
※ 固定モックHTMLおよびインラインHTML依存は完全に根絶し、パーサー契約・モデルを検証します。
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from package.parser.athomeParser import AthomeMansionParser, AthomeKodateParser, AthomeInvestmentApartmentParser
from package.models.athome import AthomeMansion, AthomeKodate, AthomeInvestmentApartment

def test_athome_mansion_parser():
    parser = AthomeMansionParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeMansion)

def test_athome_kodate_parser():
    parser = AthomeKodateParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeKodate)

def test_athome_investment_apartment_parser():
    parser = AthomeInvestmentApartmentParser()
    item = parser.createEntity()
    assert isinstance(item, AthomeInvestmentApartment)

def test_athome_url_resolution():
    parser = AthomeKodateParser()
    base = "https://www.athome.co.jp/kodate/chuko/tokyo/tokyo_fuchu-city/list/"
    rel_url = "/kodate/1012790620/?DOWN=1&BKLISTID=001LPC"
    resolved = parser.getRootDestUrl(rel_url, base_domain=base)
    assert resolved == "https://www.athome.co.jp/kodate/1012790620/?DOWN=1&BKLISTID=001LPC"
    assert "//kodate" not in resolved
    assert "/list//kodate" not in resolved


@pytest.mark.asyncio
async def test_human_mouse_move_uses_bounded_curve_and_reaches_destination():
    """The secure PRNG path still emits every step and lands exactly on target."""

    class FixedSystemRandom:
        def uniform(self, start, end):
            return (start + end) / 2

        def randint(self, start, end):
            return 15 if (start, end) == (15, 35) else 0

    parser = AthomeKodateParser()
    page = MagicMock()
    page.mouse.move = AsyncMock()

    with patch(
        "package.parser.athomeParser.secrets.SystemRandom",
        return_value=FixedSystemRandom(),
    ) as system_random, patch(
        "package.parser.athomeParser.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        await parser._humanMouseMove(page, 10, 20, 110, 80)

    system_random.assert_called_once_with()
    assert page.mouse.move.await_count == 16
    assert sleep.await_count == 16
    assert page.mouse.move.await_args_list[-1].args == (110, 80)
    assert all(
        isinstance(coordinate, int)
        for call in page.mouse.move.await_args_list
        for coordinate in call.args
    )
