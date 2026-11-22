from pathlib import Path


def test_live_crawl_guarantee_jobs_have_retry():
    yml = (
        Path(__file__).resolve().parents[4]
        / ".github"
        / "workflows"
        / "test.yml"
    ).read_text(encoding="utf-8")
    assert yml.count("for i in 1 2; do") >= 4
