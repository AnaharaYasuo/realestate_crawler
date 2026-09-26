from decimal import Decimal
from unittest.mock import MagicMock, patch

from package.utils.converter import parse_menseki, parse_ratio
from package.api.registry import ApiRegistry
from package.api.homes import ParseHomesMansionStartAsync, ParseHomesMansionDetailFuncAsync
from package.parser.homesParser import HomesMansionParser
from package.api.misawa import (
    ParseMisawaMansionStartAsync, ParseMisawaMansionListFuncAsync, ParseMisawaMansionDetailFuncAsync,
    ParseMisawaKodateStartAsync, ParseMisawaKodateListFuncAsync, ParseMisawaKodateDetailFuncAsync,
    ParseMisawaTochiStartAsync, ParseMisawaTochiListFuncAsync, ParseMisawaTochiDetailFuncAsync
)
from package.api.api import (
    _sync_save_error_html_by_url,
    API_KEY_NOMURA_MANSION_REGION_GCP,
    API_KEY_NOMURA_KODATE_REGION_GCP,
    API_KEY_NOMURA_TOCHI_REGION_GCP,
    API_KEY_SUMIFU_MANSION_REGION_GCP,
    API_KEY_SUMIFU_KODATE_REGION_GCP,
    API_KEY_SUMIFU_TOCHI_REGION_GCP,
    API_KEY_TOKYU_MANSION_AREA_GCP,
    API_KEY_TOKYU_KODATE_AREA_GCP,
    API_KEY_TOKYU_TOCHI_AREA_GCP,
    API_KEY_MITSUI_MANSION_AREA_GCP,
    API_KEY_MITSUI_KODATE_AREA_GCP,
    API_KEY_MITSUI_TOCHI_AREA_GCP,
)


def test_converter_quantize_decimal_places():
    # 3 decimal places should be rounded to 2 decimal places
    assert parse_menseki("70.523㎡") == Decimal("70.52")
    assert parse_menseki("70.526㎡") == Decimal("70.53")
    assert parse_menseki("100.999") == Decimal("101.00")
    assert parse_ratio("8.555%") == Decimal("8.56")
    assert parse_ratio("12.341％") == Decimal("12.34")


def test_homes_mansion_parser_class():
    start_proc = ParseHomesMansionStartAsync()
    detail_proc = ParseHomesMansionDetailFuncAsync()
    assert isinstance(start_proc.parser, HomesMansionParser)
    assert isinstance(detail_proc.parser, HomesMansionParser)


def test_misawa_ssl_legacy_ciphers():
    procs = [
        ParseMisawaMansionStartAsync(),
        ParseMisawaMansionListFuncAsync(),
        ParseMisawaMansionDetailFuncAsync(),
        ParseMisawaKodateStartAsync(),
        ParseMisawaKodateListFuncAsync(),
        ParseMisawaKodateDetailFuncAsync(),
        ParseMisawaTochiStartAsync(),
        ParseMisawaTochiListFuncAsync(),
        ParseMisawaTochiDetailFuncAsync(),
    ]
    mock_loop = MagicMock()
    for p in procs:
        connector = p._generateConnector(mock_loop)
        assert connector is not None
        assert connector._ssl is not None


def test_api_registry_resolves_gcp_paths():
    import package.api.nomura  # noqa: F401
    import package.api.sumifu  # noqa: F401
    import package.api.tokyu  # noqa: F401
    import package.api.mitsui  # noqa: F401

    # All GCP legacy endpoints must resolve in ApiRegistry to avoid HTTP 127.0.0.1:8000 fallback
    gcp_paths = [
        API_KEY_NOMURA_MANSION_REGION_GCP,
        API_KEY_NOMURA_KODATE_REGION_GCP,
        API_KEY_NOMURA_TOCHI_REGION_GCP,
        API_KEY_SUMIFU_MANSION_REGION_GCP,
        API_KEY_SUMIFU_KODATE_REGION_GCP,
        API_KEY_SUMIFU_TOCHI_REGION_GCP,
        API_KEY_TOKYU_MANSION_AREA_GCP,
        API_KEY_TOKYU_KODATE_AREA_GCP,
        API_KEY_TOKYU_TOCHI_AREA_GCP,
        API_KEY_MITSUI_MANSION_AREA_GCP,
        API_KEY_MITSUI_KODATE_AREA_GCP,
        API_KEY_MITSUI_TOCHI_AREA_GCP,
    ]
    for path in gcp_paths:
        handler = ApiRegistry.get(path)
        assert handler is not None, f"GCP path {path} must be registered in ApiRegistry"


def test_sync_save_error_html_with_direct_raw_html(tmp_path):
    with patch("requests.get") as mock_get, \
         patch("package.api.api.ERROR_PAGES_DIR", tmp_path), \
         patch("package.api.api.FailureReporter.record_job_failure") as mock_record:
        
        raw = b"<html>Direct Error Content</html>"
        _sync_save_error_html_by_url("https://example.com/item/123", "NomuraMansionModel", "Parse Failure", raw_html=raw)
        
        # requests.get must NOT be called when raw_html is provided
        mock_get.assert_not_called()
        
        # FailureReporter must receive the raw bytes
        mock_record.assert_called_once()
        _, kwargs = mock_record.call_args
        assert kwargs["raw_html"] == raw
