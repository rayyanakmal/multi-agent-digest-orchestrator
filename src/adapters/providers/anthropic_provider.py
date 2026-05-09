"""Anthropic LLM provider adapter (template for future implementation)"""

from src.adapters.llm_service import LLMAdapter, SummaryRequest, SummaryResponse, DigestCompositionRequest, DigestCompositionResponse


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic (Claude) API - template for future implementation"""

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        """Initialize Anthropic adapter
        
        Args:
            api_key: Anthropic API key
            model: Model name (e.g., 'claude-3-sonnet-20240229')
        """
        self.api_key = api_key
        self.model = model
        # TODO: Implement Anthropic API integration using langchain-anthropic

    def summarize_article(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize an article using Anthropic API"""
        raise NotImplementedError("Anthropic adapter not yet implemented. Use DeepSeek for now.")

    def compose_digest(self, request: DigestCompositionRequest) -> DigestCompositionResponse:
        """Compose a final digest from article summaries using Anthropic API"""
        raise NotImplementedError("Anthropic adapter not yet implemented. Use DeepSeek for now.")

    def get_provider_name(self) -> str:
        """Return provider name"""
        return "anthropic"
