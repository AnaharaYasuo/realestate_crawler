import json
from unittest.mock import patch, MagicMock
from flask import Flask
from routes.mizuho_routes import (
    get_start_url,
    mizuhoMansionStart,
    mizuhoMansionDetail,
    mizuhoKodateStart,
    mizuhoKodateDetail,
    mizuhoTochiStart,
    mizuhoTochiDetail,
    mizuhoInvestmentStart,
    mizuhoInvestmentDetail
)

app = Flask(__name__)


def test_mizuho_get_start_url_prefecture_level():
    """みずほのスタートURLが404となるcity_13102ではなくpref_13/list/であることを検証"""
    assert get_start_url('Mansion') == "https://www.mizuho-re.co.jp/buyers/search/area/type_Mansion/pref_13/list/"
    assert get_start_url('House') == "https://www.mizuho-re.co.jp/buyers/search/area/type_House/pref_13/list/"
    assert get_start_url('Land') == "https://www.mizuho-re.co.jp/buyers/search/area/type_Land/pref_13/list/"


def test_mizuho_mansion_start():
    """マンション一覧取得エンドポイントが正しいURLでパーサーを呼び出すことを検証。"""
    with patch("routes.mizuho_routes.ParseMizuhoMansionStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.mizuho-re.co.jp/buyers/property/000000000001/"]
        mock_cls.return_value = mock_instance

        res = mizuhoMansionStart()
        mock_instance.main.assert_called_once_with(
            "https://www.mizuho-re.co.jp/buyers/search/area/type_Mansion/pref_13/list/"
        )
        assert res == ["https://www.mizuho-re.co.jp/buyers/property/000000000001/"]


def test_mizuho_mansion_detail():
    """マンション詳細取得エンドポイントがリクエストURLでパーサーを呼び出すことを検証。"""
    with app.test_request_context(json={"url": "https://www.mizuho-re.co.jp/buyers/property/000000000001/"}):
        with patch("routes.mizuho_routes.ParseMizuhoMansionDetailFuncAsync") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            res = mizuhoMansionDetail()
            mock_instance.main.assert_called_once_with("https://www.mizuho-re.co.jp/buyers/property/000000000001/")
            assert res == ("finish", 200)


def test_mizuho_kodate_start():
    """戸建て一覧取得エンドポイントが正しいURLでパーサーを呼び出すことを検証。"""
    with patch("routes.mizuho_routes.ParseMizuhoKodateStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.mizuho-re.co.jp/buyers/property/000000000002/"]
        mock_cls.return_value = mock_instance

        res = mizuhoKodateStart()
        mock_instance.main.assert_called_once_with(
            "https://www.mizuho-re.co.jp/buyers/search/area/type_House/pref_13/list/"
        )
        assert res == ["https://www.mizuho-re.co.jp/buyers/property/000000000002/"]


def test_mizuho_kodate_detail():
    """戸建て詳細取得エンドポイントがリクエストURLでパーサーを呼び出すことを検証。"""
    with app.test_request_context(json={"url": "https://www.mizuho-re.co.jp/buyers/property/000000000002/"}):
        with patch("routes.mizuho_routes.ParseMizuhoKodateDetailFuncAsync") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            res = mizuhoKodateDetail()
            mock_instance.main.assert_called_once_with("https://www.mizuho-re.co.jp/buyers/property/000000000002/")
            assert res == ("finish", 200)


def test_mizuho_tochi_start():
    """土地一覧取得エンドポイントが正しいURLでパーサーを呼び出すことを検証。"""
    with patch("routes.mizuho_routes.ParseMizuhoTochiStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.mizuho-re.co.jp/buyers/property/000000000003/"]
        mock_cls.return_value = mock_instance

        res = mizuhoTochiStart()
        mock_instance.main.assert_called_once_with(
            "https://www.mizuho-re.co.jp/buyers/search/area/type_Land/pref_13/list/"
        )
        assert res == ["https://www.mizuho-re.co.jp/buyers/property/000000000003/"]


def test_mizuho_tochi_detail():
    """土地詳細取得エンドポイントがリクエストURLでパーサーを呼び出すことを検証。"""
    with app.test_request_context(json={"url": "https://www.mizuho-re.co.jp/buyers/property/000000000003/"}):
        with patch("routes.mizuho_routes.ParseMizuhoTochiDetailFuncAsync") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            res = mizuhoTochiDetail()
            mock_instance.main.assert_called_once_with("https://www.mizuho-re.co.jp/buyers/property/000000000003/")
            assert res == ("finish", 200)


def test_mizuho_investment_start():
    """投資用物件一覧取得エンドポイントが正しいURLでパーサーを呼び出すことを検証。"""
    with patch("routes.mizuho_routes.ParseMizuhoInvestmentStartAsync") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.main.return_value = ["https://www.mizuho-re.co.jp/investors/property/000000000004/"]
        mock_cls.return_value = mock_instance

        res = mizuhoInvestmentStart()
        mock_instance.main.assert_called_once_with(
            "https://www.mizuho-re.co.jp/investors/search/area/all_apartment-building-dormitory-office-store-warehouse-factory-land-other/pref_13/list/"
        )
        assert res == ["https://www.mizuho-re.co.jp/investors/property/000000000004/"]


def test_mizuho_investment_detail():
    """投資用物件詳細取得エンドポイントがリクエストURLでパーサーを呼び出すことを検証。"""
    with app.test_request_context(json={"url": "https://www.mizuho-re.co.jp/investors/property/000000000004/"}):
        with patch("routes.mizuho_routes.ParseMizuhoInvestmentDetailFuncAsync") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            res = mizuhoInvestmentDetail()
            mock_instance.main.assert_called_once_with("https://www.mizuho-re.co.jp/investors/property/000000000004/")
            assert res == ("finish", 200)


def test_mizuho_detail_with_json_string():
    """文字列形式のJSONペイロードがjson.loadsで透過的に処理されることを検証。"""
    with app.test_request_context(json=json.dumps({"url": "https://www.mizuho-re.co.jp/buyers/property/000000000005/"})):
        with patch("routes.mizuho_routes.ParseMizuhoMansionDetailFuncAsync") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            res = mizuhoMansionDetail()
            mock_instance.main.assert_called_once_with("https://www.mizuho-re.co.jp/buyers/property/000000000005/")
            assert res == ("finish", 200)
