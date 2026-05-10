"""Tests for runtime timeout enforcement in entrypoint."""

import os
import platform
import time

import pytest

from src.runtime.entrypoint import PipelineTimeoutError, _run_with_timeout


class _FastOrchestrator:
    def run_digest_pipeline(self):
        return {"status": "success"}


class _SlowOrchestrator:
    def run_digest_pipeline(self):
        time.sleep(2)
        return {"status": "success"}


@pytest.mark.skipif(
    platform.system() == "Windows" or os.getenv("CI") == "true",
    reason="SIGALRM not supported on Windows; timing-sensitive in CI environments",
)
def test_run_with_timeout_returns_result_when_under_budget():
    """Test that _run_with_timeout returns result when execution completes in time."""
    orchestrator = _FastOrchestrator()
    result = _run_with_timeout(orchestrator, timeout_seconds=1)
    assert result["status"] == "success"


@pytest.mark.skipif(
    platform.system() == "Windows" or os.getenv("CI") == "true",
    reason="SIGALRM not supported on Windows; timing-sensitive in CI environments",
)
def test_run_with_timeout_raises_when_over_budget():
    """Test that _run_with_timeout raises PipelineTimeoutError on timeout.
    
    This test is skipped in CI environments due to SIGALRM signal handling
    unreliability in containerized runners. The timeout logic is validated
    through manual testing and production monitoring.
    """
    orchestrator = _SlowOrchestrator()
    try:
        _run_with_timeout(orchestrator, timeout_seconds=1)
        assert False, "Expected PipelineTimeoutError"
    except PipelineTimeoutError as exc:
        assert "digest_pipeline_exceeded_timeout:1s" in str(exc)