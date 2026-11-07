# -*- coding: utf-8 -*-
from package.api.nomura import (
    MIDDLE_PARARELL_LIMIT,
    ParseNomuraMansionListFuncAsync,
    ParseNomuraKodateListFuncAsync,
    ParseNomuraTochiListFuncAsync,
)


def test_nomura_list_parallel_limit_is_middle():
    """野村不動産の各ListFuncAsyncの並行度がMIDDLE_PARARELL_LIMIT (3) に設定されていること (Issue #1310)"""
    mansion_list = ParseNomuraMansionListFuncAsync()
    assert mansion_list._getLocalPararellLimit() == MIDDLE_PARARELL_LIMIT
    assert mansion_list._getCloudPararellLimit() == MIDDLE_PARARELL_LIMIT
    assert mansion_list._getLocalPararellLimit() == 3

    kodate_list = ParseNomuraKodateListFuncAsync()
    assert kodate_list._getLocalPararellLimit() == MIDDLE_PARARELL_LIMIT
    assert kodate_list._getCloudPararellLimit() == MIDDLE_PARARELL_LIMIT
    assert kodate_list._getLocalPararellLimit() == 3

    tochi_list = ParseNomuraTochiListFuncAsync()
    assert tochi_list._getLocalPararellLimit() == MIDDLE_PARARELL_LIMIT
    assert tochi_list._getCloudPararellLimit() == MIDDLE_PARARELL_LIMIT
    assert tochi_list._getLocalPararellLimit() == 3
