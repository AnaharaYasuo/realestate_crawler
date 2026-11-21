from pathlib import Path


def test_mizuho_bypass_uses_domcontentloaded_instead_of_networkidle():
    src = (
        Path(__file__).resolve().parents[2]
        / "package"
        / "utils"
        / "mizuho_bypass.py"
    ).read_text(encoding="utf-8")
    assert 'wait_until="domcontentloaded"' in src
    assert 'wait_until="networkidle"' not in src
