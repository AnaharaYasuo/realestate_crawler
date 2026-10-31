"""Automated Architectural Fitness Functions (Layer 3 Governance Harness - Issue #1151 & #1160).

Continuously enforces the project-wide quality and architecture gates:
  - Gate 1: Documentation SSOT & Antigravity Customization Integrity (0 duplicate .md filenames in docs/)
  - Gate 2: Core Model & Parser Reference Compliance (InvestmentBaseModel, blank=True schema invariant, single-save detail lifecycle)
  - Gate 3: Unified SiteRegistry 10-Point Wiring Completeness (all companies & crawl jobs wired)
  - Gate 4: Property-Type 0% Misclassification & ML Valuation Invariants (4-layer defense, GroupKFold, P10 interval)
  - Gate 5: Strict AST Import & Layer Boundaries
"""
from collections import Counter
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from django.apps import apps
import numpy as np

import setup_env  # noqa: F401
from package.api.api import ApiAsyncProcBase, ParseDetailPageAsyncBase
from package.ml.inference.ensemble import (
    compute_prediction_interval_p10,
    compute_risk_adjusted_bargain_score,
)
from package.ml.training.pipeline import DEFAULT_MAX_TRAINING_ITEMS
from package.models.base import InvestmentBaseModel, PropertyBaseModel
from package.parser import sumifuParser
from package.parser.investmentParser import InvestmentParser
from package.site_registry import verify_all_registered_sites
from package.utils.property_type_detector import PropertyTypeDetector


REPO_ROOT = Path(__file__).resolve().parents[4]

OPTIONAL_SPEC_TEXT_FIELDS = frozenset({
    "syuzenTsumitateStr",
    "kanrihiStr",
    "tochikenri",
    "kenpeiStr",
    "yousekiStr",
    "kenpeiYousekiStr",
    "setsudou",
    "setsumenStr",
    "douroHabaStr",
    "balconyMensekiStr",
    "kaisuStr",
    "kasitampokikan",
    "hikiwatashi",
    "genkyo",
    "biko",
    "chushajo",
    "youtoChiiki",
    "chimoku",
    "chisei",
    "toshiKeikaku",
})


class _DummyInvestmentParser(InvestmentParser):
    def createEntity(self):
        return None


class _DummyDetailApi(ParseDetailPageAsyncBase):
    def _generateParser(self):
        return MagicMock()

    def _getLocalPararellLimit(self):
        return 1

    def _getCloudPararellLimit(self):
        return 1

    def _getTimeOutSecond(self):
        return 10

    def _getApiKey(self):
        return ""


