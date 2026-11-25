import inspect

from scripts.debug_tools import auto_heal_parsers


def test_auto_heal_parsers_excludes_source_data_invalid():
    """auto_heal_parsers.py の PropertyEvaluation スキャンが heal_status='source_data_invalid' を除外すること (#1468)"""
    src = inspect.getsource(auto_heal_parsers)
    assert 'heal_status", None) == "source_data_invalid"' in src
