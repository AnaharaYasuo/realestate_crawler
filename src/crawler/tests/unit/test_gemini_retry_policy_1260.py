"""Issue #1260: Gemini API リトライ方針（エラーコード別）と推奨モデル既定値"""
import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from package.ml import report_generator as rg


def _http_error(code: int, headers: dict | None = None) -> urllib.error.HTTPError:
    msg = MagicMock()
    msg.get = lambda k, d=None: (headers or {}).get(k, d)
    return urllib.error.HTTPError("http://x", code, f"err{code}", msg, io.BytesIO(b""))


def _ok_response(payload: dict | None = None):
    body = {"candidates": [{"content": {"parts": [{"text": json.dumps(payload or {"investment_rating": "A"})}]}}]}
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    return resp


def _bad_response():
    body = {"candidates": [{"content": {"parts": [{"text": "not json at all"}]}}]}
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode("utf-8")
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    return resp


def test_default_recommend_model_is_gemini_3_5_flash(monkeypatch):
    monkeypatch.delenv("GEMINI_RECOMMEND_MODEL", raising=False)
    assert rg.DEFAULT_RECOMMEND_MODEL == "gemini-3.5-flash"


def test_model_wait_factor_increases_with_model_tier():
    assert rg._model_wait_factor("gemini-3.5-flash-lite") < rg._model_wait_factor("gemini-3.5-flash")
    assert rg._model_wait_factor("gemini-3.5-flash") < rg._model_wait_factor("gemini-3.5-pro")


@pytest.mark.parametrize("code,expected", [
    (429, "rate_limit"), (500, "transient"), (502, "transient"), (503, "transient"), (504, "transient"),
    (400, "fatal"), (401, "fatal"), (402, "fatal"), (403, "fatal"), (404, "fatal"),
])
def test_classify_http_codes(code, expected):
    kind, _ = rg._classify_gemini_error(_http_error(code))
    assert kind == expected


def test_classify_timeout_is_transient_and_bad_json_is_parse():
    assert rg._classify_gemini_error(TimeoutError("The read operation timed out"))[0] == "transient"
    assert rg._classify_gemini_error(ValueError("bad json"))[0] == "parse"


def test_classify_reads_retry_after_header():
    _, retry_after = rg._classify_gemini_error(_http_error(429, {"Retry-After": "42"}))
    assert retry_after == 42.0


def test_rate_limit_wait_longer_for_higher_tier_and_longer_than_transient():
    no_jitter = lambda: 0.5  # noqa: E731
    lite = rg._compute_retry_wait_sec("rate_limit", "gemini-3.5-flash-lite", 0, rng=no_jitter)
    flash = rg._compute_retry_wait_sec("rate_limit", "gemini-3.5-flash", 0, rng=no_jitter)
    pro = rg._compute_retry_wait_sec("rate_limit", "gemini-3.5-pro", 0, rng=no_jitter)
    transient = rg._compute_retry_wait_sec("transient", "gemini-3.5-flash", 0, rng=no_jitter)
    assert lite < flash < pro
    assert flash > transient


def test_wait_grows_exponentially_and_is_capped():
    no_jitter = lambda: 0.5  # noqa: E731
    w0 = rg._compute_retry_wait_sec("transient", "gemini-3.5-flash", 0, rng=no_jitter)
    w1 = rg._compute_retry_wait_sec("transient", "gemini-3.5-flash", 1, rng=no_jitter)
    assert w1 == pytest.approx(w0 * 2)
    assert rg._compute_retry_wait_sec("rate_limit", "gemini-3.5-pro", 10, rng=no_jitter) <= rg.MAX_WAIT_SEC


def test_retry_after_is_honored_and_capped():
    assert rg._compute_retry_wait_sec("rate_limit", "gemini-3.5-flash", 0, retry_after=30.0) == 30.0
    assert rg._compute_retry_wait_sec("rate_limit", "gemini-3.5-flash", 0, retry_after=9999.0) == rg.MAX_WAIT_SEC


def test_call_retries_429_then_succeeds_with_long_wait():
    with patch.object(rg.urllib.request, "urlopen", side_effect=[_http_error(429), _ok_response()]) as uo, \
            patch.object(rg.time, "sleep") as sleep:
        result = rg._call_gemini_api("gemini-3.5-flash", "k", "p")
    assert result == {"investment_rating": "A"}
    assert uo.call_count == 2
    assert sleep.call_args[0][0] >= 10  # 429 は長め


def test_call_gives_up_after_max_rate_limit_retries():
    errs = [_http_error(429)] * (rg.MAX_RETRIES_RATE_LIMIT + 1)
    with patch.object(rg.urllib.request, "urlopen", side_effect=errs) as uo, patch.object(rg.time, "sleep"):
        assert rg._call_gemini_api("gemini-3.5-flash", "k", "p") is None
    assert uo.call_count == rg.MAX_RETRIES_RATE_LIMIT + 1


def test_call_retries_503_and_timeout_with_backoff():
    side = [_http_error(503), TimeoutError("The read operation timed out"), _ok_response()]
    with patch.object(rg.urllib.request, "urlopen", side_effect=side), patch.object(rg.time, "sleep") as sleep:
        assert rg._call_gemini_api("gemini-3.5-flash", "k", "p") is not None
    waits = [c[0][0] for c in sleep.call_args_list]
    assert len(waits) == 2
    assert waits[1] > waits[0] * 1.2  # 指数的に増加（ジッター考慮）


@pytest.mark.parametrize("code", [400, 401, 402, 403, 404])
def test_call_does_not_retry_fatal_errors(code):
    with patch.object(rg.urllib.request, "urlopen", side_effect=[_http_error(code)]) as uo, \
            patch.object(rg.time, "sleep") as sleep:
        assert rg._call_gemini_api("gemini-3.5-flash", "k", "p") is None
    assert uo.call_count == 1
    sleep.assert_not_called()


def test_call_retries_unparseable_response_once_only():
    with patch.object(rg.urllib.request, "urlopen", side_effect=[_bad_response(), _bad_response(), _ok_response()]) as uo, \
            patch.object(rg.time, "sleep"):
        assert rg._call_gemini_api("gemini-3.5-flash", "k", "p") is None
    assert uo.call_count == 2
