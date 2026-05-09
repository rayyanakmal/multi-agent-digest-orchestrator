"""Typed contracts for agent communication and run artifacts"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Literal
from pydantic import BaseModel, Field


class Article(BaseModel):
    """Normalized article record from any news source"""
    
    url: str = Field(..., description="Canonical URL of the article")
    title: str = Field(..., description="Article headline")
    description: str = Field(..., description="Article summary or excerpt")
    source: str = Field(..., description="News source name (e.g., 'NewsAPI', 'TechCrunch')")
    published_at: Optional[str] = Field(default=None, description="ISO 8601 publication timestamp")
    author: Optional[str] = Field(default=None, description="Article author")
    image_url: Optional[str] = Field(default=None, description="Featured image URL")
    content: Optional[str] = Field(default=None, description="Full article content (if available)")
    relevance_score: float = Field(default=0.5, description="Relevance to topic (0-1)")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article",
                "title": "AI Breakthrough",
                "description": "New AI model shows promise",
                "source": "NewsAPI",
                "published_at": "2026-05-09T10:00:00Z",
                "relevance_score": 0.9
            }
        }


class SummaryItem(BaseModel):
    """Summary of a single article"""
    
    url: str = Field(..., description="Original article URL")
    title: str = Field(..., description="Article title")
    summary: str = Field(..., description="1-2 sentence LLM summary")
    key_points: list[str] = Field(default_factory=list, description="Bullet-point takeaways")
    source: str = Field(..., description="Article source")
    image_url: Optional[str] = Field(default=None, description="Optional article image for visual cards")
    category: str = Field(default="general", description="Content category for page routing")
    strategic_why: str = Field(
        default="This matters because it affects implementation choices for engineers shipping AI products in Hong Kong.",
        description="Why this matters for a developer in HK"
    )
    confidence: float = Field(default=0.7, description="Confidence score for summary quality (0-1)")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article",
                "title": "AI Breakthrough",
                "summary": "Researchers unveiled a new model that outperforms previous benchmarks.",
                "key_points": ["50% improvement on benchmarks", "Open source availability"],
                "source": "NewsAPI"
            }
        }


class DigestOutput(BaseModel):
    """Final digest artifact for publication"""
    
    title: str = Field(..., description="Digest title (e.g., 'Daily AI and Technology Digest - 2026-05-09')")
    date: str = Field(..., description="ISO 8601 date of digest")
    top_takeaways: list[str] = Field(default_factory=list, description="Top 3-5 key insights")
    article_summaries: list[SummaryItem] = Field(..., description="List of summarized articles")
    watchlist: Optional[str] = Field(default=None, description="Risk/watchlist section")
    metadata: dict = Field(default_factory=dict, description="Run statistics: source_count, deduplicated_count, run_time_sec, cost_usd")
    layout_pages: list[dict] = Field(default_factory=list, description="Structured 5-page report layout")
    executive_snapshot: list[str] = Field(default_factory=list, description="Top-level daily executive snapshot bullets")

    class Config:
        """Pydantic config"""
        json_schema_extra = {
            "example": {
                "title": "Daily AI and Technology Digest - 2026-05-09",
                "date": "2026-05-09",
                "top_takeaways": ["AI model achieves new benchmark"],
                "article_summaries": [],
                "metadata": {"source_count": 25, "deduplicated_count": 15}
            }
        }


class RunStatus(str, Enum):
    """Status of a digest run"""
    
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"  # Completed but with fallbacks (e.g., Drive upload failed, local saved)
    FAILED = "failed"
    TIMEOUT = "timeout"


class RunContext(BaseModel):
    """Context for a single digest run"""
    
    run_id: str = Field(..., description="Unique run identifier (e.g., 'digest-2026-05-09-123abc')")
    start_time: datetime = Field(default_factory=datetime.utcnow, description="Run start timestamp")
    end_time: Optional[datetime] = Field(default=None, description="Run end timestamp")
    status: RunStatus = Field(default=RunStatus.PENDING, description="Current run status")
    step_counter: int = Field(default=0, description="Sequential step counter")
    budget_spent_usd: float = Field(default=0.0, description="LLM cost incurred so far")
    tokens_used: int = Field(default=0, description="Total tokens used in run")
    errors: list[str] = Field(default_factory=list, description="Collected error messages")
    fetch_count: int = Field(default=0, description="Articles fetched from sources")
    deduplicated_count: int = Field(default=0, description="Articles after deduplication")
    summarized_count: int = Field(default=0, description="Articles successfully summarized")
    retry_history: dict = Field(default_factory=dict, description="Retries per agent")

    class Config:
        """Pydantic config"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentMessage(BaseModel):
    """Envelope for inter-agent communication"""
    
    run_id: str = Field(..., description="Run identifier for tracing")
    step_id: int = Field(..., description="Sequential step counter")
    actor: str = Field(..., description="Agent name (e.g., 'fetcher', 'summarizer')")
    intent: str = Field(..., description="Operation (e.g., 'fetch_news', 'deduplicate')")
    payload: dict = Field(..., description="Tool input/output data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    status: Literal["pending", "success", "error"] = Field(default="pending", description="Status")
    error: Optional[str] = Field(default=None, description="Error message if status == error")
    metadata: dict = Field(default_factory=dict, description="Additional context (retry_count, budget_used, etc.)")

    class Config:
        """Pydantic config"""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def with_success(self, payload: dict, metadata: dict = None) -> "AgentMessage":
        """Create a success variant of this message"""
        return AgentMessage(
            run_id=self.run_id,
            step_id=self.step_id,
            actor=self.actor,
            intent=self.intent,
            payload=payload,
            timestamp=datetime.utcnow(),
            status="success",
            metadata=metadata or {}
        )

    def with_error(self, error: str, metadata: dict = None) -> "AgentMessage":
        """Create an error variant of this message"""
        return AgentMessage(
            run_id=self.run_id,
            step_id=self.step_id,
            actor=self.actor,
            intent=self.intent,
            payload={},
            timestamp=datetime.utcnow(),
            status="error",
            error=error,
            metadata=metadata or {}
        )
