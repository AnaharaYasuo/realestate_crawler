from unittest.mock import MagicMock, patch

from package.api.api import ParseDetailPageAsyncBase


class _DummyDetailProc(ParseDetailPageAsyncBase):
    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.parser = None

    def _generateParser(self):
        return None

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 30

    def _getApiKey(self):
        return ""


def test_sync_mark_delisted_clears_needs_parser_fix_and_quality_issue():
    """掲載終了(ListingEndedException)検知時に needs_parser_fix / heal_status / data_quality_issue がクリアされること (#1468)"""
    proc = _DummyDetailProc(
        "https://homes.panasonic.com/rearie/buy/property/mansion/detail.html?id=33991"
    )
    mock_eval = MagicMock()
    mock_eval.is_published = True
    mock_eval.needs_parser_fix = True
    mock_eval.needs_recrawl = True
    mock_eval.heal_status = "detected"
    mock_eval.data_quality_issue = "必須項目欠損 (物件名が未抽出)"

    with patch.object(proc, "_find_existing_evaluation", return_value=mock_eval):
        proc._sync_persist_delisted()

    assert mock_eval.is_published is False
    assert mock_eval.delisted_at is not None
    assert mock_eval.needs_parser_fix is False
    assert mock_eval.needs_recrawl is False
    assert mock_eval.heal_status == "healthy"
    assert mock_eval.data_quality_issue == ""
    mock_eval.save.assert_called_once()


def test_auto_heal_parsers_excludes_source_data_invalid():
    """auto_heal_parsers.py の PropertyEvaluation スキャンが heal_status='source_data_invalid' を除外すること (#1468)"""
    import inspect
    from scripts.debug_tools import auto_heal_parsers

    src = inspect.getsource(auto_heal_parsers)
    assert 'heal_status", None) == "source_data_invalid"' in src
