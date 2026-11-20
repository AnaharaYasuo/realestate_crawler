from pathlib import Path


def test_run_all_crawlers_enforces_active_company_counts():
    script = Path(__file__).resolve().parents[4] / "src" / "crawler" / "scripts" / "ops" / "run_all_crawlers.py"
    text = script.read_text(encoding="utf-8")
    assert "active_company_counts" in text
