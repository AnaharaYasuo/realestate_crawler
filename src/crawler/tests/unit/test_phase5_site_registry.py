"""Unit tests for Phase 5: Unified SiteRegistry & 10-Point Wiring Verification (Issue #1151)."""
import subprocess
import sys
from pathlib import Path

import setup_env  # noqa: F401
from package.site_registry import SiteDefinition, SiteRegistry, verify_all_registered_sites


class TestPhase5SiteRegistry:
    def test_verify_all_registered_sites_has_zero_missing_wiring(self):
        """All 30 companies and 104 crawl jobs must be wired across parser, model, dispatch, router, task dist, and ML."""
        report = verify_all_registered_sites()
        assert report["missing"] == [], f"Unexpected site wiring gaps: {report['missing']}"
        assert report["total_sites"] >= 30
        assert report["total_jobs"] >= 104

    def test_register_site_dynamically_adds_custom_site(self):
        """SiteRegistry.register_site allows dynamic registration and surfaces missing files if un-scaffolded."""
        dummy = SiteDefinition(
            company="dummy_broker_xyz",
            property_types=("mansion",),
            parser_module="package.parser.dummy_broker_xyzParser",
            model_module="package.models.dummy_broker_xyz",
        )
        try:
            SiteRegistry.register_site(dummy)
            sites = SiteRegistry.get_all_sites()
            assert "dummy_broker_xyz" in sites
            report = verify_all_registered_sites()
            assert any("dummy_broker_xyz" in msg for msg in report["missing"])
        finally:
            SiteRegistry._custom_sites.pop("dummy_broker_xyz", None)

    def test_verify_site_wiring_cli_script_exits_zero(self):
        """The /onboard-new-site skill's verify_site_wiring.py script must exit with code 0."""
        repo_root = Path(__file__).resolve().parents[4]
        script = repo_root / ".agents" / "skills" / "onboard-new-site" / "scripts" / "verify_site_wiring.py"
        assert script.exists()
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, f"verify_site_wiring.py failed: {proc.stdout}\n{proc.stderr}"
        assert "ALL SITES WIRED CLEANLY" in proc.stdout
