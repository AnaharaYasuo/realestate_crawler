# -*- coding: utf-8 -*-
from unittest.mock import patch, MagicMock
from routes.tokyu_routes import tokyuTochiStart, tokyuKodateStart, tokyuMansionStart


def test_tokyu_tochi_start_url():
    """東急土地スタートURLが404の旧URLではなくhttps://www.livable.co.jp/kounyu/tochi/であることを検証"""
    with patch("routes.tokyu_routes.ParseTokyuTochiStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.livable.co.jp/kounyu/tochi/select-area/tokyo/"]
        mock_cls.return_value = mock_instance

        res = tokyuTochiStart()
        mock_instance.main.assert_called_once_with("https://www.livable.co.jp/kounyu/tochi/")
        assert res == ["https://www.livable.co.jp/kounyu/tochi/select-area/tokyo/"]


def test_tokyu_kodate_start_url():
    """東急戸建てスタートURLが301リダイレクトを避けてhttps://www.livable.co.jp/kounyu/kodate/であることを検証"""
    with patch("routes.tokyu_routes.ParseTokyuKodateStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.livable.co.jp/kounyu/kodate/select-area/tokyo/"]
        mock_cls.return_value = mock_instance

        res = tokyuKodateStart()
        mock_instance.main.assert_called_once_with("https://www.livable.co.jp/kounyu/kodate/")
        assert res == ["https://www.livable.co.jp/kounyu/kodate/select-area/tokyo/"]


def test_tokyu_mansion_start_url():
    """東急マンションスタートURLがhttps://www.livable.co.jp/mansion/であることを検証"""
    with patch("routes.tokyu_routes.ParseTokyuMansionStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.livable.co.jp/kounyu/chuko-mansion/select-area/tokyo/"]
        mock_cls.return_value = mock_instance

        res = tokyuMansionStart()
        mock_instance.main.assert_called_once_with("https://www.livable.co.jp/mansion/")
        assert res == ["https://www.livable.co.jp/kounyu/chuko-mansion/select-area/tokyo/"]
