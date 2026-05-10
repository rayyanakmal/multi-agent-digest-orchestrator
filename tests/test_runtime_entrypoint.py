"""Tests for runtime timeout enforcement in entrypoint."""

import time

from src.runtime.entrypoint import PipelineTimeoutError, _run_with_timeout


class _FastOrchestrator:
    def run_digest_pipeline(self):
        return {"status": "success"}


class _SlowOrchestrator:
    def run_digest_pipeline(self):
        time.sleep(2)
        return {"status": "success"}


def test_run_with_timeout_returns_result_when_under_budget():
    orchestrator = _FastOrchestrator()
    result = _run_with_timeout(orchestrator, timeout_seconds=1)
    assert result["status"] == "success"


def test_run_with_timeout_raises_when_over_budget():
    orchestrator = _SlowOrchestrator()
    try:
        _run_with_timeout(orchestrator, timeout_seconds=1)
        assert False, "Expected PipelineTimeoutError"
    except PipelineTimeoutError as exc:
        assert "digest_pipeline_exceeded_timeout:1s" in str(exc)