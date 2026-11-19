from pathlib import Path


def test_daily_pipeline_uses_json_encode_to_string_for_crawler_error():
    yaml_path = Path(__file__).resolve().parents[4] / "terraform" / "workflows" / "daily_pipeline.yaml"
    text = yaml_path.read_text(encoding="utf-8")
    assert "json.encode_to_string(crawlerError)" in text
    assert "+ string(crawlerError)" not in text
