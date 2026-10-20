from package.api.sumifu_investment import (
    ParseSumifuInvestKodateStartAsync,
    ParseSumifuInvestApartmentStartAsync,
)


def test_sumifu_investment_seed_urls():
    """Verify that sumifu investment seed URLs use correct smk bitmask for kodate and apartment."""
    kodate_urls = ParseSumifuInvestKodateStartAsync.urlList
    assert len(kodate_urls) == 1
    # 投資用戸建 is 6th bit (value 7 -> 000001000000)
    assert "smk=000001000000" in kodate_urls[0]
    assert "type=pro2" in kodate_urls[0] or "ca_0_001" in kodate_urls[0]

    apt_urls = ParseSumifuInvestApartmentStartAsync.urlList
    assert len(apt_urls) == 1
    # アパート(一棟) is 3rd bit (value 10 -> 001000000000)
    assert "smk=001000000000" in apt_urls[0]
    assert "type=pro2" in apt_urls[0] or "ca_0_001" in apt_urls[0]


def test_sotetsu_routes_do_not_restrict_to_single_city():
    """Verify sotetsu routes do not hardcode a single municipality code (a5[]=13209)."""
    import inspect
    from routes import sotetsu_routes

    src = inspect.getsource(sotetsu_routes)
    assert "a5[]=" not in src
    assert "a5%5B%5D=" not in src
