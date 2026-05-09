"""Agent scaffolds and initialization"""

from src.agents.base_agent import BaseAgent
from src.agents.fetch_newsapi import NewsAPIFetcher
from src.agents.fetch_rss import RSSFetcher
from src.agents.fetch_github_trending import GitHubTrendingFetcher

__all__ = [
    "BaseAgent",
    "NewsAPIFetcher",
    "RSSFetcher",
    "GitHubTrendingFetcher",
]
