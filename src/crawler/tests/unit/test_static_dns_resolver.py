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
