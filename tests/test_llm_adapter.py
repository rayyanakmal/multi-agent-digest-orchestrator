"""Test utilities for provider-swap validation"""

import pytest
from src.adapters.llm_service import LLMAdapter, SummaryRequest, SummaryResponse


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter for testing provider-agnostic behavior"""

    def summarize_article(self, request: SummaryRequest) -> SummaryResponse:
        """Return a mock summary"""
        return SummaryResponse(
            summary="Mock summary of the article.",
            key_points=["Key point 1", "Key point 2"],
            tokens_used=100,
            cost_usd=0.001
        )

    def compose_digest(self, request) -> dict:
        """Return a mock digest"""
        return {
            "takeaways": ["Takeaway 1", "Takeaway 2"],
            "watchlist": "Watch for policy changes",
            "tokens_used": 200,
            "cost_usd": 0.002
        }

    def get_provider_name(self) -> str:
        """Return mock provider name"""
        return "mock"


def test_llm_interface_stability():
    """Test that LLM interface remains stable across adapters"""
    from src.adapters.llm_service import SummarizerService
    
    # Create service with mock adapter
    mock_adapter = MockLLMAdapter()
    service = SummarizerService(mock_adapter)
    
    # Call summarize
    response = service.summarize_article(
        title="Test Article",
        content="Test content here",
        max_length=200
    )
    
    assert response.summary is not None
    assert response.tokens_used > 0
    assert response.cost_usd >= 0
    assert len(response.key_points) > 0
    assert service.get_total_cost() > 0
    assert service.get_total_tokens() > 0
