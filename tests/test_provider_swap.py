"""Integration test for provider switching"""

import pytest

from src.adapters.llm_service import SummarizerService
from src.adapters.provider_registry import get_summarizer_service
from src.config.settings import reload_settings
from tests.test_llm_adapter import MockLLMAdapter


def test_provider_swap_output_stability():
    """Verify that output format is stable when switching providers"""
    # Initialize with mock adapter
    mock_adapter = MockLLMAdapter()
    service = SummarizerService(mock_adapter)
    
    # Run summarization
    response = service.summarize_article(
        title="AI Breakthrough Article",
        content="New AI model shows promising results...",
        max_length=200
    )
    
    # Verify output structure is stable
    assert isinstance(response.summary, str)
    assert isinstance(response.key_points, list)
    assert isinstance(response.tokens_used, int)
    assert isinstance(response.cost_usd, float)
    
    # Verify response format works consistently
    assert len(response.summary) > 0
    assert all(isinstance(p, str) for p in response.key_points)


class TimeoutLikeAdapter(MockLLMAdapter):
    """Adapter that simulates upstream timeout failures."""

    def summarize_article(self, request):
        raise TimeoutError("simulated provider timeout")


def test_provider_timeout_surfaces_error():
    """Service should surface provider exceptions to caller for agent-level handling."""
    service = SummarizerService(TimeoutLikeAdapter())
    with pytest.raises(TimeoutError):
        service.summarize_article(title="title", content="content", max_length=200)


def test_provider_registry_requires_key(monkeypatch):
    """Registry should fail fast when provider is unsupported."""
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    reload_settings()

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_summarizer_service()
