"""Resilience primitives for retry, rate-limit handling, and circuit breaking."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, TypeVar

import requests


logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CircuitBreaker:
    """Simple in-memory circuit breaker with cooldown window."""

    name: str
    failure_threshold: int = 5
    cooldown_seconds: int = 120
    consecutive_failures: int = 0
    opened_until: Optional[datetime] = None

    def is_open(self) -> bool:
        """Return True while the breaker is open."""
        if not self.opened_until:
            return False
        if datetime.utcnow() >= self.opened_until:
            self.opened_until = None
            self.consecutive_failures = 0
            return False
        return True

    def record_success(self):
        """Reset breaker state after a successful request."""
        self.consecutive_failures = 0
        self.opened_until = None

    def record_failure(self):
        """Track a failure and open the breaker after threshold."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_until = datetime.utcnow() + timedelta(seconds=self.cooldown_seconds)
            logger.error(
                "Circuit breaker opened for %s after %s failures; cooling down for %ss",
                self.name,
                self.consecutive_failures,
                self.cooldown_seconds,
            )


def _is_retryable_http_error(exc: Exception) -> bool:
    """Return True for transient request failures that can be retried."""
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True

    if isinstance(exc, requests.HTTPError):
        response = exc.response
        if response is None:
            return True
        return response.status_code == 429 or 500 <= response.status_code < 600

    return False


def _compute_retry_delay(attempt: int, base_delay: float, max_delay: float, jitter: bool) -> float:
    """Compute exponential backoff delay with optional jitter."""
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    if jitter:
        delay *= random.uniform(0.8, 1.2)
    return delay


def request_with_retry(
    fn: Callable[[], T],
    operation: str,
    max_retries: int,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    jitter: bool = True,
    breaker: Optional[CircuitBreaker] = None,
) -> T:
    """Execute a request function with retries and optional circuit breaker."""
    if breaker and breaker.is_open():
        raise RuntimeError(f"circuit_open:{breaker.name}")

    for attempt in range(1, max_retries + 2):
        try:
            result = fn()
            if breaker:
                breaker.record_success()
            return result
        except Exception as exc:  # broad catch to support requests and custom wrappers
            is_retryable = _is_retryable_http_error(exc)
            if breaker:
                breaker.record_failure()

            if attempt > max_retries or not is_retryable:
                raise

            retry_after = None
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                header_value = exc.response.headers.get("Retry-After")
                if header_value and header_value.isdigit():
                    retry_after = float(header_value)

            delay = retry_after or _compute_retry_delay(attempt, base_delay, max_delay, jitter)
            logger.warning(
                "Retrying %s after attempt %s/%s due to %s; sleeping %.2fs",
                operation,
                attempt,
                max_retries + 1,
                type(exc).__name__,
                delay,
            )
            time.sleep(delay)

    raise RuntimeError(f"retry_exhausted:{operation}")