class TestArchitectureHarness:
    def test_gate1_documentation_ssot_and_antigravity_harness_files(self):
        """Gate 1: Zero duplicate markdown filenames in docs/ and required Antigravity harness files exist."""
        docs_dir = REPO_ROOT / "docs"
        md_files = [p.name for p in docs_dir.rglob("*.md")]
        counts = Counter(md_files)
        duplicates = {name: cnt for name, cnt in counts.items() if cnt > 1}
        assert duplicates == {}, f"Duplicate markdown filenames found in docs/: {duplicates}"

        required_files = [
            REPO_ROOT / ".agents" / "AGENTS.md",
            REPO_ROOT / ".agents" / "hooks.json",
            REPO_ROOT / ".agents" / "scripts" / "hook_guard.py",
            REPO_ROOT / ".agents" / "skills" / "onboard-new-site" / "SKILL.md",
            REPO_ROOT / "docs" / "AGENTS.md",
            REPO_ROOT / "src" / "crawler" / "package" / "models" / "AGENTS.md",
            REPO_ROOT / "src" / "crawler" / "package" / "parser" / "AGENTS.md",
            REPO_ROOT / "src" / "crawler" / "package" / "ml" / "AGENTS.md",
        ]
        for req in required_files:
            assert req.exists(), f"Required governance harness file missing: {req}"

    def test_gate2_model_and_parser_reference_compliance(self):
        """Gate 2: InvestmentBaseModel is abstract, decimal 億円 parses without 10x inflation, no sys reload."""
        assert InvestmentBaseModel._meta.abstract is True
        p = _DummyInvestmentParser()
        assert p._parse_price("1.5億円") == 150_000_000

        sumifu_src = inspect.getsource(sumifuParser)
        assert "importlib.reload(sys)" not in sumifu_src
        assert "Chrome/74." not in ApiAsyncProcBase.USER_AGENT

    def test_gate2_concrete_models_blank_true_and_detail_single_save(self):
        """Gate 2 (Issue #1160): All concrete property models allow blank=True on nullable/optional fields, and ParseDetailPageAsyncBase does not double-save in _afterRunProc."""
        schema_violations: list[str] = []
        strict_legacy_models = {"MitsuiInvestmentKodate"}
        strict_legacy_fields = {("TokyuTochi", "chimoku")}
        for model in apps.get_models():
            if not issubclass(model, PropertyBaseModel) or model._meta.abstract or model.__name__ in strict_legacy_models:
                continue
            for field in model._meta.local_fields:
                if getattr(field, "primary_key", False) or (model.__name__, field.name) in strict_legacy_fields:
                    continue
                if getattr(field, "null", False) and not getattr(field, "blank", False):
                    schema_violations.append(f"{model.__name__}.{field.name} has null=True without blank=True")
                elif field.name in OPTIONAL_SPEC_TEXT_FIELDS and not getattr(field, "blank", False):
                    schema_violations.append(f"{model.__name__}.{field.name} is an optional spec field without blank=True")

        assert schema_violations == [], "Model schema blank=True violations:\n" + "\n".join(schema_violations)

        detail_api = _DummyDetailApi()
        mock_item = MagicMock()
        detail_api._save_item_with_retry = MagicMock()
        with patch("package.api.api.close_old_connections"):
            detail_api._afterRunProc([mock_item])
        detail_api._save_item_with_retry.assert_not_called()

    def test_gate3_unified_site_registry_completeness(self):
        """Gate 3: All registered sites and crawl jobs pass 10-point wiring verification."""
        report = verify_all_registered_sites()
        assert report["missing"] == [], f"SiteRegistry wiring errors: {report['missing']}"
        assert report["total_sites"] >= 30
        assert report["total_jobs"] >= 104

    def test_gate4_property_type_defense_and_ml_invariants(self):
        """Gate 4: 4-Layer PropertyTypeDetector defense and ML P10 / 50k cap invariants hold."""
        soup = BeautifulSoup(
            "<html><body><nav>マンション 戸建て 土地</nav><main><h1>売地 120㎡</h1></main></body></html>",
            "html.parser",
        )
        clean_text = PropertyTypeDetector.extract_clean_body_text(soup)
        assert "マンション" not in clean_text

        ok, actual_type, reason = PropertyTypeDetector.validate_physical_invariants(
            {"price": 50000000, "tochiMenseki": None, "senyuMenseki": 65.0, "kaisuStr": "5階"},
            "tochi",
        )
        assert ok is False and actual_type == "mansion" and bool(reason)

        assert DEFAULT_MAX_TRAINING_ITEMS >= 50000
        pts, p10s = compute_prediction_interval_p10(
            {"lgb": np.array([np.log1p(100.0)]), "xgb": np.array([np.log1p(110.0)])},
            {"lgb": 0.5, "xgb": 0.5},
            1.0,
            np.array([60.0]),
        )
        assert p10s[0] < pts[0]
        score = compute_risk_adjusted_bargain_score(4500.0, float(pts[0]), float(p10s[0]))
        assert 0.0 < score <= 1.0

    def test_gate5_architectural_import_and_layer_boundaries(self):
        """Gate 5: Strict AST import dependency rules preventing layer inversion and cycles."""
        import ast

        package_root = REPO_ROOT / "src" / "crawler" / "package"
        models_dir = package_root / "models"
        ml_dir = package_root / "ml"

        violations: list[str] = []

        forbidden_in_models = {"package.parser", "package.api", "package.ml"}
        for py_path in models_dir.rglob("*.py"):
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name == f or alias.name.startswith(f + ".") for f in forbidden_in_models):
                            violations.append(f"{py_path.name} imports forbidden module: {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module and any(node.module == f or node.module.startswith(f + ".") for f in forbidden_in_models):
                    violations.append(f"{py_path.name} imports from forbidden module: {node.module}")

        forbidden_in_ml = {"package.parser", "package.api"}
        for py_path in ml_dir.rglob("*.py"):
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(alias.name == f or alias.name.startswith(f + ".") for f in forbidden_in_ml):
                            violations.append(f"{py_path.name} imports forbidden module: {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module and any(node.module == f or node.module.startswith(f + ".") for f in forbidden_in_ml):
                    violations.append(f"{py_path.name} imports from forbidden module: {node.module}")

        assert violations == [], "Architectural layer import boundary violations found:\n" + "\n".join(violations)
