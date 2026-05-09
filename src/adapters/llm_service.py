"""Abstract LLM interface and base adapter for provider-blind agents"""

from abc import ABC, abstractmethod
from typing import Optional, Any
from pydantic import BaseModel


class SummaryRequest(BaseModel):
    """Request to summarize an article"""
    
    title: str
    content: str
    max_length: int = 200


class SummaryResponse(BaseModel):
    """Response with summarized article"""
    
    summary: str
    key_points: list[str]
    strategic_why: str = "This matters because it affects implementation choices for engineers shipping AI products in Hong Kong."
    category: str = "general"
    confidence: float = 0.7
    tokens_used: int
    cost_usd: float


class DigestCompositionRequest(BaseModel):
    """Request to compose a final digest"""
    
    summaries: list[SummaryResponse]
    topic: str
    article_count: int


class DigestCompositionResponse(BaseModel):
    """Response with composed digest"""
    
    takeaways: list[str]
    watchlist: str
    tokens_used: int
    cost_usd: float


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters"""

    @abstractmethod
    def summarize_article(self, request: SummaryRequest) -> SummaryResponse:
        """Summarize a single article. Must be implemented by each provider."""
        pass

    @abstractmethod
    def compose_digest(self, request: DigestCompositionRequest) -> DigestCompositionResponse:
        """Compose final digest from summaries. Must be implemented by each provider."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'deepseek', 'openai')"""
        pass


class SummarizerService:
    """Provider-blind summarizer service that agents call.
    
    This service encapsulates the LLM adapter and presents a single interface
    to all agents. Switching providers only requires changing the adapter,
    not touching any agent code.
    """

    def __init__(self, adapter: LLMAdapter):
        """Initialize with a specific LLM adapter"""
        self._adapter = adapter
        self._total_cost = 0.0
        self._total_tokens = 0

    def summarize_article(self, title: str, content: str, max_length: int = 200) -> SummaryResponse:
        """Summarize an article using the configured LLM provider"""
        request = SummaryRequest(
            title=title,
            content=content,
            max_length=max_length
        )
        response = self._adapter.summarize_article(request)
        self._total_cost += response.cost_usd
        self._total_tokens += response.tokens_used
        return response

    def compose_digest(self, summaries: list[SummaryResponse], topic: str) -> DigestCompositionResponse:
        """Compose final digest from summarized articles using the configured LLM provider"""
        request = DigestCompositionRequest(
            summaries=summaries,
            topic=topic,
            article_count=len(summaries)
        )
        response = self._adapter.compose_digest(request)
        self._total_cost += response.cost_usd
        self._total_tokens += response.tokens_used
        return response

    def get_provider_name(self) -> str:
        """Get the name of the currently configured provider"""
        return self._adapter.get_provider_name()

    def get_total_cost(self) -> float:
        """Get cumulative LLM cost for this service instance"""
        return self._total_cost

    def get_total_tokens(self) -> int:
        """Get cumulative tokens used by this service instance"""
        return self._total_tokens

    def reset_counters(self):
        """Reset cost and token counters (e.g., for next run)"""
        self._total_cost = 0.0
        self._total_tokens = 0
