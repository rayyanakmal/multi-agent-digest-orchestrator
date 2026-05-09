"""Registry and factory for LLM provider adapters"""

from typing import Optional
from src.adapters.llm_service import LLMAdapter, SummarizerService
from src.config import get_settings


def get_llm_provider() -> LLMAdapter:
    """Get the configured LLM adapter based on settings
    
    Returns:
        LLMAdapter: The initialized adapter for the configured provider
        
    Raises:
        ValueError: If provider is not recognized or credentials are missing
    """
    settings = get_settings()
    provider_name = settings.llm_provider.lower()

    if provider_name == "deepseek":
        from src.adapters.providers.deepseek_provider import DeepSeekAdapter
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is required but not set")
        return DeepSeekAdapter(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.llm_model
        )
    elif provider_name == "openai":
        from src.adapters.providers.openai_provider import OpenAIAdapter
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required but not set")
        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.llm_model
        )
    elif provider_name == "anthropic":
        from src.adapters.providers.anthropic_provider import AnthropicAdapter
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required but not set")
        return AnthropicAdapter(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")


def get_summarizer_service() -> SummarizerService:
    """Create and return a SummarizerService with the configured provider adapter"""
    adapter = get_llm_provider()
    return SummarizerService(adapter)
