# -*- coding: utf-8 -*-
import pytest
from bs4 import BeautifulSoup
from package.parser.baseParser import check_site_maintenance, SiteMaintenanceException, ServerBusyException


def test_check_site_maintenance_detects_emergency_and_system_maintenance():
    # 1. Title contains maintenance
    soup1 = BeautifulSoup("<html><head><title>緊急メンテナンスのお知らせ</title></head><body></body></html>", "html.parser")
    with pytest.raises(SiteMaintenanceException) as exc_info:
        check_site_maintenance(soup1, "sotetsu")
    assert "緊急メンテナンスのお知らせ" in str(exc_info.value)
    assert issubclass(SiteMaintenanceException, ServerBusyException)

    # 2. H1 contains maintenance
    soup2 = BeautifulSoup("<html><head><title>不動産</title></head><body><h1>システムメンテナンス中</h1></body></html>", "html.parser")
    with pytest.raises(SiteMaintenanceException) as exc_info2:
        check_site_maintenance(soup2, "misawa")
    assert "システムメンテナンス中" in str(exc_info2.value)

    # 3. Normal page does not raise
    normal_soup = BeautifulSoup("<html><head><title>中古戸建て一覧 | 相鉄不動産</title></head><body><h1>一覧</h1></body></html>", "html.parser")
    check_site_maintenance(normal_soup, "sotetsu")
