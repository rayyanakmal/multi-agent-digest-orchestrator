"""Adapter layer for pluggable LLM providers and external services"""

from src.adapters.llm_service import SummarizerService, LLMAdapter
from src.adapters.provider_registry import get_llm_provider

__all__ = [
    "SummarizerService",
    "LLMAdapter",
    "get_llm_provider",
]
