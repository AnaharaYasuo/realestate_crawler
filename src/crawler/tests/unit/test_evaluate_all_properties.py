# -*- coding: utf-8 -*-
from unittest.mock import MagicMock
from scripts.debug_tools.evaluate_all_properties import (
    _extract_area,
    _resolve_company_code,
    _calculate_distribution_stats
)


class TestExtractArea:
    """面積抽出ヘルパーのテスト（CodeRabbit指摘: 欠損時は 0.0 を返し統計対象外とする）"""

    def test_extract_area_senyu_menseki(self):
        """専有面積がある場合はその値を返すことを確認する。"""
        item = MagicMock()
        item.senyuMenseki = 65.5
        item.tatemonoMenseki = None
        item.tochiMenseki = None
        assert _extract_area(item) == 65.5

    def test_extract_area_tatemono_menseki(self):
        """専有面積がなく建物面積がある場合は建物面積を返すことを確認する。"""
        item = MagicMock()
        item.senyuMenseki = None
        item.tatemonoMenseki = 88.0
        item.tochiMenseki = None
        assert _extract_area(item) == 88.0

    def test_extract_area_tochi_menseki(self):
        """建物面積もなく土地面積がある場合は土地面積を返すことを確認する。"""
        item = MagicMock()
        item.senyuMenseki = None
        item.tatemonoMenseki = None
        item.tochiMenseki = 120.3
        assert _extract_area(item) == 120.3

    def test_extract_area_all_missing_returns_zero(self):
        """全ての面積属性がNoneの場合、10.0ではなく0.0を返して面積閾値（area >= 10.0）で除外可能とすること"""
        item = MagicMock()
        item.senyuMenseki = None
        item.tatemonoMenseki = None
        item.tochiMenseki = None
        assert _extract_area(item) == 0.0


class TestResolveCompanyCode:
    """モデル名からの会社コード解決テスト"""

    def test_resolve_known_companies(self):
        """既知のモデル名を対応する会社コードへ解決できることを確認する。"""
        assert _resolve_company_code("mitsuimansion") == "mitsui"
        assert _resolve_company_code("sumifukodate") == "sumifu"
        assert _resolve_company_code("tokyuinvestmentapartment") == "tokyu"
        assert _resolve_company_code("nomuratochi") == "nomura"
        assert _resolve_company_code("misawamansion") == "misawa"
        assert _resolve_company_code("athomekodate") == "athome"
        assert _resolve_company_code("homesmansion") == "homes"

    def test_resolve_unknown_company(self):
        """未知のモデル名はunknownへ解決されることを確認する。"""
        assert _resolve_company_code("othercompany") == "unknown"


class TestDistributionStats:
    """統計量計算および正規分布適合判定のテスト"""

    def test_empty_errors(self):
        """誤差データが空の場合はデータ不足として扱われることを確認する。"""
        n, mean_err, std_err, skewness, kurtosis, status_str = _calculate_distribution_stats([])
        assert n == 0
        assert status_str == "データ不足のため判定不能"

    def test_normal_distribution_stats(self):
        """十分な誤差データから分布統計を計算できることを確認する。"""
        errors = [0.01, -0.02, 0.03, -0.01, 0.02, -0.03]
        n, mean_err, std_err, skewness, kurtosis, status_str = _calculate_distribution_stats(errors)
        assert n == 6
        assert abs(mean_err) <= 0.05
        assert "適合" in status_str
