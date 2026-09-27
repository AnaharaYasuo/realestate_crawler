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

    active_lines = [
        line for line in content.splitlines() if not line.lstrip().startswith(("#", "//"))
    ]
    assignments = [
        m.group(1)
        for m in (re.match(r"\s*push_endpoint\s*=\s*(.+)", line) for line in active_lines)
        if m
    ]
    assert len(assignments) == 1, f"expected exactly one active push_endpoint, found {len(assignments)}"
    endpoint_expr = assignments[0].strip()
    fallback_url = (
        '"https://log-api.newrelic.com/log/v1?Api-Key='
        '${trimspace(google_secret_manager_secret_version.new_relic_license_key_version.secret_data)}"'
    )
    assert endpoint_expr == (
        'var.new_relic_log_ingest_url != "" ? var.new_relic_log_ingest_url : ' + fallback_url
    ), "push_endpoint fallback must set Api-Key to exactly the trimspace()-normalized license key"
