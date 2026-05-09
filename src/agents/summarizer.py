"""Summarization agent using LangChain and provider-agnostic LLM"""

from typing import List
from src.agents.base_agent import BaseAgent
from src.models.contracts import AgentMessage, Article, SummaryItem, RunContext
from src.adapters.provider_registry import get_summarizer_service
from src.config import get_settings


class SummarizationAgent(BaseAgent):
    """Summarizes articles using configurable LLM provider"""

    def __init__(self):
        """Initialize summarization agent"""
        super().__init__("summarizer")
        self.settings = get_settings()
        self.summarizer_service = None

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Summarize articles using provider-blind LLM service
        
        Args:
            context: Run context
            input_data: Should contain 'articles' list
            
        Returns:
            AgentMessage: Result with summarized articles
        """
        msg = self.create_message(context, "summarize_articles")
        
        if not self.summarizer_service:
            try:
                self.summarizer_service = get_summarizer_service()
            except Exception as e:
                return msg.with_error(f"Failed to initialize LLM service: {str(e)}")
        
        try:
            articles_data = input_data.get("articles", [])
            articles = [Article(**a) for a in articles_data]
            
            summaries = []
            total_cost = 0.0
            
            for article in articles[:self.settings.max_articles]:
                try:
                    # Call provider-blind summarization service
                    response = self.summarizer_service.summarize_article(
                        title=article.title,
                        content=article.description or article.content or article.title,
                        max_length=200
                    )

                    normalized_summary = self._normalize_summary_length(response.summary)
                    strategic_why = response.strategic_why.strip() if response.strategic_why else ""
                    if not strategic_why:
                        strategic_why = (
                            "This matters because it can influence architecture, integration, and"
                            " delivery priorities for developers building AI products in Hong Kong."
                        )
                    
                    summary_item = SummaryItem(
                        url=article.url,
                        title=article.title,
                        summary=normalized_summary,
                        key_points=response.key_points,
                        source=article.source,
                        image_url=article.image_url,
                        category=response.category,
                        strategic_why=strategic_why,
                        confidence=response.confidence,
                    )
                    summaries.append(summary_item)
                    total_cost += response.cost_usd
                    context.tokens_used += response.tokens_used
                    
                    # Check cost budget
                    if context.budget_spent_usd + total_cost > self.settings.cost_limit_usd:
                        break
                        
                except Exception as article_error:
                    # Continue with other articles even if one fails
                    pass
            
            context.summarized_count = len(summaries)
            context.budget_spent_usd += total_cost
            
            return msg.with_success(
                payload={
                    "summaries": [s.model_dump() for s in summaries],
                    "provider": self.summarizer_service.get_provider_name()
                },
                metadata={
                    "summaries_count": len(summaries),
                    "cost_usd": total_cost,
                    "tokens_used": context.tokens_used
                }
            )
        except Exception as e:
            return msg.with_error(f"Summarization failed: {str(e)}")

    def _normalize_summary_length(self, summary: str) -> str:
        """Keep summaries in a readable range close to 70-120 words."""
        words = summary.split()
        if not words:
            return "Summary unavailable due to upstream parsing issues."

        if len(words) > 120:
            return " ".join(words[:120])

        # Keep lower bound soft if model returned concise but useful output.
        if len(words) < 70:
            return summary + " This implies teams should evaluate implementation impact before committing roadmap changes."

        return summary
