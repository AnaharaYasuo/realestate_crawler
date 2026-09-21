# -*- coding: utf-8 -*-
from unittest.mock import patch, MagicMock
from routes.tokyu_routes import tokyuTochiStart, tokyuKodateStart, tokyuMansionStart


def test_tokyu_tochi_start_url():
    """東急土地スタートURLが全国エリア選択ページhttps://www.livable.co.jp/kounyu/tochi/select-area/であることを検証"""
    with patch("routes.tokyu_routes.ParseTokyuTochiStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.livable.co.jp/kounyu/tochi/tokyo/select-area/"]
        mock_cls.return_value = mock_instance

        res = tokyuTochiStart()
        mock_instance.main.assert_called_once_with("https://www.livable.co.jp/kounyu/tochi/select-area/")
        assert res == ["https://www.livable.co.jp/kounyu/tochi/tokyo/select-area/"]


def test_tokyu_kodate_start_url():
    """東急戸建てスタートURLが全国エリア選択ページhttps://www.livable.co.jp/kounyu/kodate/select-area/であることを検証"""
    with patch("routes.tokyu_routes.ParseTokyuKodateStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.livable.co.jp/kounyu/kodate/tokyo/select-area/"]
        mock_cls.return_value = mock_instance

        res = tokyuKodateStart()
        mock_instance.main.assert_called_once_with("https://www.livable.co.jp/kounyu/kodate/select-area/")
        assert res == ["https://www.livable.co.jp/kounyu/kodate/tokyo/select-area/"]


def test_tokyu_mansion_start_url():
    """東急マンションスタートURLが全国エリア選択ページhttps://www.livable.co.jp/kounyu/chuko-mansion/select-area/であることを検証"""
    with patch("routes.tokyu_routes.ParseTokyuMansionStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/select-area/"]
        mock_cls.return_value = mock_instance

        res = tokyuMansionStart()
        mock_instance.main.assert_called_once_with("https://www.livable.co.jp/kounyu/chuko-mansion/select-area/")
        assert res == ["https://www.livable.co.jp/kounyu/chuko-mansion/tokyo/select-area/"]
