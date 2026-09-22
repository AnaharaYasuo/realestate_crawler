# -*- coding: utf-8 -*-
"""nomura_investment / tokyu_investment のクラウド並列定数 NameError 防止 (Issue #317)"""
import os


def test_nomura_invest_apartment_cloud_parallel_limit_resolves():
    from package.api import nomura_investment as mod

    assert mod.DEFAULT_PARARELL_LIMIT == mod.DEFAULT_PARALLEL_LIMIT
    previous_is_cloud = os.environ.get("IS_CLOUD")
    had_is_cloud = "IS_CLOUD" in os.environ
    os.environ["IS_CLOUD"] = "1"
    try:
        handler = mod.ParseNomuraInvestApartmentListFuncAsync()
        assert handler._getCloudPararellLimit() == mod.DEFAULT_PARALLEL_LIMIT
    finally:
        if had_is_cloud:
            os.environ["IS_CLOUD"] = previous_is_cloud
        else:
            os.environ.pop("IS_CLOUD", None)


def test_tokyu_invest_cloud_parallel_limit_resolves():
    from package.api import tokyu_investment as mod

    assert mod.DEFAULT_PARARELL_LIMIT == mod.DEFAULT_PARALLEL_LIMIT
    # unbound method on base class (avoids abstract __init__)
    limit = mod.ParseTokyuInvestListFuncAsyncBase._getCloudPararellLimit(None)
    assert limit == mod.DEFAULT_PARALLEL_LIMIT
