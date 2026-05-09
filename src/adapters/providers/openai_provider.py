"""OpenAI LLM provider adapter (template for future implementation)"""

from src.adapters.llm_service import LLMAdapter, SummaryRequest, SummaryResponse, DigestCompositionRequest, DigestCompositionResponse


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI API - template for future implementation"""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo"):
        """Initialize OpenAI adapter
        
        Args:
            api_key: OpenAI API key
            model: Model name (e.g., 'gpt-4-turbo')
        """
        self.api_key = api_key
        self.model = model
        # TODO: Implement OpenAI API integration using langchain-openai

    def summarize_article(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize an article using OpenAI API"""
        raise NotImplementedError("OpenAI adapter not yet implemented. Use DeepSeek for now.")

    def compose_digest(self, request: DigestCompositionRequest) -> DigestCompositionResponse:
        """Compose a final digest from article summaries using OpenAI API"""
        raise NotImplementedError("OpenAI adapter not yet implemented. Use DeepSeek for now.")

    def get_provider_name(self) -> str:
        """Return provider name"""
        return "openai"
