"""RSS feed fetcher agent"""

import feedparser
import requests
from typing import List
from src.agents.base_agent import BaseAgent
from src.models.contracts import AgentMessage, Article, RunContext
from src.config import get_settings


class RSSFetcher(BaseAgent):
    """Fetches articles from RSS feeds"""

    def __init__(self):
        """Initialize RSS fetcher"""
        super().__init__("rss_fetcher")
        self.settings = get_settings()

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Fetch articles from configured RSS feeds
        
        Args:
            context: Run context
            input_data: Can contain optional 'feeds' override
            
        Returns:
            AgentMessage: Result with articles list or error
        """
        msg = self.create_message(context, "fetch_rss")
        
        feeds = input_data.get("feeds") or self.settings.get_rss_feeds_list()
        
        if not feeds:
            return msg.with_success(
                payload={"articles": [], "source": "rss"},
                metadata={"article_count": 0, "feeds_count": 0}
            )
        
        try:
            articles = self._fetch_from_feeds(feeds)
            context.fetch_count += len(articles)
            
            return msg.with_success(
                payload={"articles": [a.model_dump() for a in articles], "source": "rss"},
                metadata={"article_count": len(articles), "feeds_count": len(feeds)}
            )
        except Exception as e:
            return msg.with_error(f"RSS fetch failed: {str(e)}")

    def _fetch_from_feeds(self, feed_urls: List[str]) -> List[Article]:
        """Fetch articles from multiple RSS feeds
        
        Args:
            feed_urls: List of RSS feed URLs
            
        Returns:
            List[Article]: Normalized article records
        """
        articles = []
        
        for url in feed_urls:
            try:
                response = requests.get(
                    url,
                    timeout=10,
                    headers={"User-Agent": "daily-digest/1.0"},
                )
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                source_name = feed.get("feed", {}).get("title", "RSS Feed")
                
                for entry in feed.get("entries", [])[:15]:  # Limit per feed
                    content_value = None
                    if entry.get("content") and isinstance(entry.get("content"), list):
                        first_content = entry.get("content")[0]
                        if isinstance(first_content, dict):
                            content_value = first_content.get("value")

                    image_url = None
                    media_content = entry.get("media_content")
                    if isinstance(media_content, list) and media_content:
                        first_media = media_content[0]
                        if isinstance(first_media, dict):
                            image_url = first_media.get("url")
                    if not image_url:
                        media_thumbnail = entry.get("media_thumbnail")
                        if isinstance(media_thumbnail, list) and media_thumbnail:
                            first_thumb = media_thumbnail[0]
                            if isinstance(first_thumb, dict):
                                image_url = first_thumb.get("url")
                    if not image_url:
                        image_url = entry.get("image", {}).get("href") if isinstance(entry.get("image"), dict) else None

                    article = Article(
                        url=entry.get("link", ""),
                        title=entry.get("title", ""),
                        description=entry.get("summary", ""),
                        source=source_name,
                        published_at=entry.get("published"),
                        author=entry.get("author"),
                        image_url=image_url,
                        content=content_value,
                        relevance_score=0.7  # Slightly lower for secondary sources
                    )
                    
                    if article.url and article.title:
                        articles.append(article)
            except Exception as feed_error:
                # Skip individual feed failures, continue with others
                pass
        
        return articles
