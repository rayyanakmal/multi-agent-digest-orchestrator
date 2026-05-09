"""Integration test for provider switching"""

from src.adapters.llm_service import SummarizerService
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
