import datetime
from scripts.ops.run_ttl_expired_recrawl import build_ttl_expired_targets_from_snapshots


def test_build_ttl_expired_targets_excludes_needs_parser_fix_and_needs_recrawl():
    now = datetime.datetime.now(datetime.timezone.utc)
    old_dt = now - datetime.timedelta(days=20)

    eval_rows = [
        # Normal expired item -> should be queued
        {
            "id": 1,
            "property_url": "https://www.example.com/prop/1",
            "company": "tokyu",
            "property_type": "mansion",
            "property_id": 101,
            "is_published": True,
            "last_detail_fetched_at": old_dt,
            "needs_parser_fix": False,
            "needs_recrawl": False,
        },
        # needs_parser_fix item -> should be EXCLUDED
        {
            "id": 2,
            "property_url": "https://www.example.com/prop/2",
            "company": "tokyu",
            "property_type": "mansion",
            "property_id": 102,
            "is_published": True,
            "last_detail_fetched_at": old_dt,
            "needs_parser_fix": True,
            "needs_recrawl": False,
        },
        # needs_recrawl item -> should be EXCLUDED
        {
            "id": 3,
            "property_url": "https://www.example.com/prop/3",
            "company": "tokyu",
            "property_type": "mansion",
            "property_id": 103,
            "is_published": True,
            "last_detail_fetched_at": old_dt,
            "needs_parser_fix": False,
            "needs_recrawl": True,
        },
    ]

    targets = build_ttl_expired_targets_from_snapshots(
        eval_rows=eval_rows,
        model_rows_by_entry=[],
        now=now,
        ttl_days=14,
    )

    assert len(targets) == 1
    assert targets[0].property_url == "https://www.example.com/prop/1"
