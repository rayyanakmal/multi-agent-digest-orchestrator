"""Tests for retry and circuit-breaker resilience helpers."""

import requests

from src.adapters.resilience import CircuitBreaker, request_with_retry


def test_request_with_retry_succeeds_after_transient_timeout():
    """Transient timeout should be retried and eventually succeed."""
    attempts = {"count": 0}

    def flaky_call():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise requests.Timeout("simulated timeout")
        return "ok"

    result = request_with_retry(
        fn=flaky_call,
        operation="test.flaky_call",
        max_retries=2,
        base_delay=0.01,
        max_delay=0.02,
        jitter=False,
    )

    assert result == "ok"
    assert attempts["count"] == 2


def test_request_with_retry_does_not_retry_non_retryable_error():
    """Client-side 400 responses should not be retried."""

    class DummyResponse:
        status_code = 400
        headers = {}

    attempts = {"count": 0}

    def bad_request():
        attempts["count"] += 1
        raise requests.HTTPError("bad request", response=DummyResponse())

    try:
        request_with_retry(
            fn=bad_request,
            operation="test.bad_request",
            max_retries=3,
            base_delay=0.01,
            max_delay=0.02,
            jitter=False,
        )
        assert False, "Expected HTTPError for non-retryable status"
    except requests.HTTPError:
        pass

    assert attempts["count"] == 1


def test_circuit_breaker_opens_after_threshold_failures():
    """Circuit breaker should open and short-circuit calls after repeated failures."""
    breaker = CircuitBreaker(name="test-breaker", failure_threshold=2, cooldown_seconds=30)
    attempts = {"count": 0}

    def always_fails():
        attempts["count"] += 1
        raise requests.Timeout("always failing")

    for _ in range(2):
        try:
            request_with_retry(
                fn=always_fails,
                operation="test.always_fails",
                max_retries=0,
                base_delay=0.01,
                max_delay=0.02,
                jitter=False,
                breaker=breaker,
            )
        except requests.Timeout:
            pass

    assert breaker.is_open()

    try:
        request_with_retry(
            fn=always_fails,
            operation="test.short_circuit",
            max_retries=0,
            base_delay=0.01,
            max_delay=0.02,
            jitter=False,
            breaker=breaker,
        )
        assert False, "Expected RuntimeError when circuit is open"
    except RuntimeError as exc:
        assert "circuit_open:test-breaker" in str(exc)

    assert attempts["count"] == 2