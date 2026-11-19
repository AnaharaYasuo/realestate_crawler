from scripts.ops.run_ttl_expired_recrawl import _BatchRunState


def test_item_error_does_not_trip_circuit_breaker():
    state = _BatchRunState(total=5, started_mono=0.0, stats={}, max_consecutive_failures=3)
    for _ in range(5):
        state.record_outcome("item_error")
    assert state.stats["error"] == 5
    assert state.consecutive_hard_errors == 0
    assert state.circuit_tripped is False
