# -*- coding: utf-8 -*-
"""
Unit tests for Issue #925:
Execution issues resolution, auto_heal path fix, parser fallback resilience, and code quality.
"""
import os
from bs4 import BeautifulSoup

from package.parser.mitsuiParser import MitsuiMansionParser
from package.parser.sumifuParser import SumifuMansionParser
from scripts.debug_tools.auto_heal_parsers import get_project_root, _get_cb_state_path


def test_auto_heal_project_root_resolution():
    """Verify get_project_root resolves to true repo root, not src."""
    root = get_project_root()
    assert os.path.exists(root), f"Resolved root {root} does not exist"
    # Root should contain src and docs directories
    assert os.path.isdir(os.path.join(root, "src")), "Root must contain 'src' directory"
    assert not root.endswith("src"), "Root must not be the 'src' directory itself"

    cb_path = _get_cb_state_path()
    assert "src/Temp" not in cb_path.replace("\\", "/"), f"Circuit breaker path must not be inside src: {cb_path}"
    assert cb_path.replace("\\", "/").endswith("Temp/gemini_circuit_breaker.json"), f"Unexpected cb path: {cb_path}"


def test_mitsui_traffic_fallback_and_labels():
    """Verify MitsuiParser extracts traffic from varied labels and specs fallback."""
    parser = MitsuiMansionParser()

    # Case 1: Label 最寄り駅
    html_1 = """
    <html><body><table><tr><th>最寄り駅</th><td><p>JR山手線 渋谷駅 徒歩5分</p></td></tr></table></body></html>
    """
    soup_1 = BeautifulSoup(html_1, "html.parser")
    lines_1 = parser._parseTrafficLines(soup_1)
    assert len(lines_1) == 1
    assert "渋谷駅" in lines_1[0]

    # Case 2: Label 交通 with text
    html_2 = """
    <html><body><table><tr><th>交通</th><td>東京メトロ銀座線 表参道駅 徒歩3分</td></tr></table></body></html>
    """
    soup_2 = BeautifulSoup(html_2, "html.parser")
    lines_2 = parser._parseTrafficLines(soup_2)
    assert len(lines_2) == 1
    assert "表参道駅" in lines_2[0]

    # Case 3: Label 沿線・駅
    html_3 = """
    <html><body><table><tr><th>沿線・駅</th><td><p>東急東横線 中目黒駅 徒歩7分</p></td></tr></table></body></html>
    """
    soup_3 = BeautifulSoup(html_3, "html.parser")
    lines_3 = parser._parseTrafficLines(soup_3)
    assert len(lines_3) == 1
    assert "中目黒駅" in lines_3[0]

    # Case 4: Table missing label, fallback to _specs
    html_4 = "<html><body><table></table></body></html>"
    soup_4 = BeautifulSoup(html_4, "html.parser")
    specs_4 = {"交通": "都営大江戸線 六本木駅 徒歩2分"}
    lines_4 = parser._parseTrafficLines(soup_4, _specs=specs_4)
    assert len(lines_4) == 1
    assert "六本木駅" in lines_4[0]


def test_mitsui_kaisu_fallback():
    """Verify MitsuiParser extracts kaisu string from diverse table labels and specs keys."""
    parser = MitsuiMansionParser()

    # Case 1: 所在階/階建 in table
    html_1 = """
    <html><body><table><tr><th>所在階 / 階建</th><td>10階 / 地上20階建</td></tr></table></body></html>
    """
    soup_1 = BeautifulSoup(html_1, "html.parser")
    assert "10階" in parser._parseKaisuStr(soup_1)
    assert parser._parseKaisu(soup_1) == 10

    # Case 2: Specs fallback with 所在階・階建
    html_2 = "<html><body><table></table></body></html>"
    soup_2 = BeautifulSoup(html_2, "html.parser")
    specs_2 = {"所在階・階建": "5階 / 地上14階建"}
    assert "5階" in parser._parseKaisuStr(soup_2, specs=specs_2)
    assert parser._parseKaisu(soup_2, _specs=specs_2) == 5


def test_sumifu_kaisu_and_traffic_fallbacks():
    """Verify SumifuParser extracts kaisu and traffic with fallbacks."""
    parser = SumifuMansionParser()

    # Case 1: Kaisu with 階数 key
    specs = {"階数": "3階・RC造"}
    assert parser._parseKaisuRaw(None, specs=specs) == "3階・RC造"
    assert parser._parseKaisu(None, _specs=specs) == 3

    # Case 2: Kaisu with 所在階構造 key
    specs_alt = {"所在階構造": "7階・SRC造"}
    assert parser._parseKaisuRaw(None, specs=specs_alt) == "7階・SRC造"
    assert parser._parseKaisu(None, _specs=specs_alt) == 7

    # Case 3: Traffic fallback from specs
    html_empty = "<html><body><table></table></body></html>"
    soup_empty = BeautifulSoup(html_empty, "html.parser")
    specs_traffic = {"交通": "JR中央線 新宿駅 徒歩4分"}
    traffic_lines = parser._parseTrafficLines(soup_empty, _specs=specs_traffic)
    assert len(traffic_lines) == 1
    assert "新宿駅" in traffic_lines[0]
