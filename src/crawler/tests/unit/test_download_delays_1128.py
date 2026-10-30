import pytest
from package.api.api import ParseDetailPageAsyncBase


def test_site_download_delays_configured_for_sumai1_and_odakyu():
    delays = ParseDetailPageAsyncBase.SITE_DOWNLOAD_DELAYS
    assert "sumai1" in delays, "sumai1 should be present in SITE_DOWNLOAD_DELAYS"
    assert delays["sumai1"] == 0.5, "sumai1 delay should be 0.5s"
    assert "odakyu" in delays, "odakyu should be present in SITE_DOWNLOAD_DELAYS"
    assert delays["odakyu"] == 0.5, "odakyu delay should be 0.5s"
