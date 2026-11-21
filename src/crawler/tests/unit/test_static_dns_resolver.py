from package.api.api import DetailFetchCircuitBreaker


def test_detail_fetch_circuit_breaker_opens_on_consecutive_skips():
    cb = DetailFetchCircuitBreaker(threshold=3)
    host = "www.kenbiya.com"
    assert not cb.is_open(host)
    assert not cb.record_skip(host)
    assert not cb.record_skip(host)
    cb.record_success(host)  # resets consecutive count
    assert not cb.record_skip(host)
    assert not cb.record_skip(host)
    assert cb.record_skip(host)  # 3rd consecutive skip opens circuit
    assert cb.is_open(host)


def test_crawl_cooldown_controller_pauses_and_resets():
    from package.api.api import CrawlCooldownController

    ctrl = CrawlCooldownController()
    host = "www.kenbiya.com"
    assert ctrl.get_wait_seconds(host, work_seconds=3600, rest_seconds=900, now=1000.0) == 0.0
    assert ctrl.get_wait_seconds(host, work_seconds=3600, rest_seconds=900, now=4599.0) == 0.0
    # At 3600s elapsed -> enters 900s cooldown
    assert ctrl.get_wait_seconds(host, work_seconds=3600, rest_seconds=900, now=4600.0) == 900.0
    # During cooldown -> remaining seconds
    assert ctrl.get_wait_seconds(host, work_seconds=3600, rest_seconds=900, now=5000.0) == 500.0
    # After cooldown -> resets window
    assert ctrl.get_wait_seconds(host, work_seconds=3600, rest_seconds=900, now=5500.0) == 0.0
