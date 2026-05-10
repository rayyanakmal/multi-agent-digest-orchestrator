"""News provider fetcher agent supporting NewsAPI.org and NewsData.io"""

import logging
import requests
from typing import List
from src.agents.base_agent import BaseAgent
from src.adapters.resilience import CircuitBreaker, request_with_retry
from src.models.contracts import AgentMessage, Article, RunContext
from src.config import get_settings


logger = logging.getLogger(__name__)


class NewsAPIFetcher(BaseAgent):
    """Fetches articles from configured provider.

    Provider selection is automatic:
    - Keys starting with "pub_" are treated as NewsData.io keys.
    - Other keys are treated as NewsAPI.org keys.
    """

    def __init__(self):
        """Initialize News API fetcher"""
        super().__init__("newsapi_fetcher")
        self.settings = get_settings()
        self._newsapi_breaker = CircuitBreaker(name="newsapi_everything")
        self._newsdata_breaker = CircuitBreaker(name="newsdata_latest")

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Fetch articles from News API
        
        Args:
            context: Run context
            input_data: Should contain 'topic' key
            
        Returns:
            AgentMessage: Result with articles list or error
        """
        msg = self.create_message(context, "fetch_news")
        
        if not self.settings.newsapi_key:
            return msg.with_error("NEWSAPI_KEY not configured")

        topic = input_data.get("topic", self.settings.digest_topic)
        
        try:
            provider = self._detect_provider(self.settings.newsapi_key)
            articles = self._fetch_articles(topic, provider)
            context.fetch_count += len(articles)
            
            return msg.with_success(
                payload={"articles": [a.model_dump() for a in articles], "source": provider},
                metadata={"article_count": len(articles), "provider": provider}
            )
        except Exception as e:
            return msg.with_error(f"News fetch failed: {str(e)}")

    def _fetch_articles(self, topic: str, provider: str) -> List[Article]:
        """Fetch articles from selected provider.
        
        Args:
            topic: Search topic
            provider: Provider name (newsapi | newsdata)
            
        Returns:
            List[Article]: Normalized article records
        """
        if provider == "newsdata":
            return self._fetch_newsdata_articles(topic)
        return self._fetch_newsapi_articles(topic)

    def _detect_provider(self, api_key: str) -> str:
        """Infer provider from key format.

        NewsData.io keys commonly start with "pub_".
        """
        if api_key and api_key.startswith("pub_"):
            return "newsdata"
        return "newsapi"

    def _fetch_newsapi_articles(self, topic: str) -> List[Article]:
        """Fetch articles from NewsAPI.org."""
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": topic,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 30,
            "apiKey": self.settings.newsapi_key
        }
        
        response = request_with_retry(
            fn=lambda: requests.get(url, params=params, timeout=10),
            operation="newsapi.fetch_everything",
            max_retries=self.settings.max_retries,
            breaker=self._newsapi_breaker,
        )
        response.raise_for_status()
        
        data = response.json()
        articles = []
        
        for item in data.get("articles", []):
            article = Article(
                url=item.get("url", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                source=item.get("source", {}).get("name", "NewsAPI"),
                published_at=item.get("publishedAt"),
                author=item.get("author"),
                image_url=item.get("urlToImage"),
                content=item.get("content"),
                relevance_score=0.8  # High by default from primary source
            )
            if article.url and article.title:
                articles.append(article)
        
        return articles

    def _fetch_newsdata_articles(self, topic: str) -> List[Article]:
        """Fetch articles from NewsData.io."""
        url = "https://newsdata.io/api/1/latest"
        params = {
            "apikey": self.settings.newsapi_key,
            "q": topic,
            "language": "en",
        }

        response = request_with_retry(
            fn=lambda: requests.get(url, params=params, timeout=10),
            operation="newsdata.fetch_latest",
            max_retries=self.settings.max_retries,
            breaker=self._newsdata_breaker,
        )
        response.raise_for_status()

        data = response.json()
        status = data.get("status")
        if status and status != "success":
            message = data.get("results", {}).get("message") or data.get("message") or "Unknown NewsData error"
            logger.warning("NewsData returned non-success status for topic '%s': %s", topic, message)
            raise RuntimeError(message)

        articles: List[Article] = []
        for item in data.get("results", []):
            # NewsData can return list[str] for creator/category/country.
            creator = item.get("creator")
            if isinstance(creator, list):
                creator = ", ".join([c for c in creator if c]) or None

            article = Article(
                url=item.get("link", ""),
                title=item.get("title", ""),
                description=item.get("description", "") or item.get("content", ""),
                source=item.get("source_id", "NewsData"),
                published_at=item.get("pubDate"),
                author=creator,
                image_url=item.get("image_url"),
                content=item.get("content"),
                relevance_score=0.8,
            )
            if article.url and article.title:
                articles.append(article)

        return articles
