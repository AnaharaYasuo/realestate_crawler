from pathlib import Path


def test_athome_investment_parser_does_not_skip_missing_yield_or_rent():
    src = (
        Path(__file__).resolve().parents[2]
        / "package"
        / "parser"
        / "athomeParser.py"
    ).read_text(encoding="utf-8")
    assert "Athome investment listing missing yield/rent" not in src


def test_hook_guard_has_single_pr_guard():
    guard_src = (
        Path(__file__).resolve().parents[4]
        / ".agents"
        / "scripts"
        / "hook_guard.py"
    ).read_text(encoding="utf-8")
    assert "Single-PR guard" in guard_src
