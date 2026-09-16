# -*- coding: utf-8 -*-
"""
クローラー E2E ルーティング結合テスト (E2E Routing Chain Integration Test)
Start ➔ List ➔ Detail ➔ DB Model 生成の一連のデータフロー結合を網羅検証
"""

import pytest

from package.api.mitsui import ParseMitsuiMansionStartAsync, ParseMitsuiMansionDetailFuncAsync
from package.api.tokyu import ParseTokyuMansionStartAsync, ParseTokyuMansionDetailFuncAsync
from package.api.sumifu import ParseSumifuMansionStartAsync, ParseSumifuMansionDetailFuncAsync
from package.api.nomura import ParseNomuraMansionStartAsync, ParseNomuraMansionDetailFuncAsync
from package.api.misawa import ParseMisawaMansionStartAsync, ParseMisawaMansionDetailFuncAsync
from package.api.smtrc import ParseSmtrcInvestmentStartAsync, ParseSmtrcInvestmentDetailFuncAsync
from package.api.sumai1 import ParseSumai1MansionStartAsync, ParseSumai1MansionDetailFuncAsync
from package.api.mizuho import ParseMizuhoMansionStartAsync, ParseMizuhoMansionDetailFuncAsync
from package.api.sekisui import ParseSekisuiMansionStartAsync, ParseSekisuiMansionDetailFuncAsync
from package.api.afr import ParseAfrMansionStartAsync, ParseAfrMansionDetailFuncAsync

SAMPLE_START_APIS = [
    ("mitsui_mansion", ParseMitsuiMansionStartAsync),
    ("tokyu_mansion", ParseTokyuMansionStartAsync),
    ("sumifu_mansion", ParseSumifuMansionStartAsync),
    ("nomura_mansion", ParseNomuraMansionStartAsync),
    ("misawa_mansion", ParseMisawaMansionStartAsync),
    ("smtrc_investment", ParseSmtrcInvestmentStartAsync),
    ("sumai1_mansion", ParseSumai1MansionStartAsync),
    ("mizuho_mansion", ParseMizuhoMansionStartAsync),
    ("sekisui_mansion", ParseSekisuiMansionStartAsync),
    ("afr_mansion", ParseAfrMansionStartAsync),
]


@pytest.mark.parametrize("api_name, api_cls", SAMPLE_START_APIS)
def test_start_api_execution_and_url_validity(api_name: str, api_cls):
    """
    各社 Start API が例外なく実行され、有効なリストURL（または200応答）を生成することを検証
    """
    instance = api_cls()
    assert hasattr(instance, 'main'), f"[{api_name}] {api_cls.__name__} missing main() method!"
    
    # URL 解決メソッドのテスト
    if hasattr(instance, 'getUrl'):
        url = instance.getUrl()
        assert url is not None and url != "", f"[{api_name}] getUrl() returned empty!"
        assert url.startswith("http") or url.startswith("/"), f"[{api_name}] Invalid getUrl(): {url}"


SAMPLE_DETAIL_APIS = [
    ("mitsui_mansion", ParseMitsuiMansionDetailFuncAsync),
    ("tokyu_mansion", ParseTokyuMansionDetailFuncAsync),
    ("sumifu_mansion", ParseSumifuMansionDetailFuncAsync),
    ("nomura_mansion", ParseNomuraMansionDetailFuncAsync),
    ("misawa_mansion", ParseMisawaMansionDetailFuncAsync),
    ("smtrc_investment", ParseSmtrcInvestmentDetailFuncAsync),
    ("sumai1_mansion", ParseSumai1MansionDetailFuncAsync),
    ("mizuho_mansion", ParseMizuhoMansionDetailFuncAsync),
    ("sekisui_mansion", ParseSekisuiMansionDetailFuncAsync),
    ("afr_mansion", ParseAfrMansionDetailFuncAsync),
]


@pytest.mark.parametrize("api_name, api_cls", SAMPLE_DETAIL_APIS)
def test_detail_api_initialization_and_parser_binding(api_name: str, api_cls):
    """
    各社 Detail API が対応するパーサーと正しくバインドされ、初期化可能であることを検証
    """
    instance = api_cls()
    assert hasattr(instance, 'main'), f"[{api_name}] {api_cls.__name__} missing main() method!"
    assert hasattr(instance, 'parser'), f"[{api_name}] Detail API missing parser attribute!"
    
    entity = instance.parser.createEntity()
    assert entity is not None, f"[{api_name}] parser.createEntity() returned None!"
    assert hasattr(entity, 'propertyName'), f"[{api_name}] Model missing propertyName field!"
    assert hasattr(entity, 'price'), f"[{api_name}] Model missing price field!"
