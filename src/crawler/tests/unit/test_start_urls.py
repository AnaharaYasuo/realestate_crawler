# -*- coding: utf-8 -*-
"""
全クローラーのスタートAPI・パーサーモデル・本物URLマッピング自動検証テスト
"""
import pytest
import importlib
import pkgutil
from package.api.registry import ApiRegistry
import package.api

# 全APIクラスをApiRegistryに登録するためにpackage.api配下をインポート
for _, module_name, _ in pkgutil.walk_packages(package.api.__path__, package.api.__name__ + "."):
    importlib.import_module(module_name)



ALL_START_TEST_ENTRIES = [
    # 1. mitsui
    ("mitsui", "mansion", "/api/mitsui/mansion/start", "https://www.rehouse.co.jp/sitemap/"),
    ("mitsui", "kodate", "/api/mitsui/kodate/start", "https://www.rehouse.co.jp/sitemap/"),
    ("mitsui", "tochi", "/api/mitsui/tochi/start", "https://www.rehouse.co.jp/sitemap/"),
    ("mitsui", "invest_kodate", "/api/mitsui/investment/kodate/start", "https://www.rehouse.co.jp/sitemap/"),
    ("mitsui", "invest_apartment", "/api/mitsui/investment/apartment/start", "https://www.rehouse.co.jp/sitemap/"),
    # 2. sumifu
    ("sumifu", "mansion", "/api/sumifu/mansion/start", "https://www.stepon.co.jp/sitemap/"),
    ("sumifu", "kodate", "/api/sumifu/kodate/start", "https://www.stepon.co.jp/sitemap/"),
    ("sumifu", "tochi", "/api/sumifu/tochi/start", "https://www.stepon.co.jp/sitemap/"),
    ("sumifu", "invest_kodate", "/api/sumifu/investment/kodate/start", "https://www.stepon.co.jp/sitemap/"),
    ("sumifu", "invest_apartment", "/api/sumifu/investment/apartment/start", "https://www.stepon.co.jp/sitemap/"),
    # 3. tokyu
    ("tokyu", "mansion", "/api/tokyu/mansion/start", "https://www.livable.co.jp/sitemap/"),
    ("tokyu", "kodate", "/api/tokyu/kodate/start", "https://www.livable.co.jp/sitemap/"),
    ("tokyu", "tochi", "/api/tokyu/tochi/start", "https://www.livable.co.jp/sitemap/"),
    ("tokyu", "invest_kodate", "/api/tokyu/investment/kodate/start", "https://www.livable.co.jp/sitemap/"),
    ("tokyu", "invest_apartment", "/api/tokyu/investment/apartment/start", "https://www.livable.co.jp/sitemap/"),
    # 4. nomura
    ("nomura", "mansion", "/api/nomura/mansion/start", "https://www.nomu.com/sitemap/"),
    ("nomura", "kodate", "/api/nomura/kodate/start", "https://www.nomu.com/sitemap/"),
    ("nomura", "tochi", "/api/nomura/tochi/start", "https://www.nomu.com/sitemap/"),
    ("nomura", "invest_kodate", "/api/nomura/investment/kodate/start", "https://www.nomu.com/sitemap/"),
    ("nomura", "invest_apartment", "/api/nomura/investment/apartment/start", "https://www.nomu.com/sitemap/"),
    # 5. misawa
    ("misawa", "mansion", "/api/misawa/mansion/start", "https://www.misawa-mrd.com/buy/mansion/"),
    ("misawa", "kodate", "/api/misawa/kodate/start", "https://www.misawa-mrd.com/buy/kodate/"),
    ("misawa", "tochi", "/api/misawa/tochi/start", "https://www.misawa-mrd.com/buy/tochi/"),
    ("misawa", "invest_kodate", "/api/misawa/investment/kodate/start", "https://www.misawa-mrd.com/buy/invest/"),
    ("misawa", "invest_apartment", "/api/misawa/investment/apartment/start", "https://www.misawa-mrd.com/buy/invest/"),

    # 6. smtrc
    ("smtrc", "mansion", "/api/smtrc/mansion/start", "https://www.smtrc.jp/buy/mansion/"),
    ("smtrc", "kodate", "/api/smtrc/kodate/start", "https://www.smtrc.jp/buy/kodate/"),
    ("smtrc", "tochi", "/api/smtrc/tochi/start", "https://www.smtrc.jp/buy/tochi/"),
    ("smtrc", "investment", "/api/smtrc/investment/start", "https://www.smtrc.jp/buy/investment/"),
    # 7. sumai1
    ("sumai1", "mansion", "/api/sumai1/mansion/start", "https://www.sumai1.com/buy/mansion/"),
    ("sumai1", "kodate", "/api/sumai1/kodate/start", "https://www.sumai1.com/buy/kodate/"),
    ("sumai1", "tochi", "/api/sumai1/tochi/start", "https://www.sumai1.com/buy/tochi/"),
    ("sumai1", "investment", "/api/sumai1/investment/start", "https://www.sumai1.com/buy/investment/"),
    # 8. mizuho
    ("mizuho", "mansion", "/api/mizuho/mansion/start", "https://www.mizuho-re.co.jp/buy/mansion/"),
    ("mizuho", "kodate", "/api/mizuho/kodate/start", "https://www.mizuho-re.co.jp/buy/kodate/"),
    ("mizuho", "tochi", "/api/mizuho/tochi/start", "https://www.mizuho-re.co.jp/buy/tochi/"),
    ("mizuho", "investment", "/api/mizuho/investment/start", "https://www.mizuho-re.co.jp/buy/investment/"),
    # 9. sekisui
    ("sekisui", "mansion", "/api/sekisui/mansion/start", "https://www.sekisuihouse-fudosan.co.jp/buy/mansion/"),
    ("sekisui", "kodate", "/api/sekisui/kodate/start", "https://www.sekisuihouse-fudosan.co.jp/buy/kodate/"),
    ("sekisui", "tochi", "/api/sekisui/tochi/start", "https://www.sekisuihouse-fudosan.co.jp/buy/tochi/"),
    # 10. afr
    ("afr", "mansion", "/api/afr/mansion/start", "https://www.hebel-haus.com/stockhebel/purchase/forhome/searchlist.html"),
    ("afr", "kodate", "/api/afr/kodate/start", "https://www.hebel-haus.com/stockhebel/purchase/forhome/searchlist.html"),
    ("afr", "tochi", "/api/afr/tochi/start", "https://www.hebel-haus.com/stockhebel/purchase/forhome/searchlist.html"),
    # 11. daiwa
    ("daiwa", "mansion", "/api/daiwa/mansion/start", "https://www.daiwahouse.co.jp/stock/search/"),
    ("daiwa", "kodate", "/api/daiwa/kodate/start", "https://www.daiwahouse.co.jp/stock/search/"),
    ("daiwa", "tochi", "/api/daiwa/tochi/start", "https://www.daiwahouse.co.jp/stock/search/"),
    # 12. totate
    ("totate", "mansion", "/api/totate/mansion/start", "https://www.totate-m.jp/buy/mansion/"),
    ("totate", "kodate", "/api/totate/kodate/start", "https://www.totate-m.jp/buy/kodate/"),
    ("totate", "tochi", "/api/totate/tochi/start", "https://www.totate-m.jp/buy/tochi/"),
    # 13. odakyu
    ("odakyu", "mansion", "/api/odakyu/mansion/start", "https://www.odakyu-fudosan.co.jp/sumai/buy/mansion/"),
    ("odakyu", "kodate", "/api/odakyu/kodate/start", "https://www.odakyu-fudosan.co.jp/sumai/buy/kodate/"),
    ("odakyu", "tochi", "/api/odakyu/tochi/start", "https://www.odakyu-fudosan.co.jp/sumai/buy/tochi/"),
    ("odakyu", "investment", "/api/odakyu/investment/start", "https://www.odakyu-fudosan.co.jp/sumai/buy/investment/"),
    # 14. sumirin
    ("sumirin", "mansion", "/api/sumirin/mansion/start", "https://www.sumirin-hs.co.jp/buy/mansion/"),
    ("sumirin", "kodate", "/api/sumirin/kodate/start", "https://www.sumirin-hs.co.jp/buy/kodate/"),
    ("sumirin", "tochi", "/api/sumirin/tochi/start", "https://www.sumirin-hs.co.jp/buy/tochi/"),
    ("sumirin", "investment", "/api/sumirin/investment/start", "https://www.sumirin-hs.co.jp/buy/investment/"),
    # 15. heim
    ("heim", "mansion", "/api/heim/mansion/start", "https://www.heim-est.jp/buy/mansion/"),
    ("heim", "kodate", "/api/heim/kodate/start", "https://www.heim-est.jp/buy/kodate/"),
    ("heim", "tochi", "/api/heim/tochi/start", "https://www.heim-est.jp/buy/tochi/"),
    # 16. rearie
    ("rearie", "mansion", "/api/rearie/mansion/start", "https://www.rearie.jp/buy/mansion/"),
    ("rearie", "kodate", "/api/rearie/kodate/start", "https://www.rearie.jp/buy/kodate/"),
    ("rearie", "tochi", "/api/rearie/tochi/start", "https://www.rearie.jp/buy/tochi/"),
    # 17. keio
    ("keio", "mansion", "/api/keio/mansion/start", "https://www.keio-fudosan.co.jp/buy/mansion/"),
    ("keio", "kodate", "/api/keio/kodate/start", "https://www.keio-fudosan.co.jp/buy/kodate/"),
    ("keio", "tochi", "/api/keio/tochi/start", "https://www.keio-fudosan.co.jp/buy/tochi/"),
    # 18. seibu
    ("seibu", "mansion", "/api/seibu/mansion/start", "https://www.seibu-realestate.co.jp/buy/mansion/"),
    ("seibu", "kodate", "/api/seibu/kodate/start", "https://www.seibu-realestate.co.jp/buy/kodate/"),
    ("seibu", "tochi", "/api/seibu/tochi/start", "https://www.seibu-realestate.co.jp/buy/tochi/"),
    # 19. keikyu
    ("keikyu", "mansion", "/api/keikyu/mansion/start", "https://www.keikyu-sumai.com/buy/mansion/"),
    ("keikyu", "kodate", "/api/keikyu/kodate/start", "https://www.keikyu-sumai.com/buy/kodate/"),
    ("keikyu", "tochi", "/api/keikyu/tochi/start", "https://www.keikyu-sumai.com/buy/tochi/"),
    # 20. sotetsu
    ("sotetsu", "mansion", "/api/sotetsu/mansion/start", "https://www.sotetsu-re.co.jp/buy/mansion/"),
    ("sotetsu", "kodate", "/api/sotetsu/kodate/start", "https://www.sotetsu-re.co.jp/buy/kodate/"),
    ("sotetsu", "tochi", "/api/sotetsu/tochi/start", "https://www.sotetsu-re.co.jp/buy/tochi/"),
    # 21. keisei
    ("keisei", "mansion", "/api/keisei/mansion/start", "https://www.keisei-realestate.co.jp/buy/mansion/"),
    ("keisei", "kodate", "/api/keisei/kodate/start", "https://www.keisei-realestate.co.jp/buy/kodate/"),
    ("keisei", "tochi", "/api/keisei/tochi/start", "https://www.keisei-realestate.co.jp/buy/tochi/"),
    # 22. daikyo
    ("daikyo", "mansion", "/api/daikyo/mansion/start", "https://www.daikyo-anabuki.co.jp/buy/mansion/"),
    ("daikyo", "kodate", "/api/daikyo/kodate/start", "https://www.daikyo-anabuki.co.jp/buy/kodate/"),
    ("daikyo", "tochi", "/api/daikyo/tochi/start", "https://www.daikyo-anabuki.co.jp/buy/tochi/"),
    # 23. homes
    ("homes", "mansion", "/api/homes/mansion/start", "https://www.homes.co.jp/mansion/tokyo/list/"),
    ("homes", "kodate", "/api/homes/kodate/start", "https://www.homes.co.jp/kodate/tokyo/list/"),
    ("homes", "tochi", "/api/homes/tochi/start", "https://www.homes.co.jp/tochi/tokyo/list/"),
    ("homes", "invest_apartment", "/api/homes/investment/apartment/start", "https://toushi.homes.co.jp/"),
    # 24. athome
    ("athome", "mansion", "/api/athome/mansion/start", "https://www.athome.co.jp/mansion/"),
    ("athome", "kodate", "/api/athome/kodate/start", "https://www.athome.co.jp/kodate/"),
    ("athome", "tochi", "/api/athome/tochi/start", "https://www.athome.co.jp/tochi/"),
    ("athome", "invest_apartment", "/api/athome/investment/apartment/start", "https://www.athome.co.jp/buy_other/shubetsu_toushi/"),

]


@pytest.mark.parametrize("company,ptype,api_path,expected_start_url", ALL_START_TEST_ENTRIES)
def test_start_api_registry_and_urls(company, ptype, api_path, expected_start_url):
    """
    全クローラーのスタートAPIエンドポイントがApiRegistryに正常登録されており、
    パーサーインスタンス・モデルインスタンス・本物スタートURLが揃っていることを検証。
    """
    api_cls = ApiRegistry.get(api_path)
    assert api_cls is not None, f"ApiRegistry path '{api_path}' is missing."

    proc_instance = api_cls()
    parser = proc_instance.parser
    assert parser is not None, f"Parser instance for {company}-{ptype} is None."

    entity = parser.createEntity()
    assert entity is not None, f"Parser.createEntity() for {company}-{ptype} returned None."
    assert entity.__class__.__name__.lower().startswith(company.lower()), f"Model mismatch for {company}-{ptype}: {entity.__class__.__name__}"
    assert expected_start_url.startswith("https://"), f"Invalid start URL format for {company}-{ptype}: {expected_start_url}"
