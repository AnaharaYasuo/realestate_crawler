# -*- coding: utf-8 -*-
"""Unit tests for the runtime hardening changes introduced by issue #250."""

import asyncio
import runpy
import ssl
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

import package.api as api_package
import realestateSettings
from package.api import api as api_module
from package.api.api import ApiAsyncProcBase, TCP_CONNECTOR_LIMIT
from package.parser.athomeParser import AthomeParser
from scripts.debug_tools import debug_misawa_urls


class DummyProc(ApiAsyncProcBase):
    def _callApi(self, *args, **kwargs):
        return None

    def _generateParser(self, *args, **kwargs):
        return None

    def _getApiKey(self, *args, **kwargs):
        return None

    def _getCloudPararellLimit(self, *args, **kwargs):
        return 1

    def _getLocalPararellLimit(self, *args, **kwargs):
        return 1

    def _getTimeOutSecond(self, *args, **kwargs):
        return 1

    def _getTreatPageArg(self, *args, **kwargs):
        return None

    async def _treatPage(self, *args, **kwargs):
        return None


def test_api_connector_uses_default_verified_ssl_context():
    captured = {}

    def capture_connector(**kwargs):
        captured.update(kwargs)
        return object()

    with patch.object(api_module.aiohttp, "TCPConnector", side_effect=capture_connector):
        connector = DummyProc()._generateConnector(MagicMock(name="event_loop"))

    assert connector is not None
    assert captured["limit"] == TCP_CONNECTOR_LIMIT
    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_misawa_debug_client_uses_default_verified_ssl_context():
    assert debug_misawa_urls.ctx.check_hostname is True
    assert debug_misawa_urls.ctx.verify_mode == ssl.CERT_REQUIRED


def test_api_log_directory_is_project_local_not_public_tmp():
    source_root = Path(api_package.__file__).resolve().parents[3]
    expected = source_root / "logs" / "crawler_logs"

    assert Path(api_package.log_dir).resolve() == expected.resolve()
    assert not Path(api_package.log_dir).resolve().is_relative_to(Path("/tmp"))


@pytest.mark.parametrize(
    ("configured_host", "expected_host"),
    [(None, "localhost"), ("cloudsql-proxy.internal", "cloudsql-proxy.internal")],
)
def test_cloud_database_host_has_safe_default_and_honors_override(
    configured_host, expected_host, monkeypatch
):
    fake_settings = SimpleNamespace(configured=False)

    def configure_settings(**kwargs):
        fake_settings.configured = True
        fake_settings.kwargs = kwargs

    fake_settings.configure = configure_settings
    monkeypatch.setattr(realestateSettings, "settings", fake_settings)
    monkeypatch.setattr(realestateSettings.django, "setup", MagicMock())
    monkeypatch.setattr(sys, "argv", ["crawler-service"])
    for env_name in ["FORCE_SQLITE", "K_SERVICE", "CLOUD_RUN_JOB", "GOOGLE_CLOUD_PROJECT"]:
        monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv("IS_CLOUD", "true")
    if configured_host is None:
        monkeypatch.delenv("DB_HOST", raising=False)
    else:
        monkeypatch.setenv("DB_HOST", configured_host)

    realestateSettings.configure()

    assert fake_settings.kwargs["DATABASES"]["default"]["HOST"] == expected_host
    realestateSettings.django.setup.assert_called_once_with()


@pytest.mark.asyncio
async def test_human_mouse_move_uses_system_random_and_preserves_endpoints():
    class DummyAthomeParser(AthomeParser):
        def createEntity(self, *args, **kwargs):
            return None

    prng = MagicMock()
    prng.randint.side_effect = [0, 0, 0, 0, 1]
    prng.uniform.side_effect = [0.25, 0.25, 0.75, 0.75, 0.0, 0.0, 0.001, 0.001]
    page = MagicMock()
    page.mouse.move = AsyncMock()

    with patch("package.parser.athomeParser.secrets.SystemRandom", return_value=prng) as system_random, patch(
        "package.parser.athomeParser.asyncio.sleep", new_callable=AsyncMock
    ) as sleep:
        await DummyAthomeParser()._humanMouseMove(page, 0, 0, 100, 100)

    system_random.assert_called_once_with()
    assert prng.randint.call_args_list[-1] == call(15, 35)
    assert page.mouse.move.await_args_list == [call(0, 0), call(100, 100)]
    assert sleep.await_count == 2
    assert all(args.args[0] > 0 for args in sleep.await_args_list)


def test_count_new_items_uses_model_metadata_and_orm(monkeypatch, capsys):
    matching_manager = MagicMock()
    matching_manager.filter.return_value.count.return_value = 7
    empty_manager = MagicMock()
    empty_manager.filter.return_value.count.return_value = 0

    matching_model = type(
        "MatchingModel",
        (),
        {
            "inputDateTime": object(),
            "_meta": SimpleNamespace(db_table="matching_properties"),
            "objects": matching_manager,
        },
    )
    empty_model = type(
        "EmptyModel",
        (),
        {
            "inputDateTime": object(),
            "_meta": SimpleNamespace(db_table="empty_properties"),
            "objects": empty_manager,
        },
    )
    model_without_timestamp = type(
        "NoTimestampModel",
        (),
        {"_meta": SimpleNamespace(db_table="no_timestamp"), "objects": MagicMock()},
    )
    fake_apps = SimpleNamespace(
        get_models=MagicMock(return_value=[matching_model, empty_model, model_without_timestamp])
    )
    monkeypatch.setattr("django.apps.apps", fake_apps)
    script = Path(__file__).resolve().parents[2] / "scripts" / "debug_tools" / "count_new_items.py"

    runpy.run_path(str(script), run_name="count_new_items_test")

    matching_manager.filter.assert_called_once_with(inputDateTime__gte="2026-08-22 13:50:00")
    empty_manager.filter.assert_called_once_with(inputDateTime__gte="2026-08-22 13:50:00")
    model_without_timestamp.objects.filter.assert_not_called()
    output = capsys.readouterr().out
    assert "matching_properties: 7" in output
    assert "合計新規取得件数: 7" in output


def test_windows_slack_agent_resolves_an_absolute_command_shell():
    crawler_root = Path(__file__).resolve().parents[2]
    source = (crawler_root / "scripts" / "slack_agent_host.js").read_text(encoding="utf-8")

    assert "process.env.ComSpec" in source
    assert r"C:\Windows\System32\cmd.exe" in source
    assert "spawn(shellCmd" in source


def test_random_parser_verifier_uses_system_random_sampling():
    crawler_root = Path(__file__).resolve().parents[2]
    source = (crawler_root / "scripts" / "debug_tools" / "verify_parsers_random.py").read_text(
        encoding="utf-8"
    )

    assert "secrets.SystemRandom().sample(urls, sample_size)" in source
    assert "random.sample(" not in source
