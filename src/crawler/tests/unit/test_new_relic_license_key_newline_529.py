# -*- coding: utf-8 -*-
"""Issue #529: New Relic license key must be normalized (no surrounding whitespace/newline)."""
import os
import re
from unittest.mock import MagicMock, patch

import pytest

from package.utils.newrelic_helper import init_new_relic

TERRAFORM_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "terraform")
)


def _mock_newrelic_modules():
    mock_agent = MagicMock()
    mock_module = MagicMock()
    mock_module.agent = mock_agent
    return mock_agent, {"newrelic": mock_module, "newrelic.agent": mock_agent}


@pytest.mark.parametrize("raw_key", ["abc123NRAL\n", "  abc123NRAL\r\n", "\tabc123NRAL "])
def test_init_new_relic_strips_license_key_and_writes_back(raw_key):
    mock_agent, modules = _mock_newrelic_modules()
    observed = {}
    mock_agent.initialize.side_effect = lambda *a, **k: observed.setdefault(
        "key", os.environ.get("NEW_RELIC_LICENSE_KEY")
    )
    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": raw_key}):
        with patch.dict("sys.modules", modules):
            assert init_new_relic() is True
            assert os.environ["NEW_RELIC_LICENSE_KEY"] == "abc123NRAL"
    mock_agent.initialize.assert_called_once()
    assert observed["key"] == "abc123NRAL"


@pytest.mark.parametrize("blank_key", ["", "\n", "  \r\n\t "])
def test_init_new_relic_treats_blank_license_key_as_unset(blank_key):
    mock_agent, modules = _mock_newrelic_modules()
    with patch.dict(os.environ, {"NEW_RELIC_LICENSE_KEY": blank_key}):
        with patch.dict("sys.modules", modules):
            assert init_new_relic() is False
    mock_agent.initialize.assert_not_called()


def test_push_endpoint_trims_license_key():
    tf_path = os.path.join(TERRAFORM_DIR, "new_relic_gcp_integration.tf")
    with open(tf_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"push_endpoint\s*=\s*(.+)", content)
    assert match is not None, "push_endpoint not found"
    endpoint_expr = match.group(1)
    assert re.search(
        r"Api-Key=\$\{trimspace\(google_secret_manager_secret_version\."
        r"new_relic_license_key_version\.secret_data\)\}",
        endpoint_expr,
    ), "push_endpoint must embed the license key via trimspace()"
    assert "Api-Key=${google_secret_manager_secret_version" not in endpoint_expr
