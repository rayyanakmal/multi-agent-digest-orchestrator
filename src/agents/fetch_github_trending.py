"""GitHub trending repositories fetcher agent."""

from datetime import datetime, timedelta
from typing import List

import requests

from src.agents.base_agent import BaseAgent
from src.config import get_settings
from src.models.contracts import AgentMessage, Article, RunContext


class GitHubTrendingFetcher(BaseAgent):
    """Fetches top AI-related repositories from GitHub Search API."""

    def __init__(self):
        super().__init__("github_trending_fetcher")
        self.settings = get_settings()

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        msg = self.create_message(context, "fetch_github_trending")

        try:
            # Skip GitHub API calls when token is absent to avoid noisy 401 warnings.
            if not self.settings.github_token:
                return msg.with_success(
                    payload={"articles": [], "source": "github_trending"},
                    metadata={"article_count": 0, "skipped": True, "reason": "missing_github_token"},
                )

            limit = int(input_data.get("limit", 5))
            articles = self._fetch_repositories(limit=max(1, min(limit, 10)))
            context.fetch_count += len(articles)

            return msg.with_success(
                payload={"articles": [a.model_dump() for a in articles], "source": "github_trending"},
                metadata={"article_count": len(articles)},
            )
        except Exception as e:
            return msg.with_error(f"GitHub trending fetch failed: {str(e)}")

    def _fetch_repositories(self, limit: int) -> List[Article]:
        one_day_ago = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        query = f"(topic:ai OR topic:machine-learning OR topic:llm) created:>{one_day_ago}"

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "daily-digest/1.0",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"

        response = requests.get(
            "https://api.github.com/search/repositories",
            params={
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": limit,
            },
            headers=headers,
            timeout=10,
        )
        if response.status_code in (401, 403):
            return []
        response.raise_for_status()

        data = response.json()
        repositories = data.get("items", [])

        normalized: List[Article] = []
        for repo in repositories:
            stars = repo.get("stargazers_count", 0)
            language = repo.get("language") or "Unknown"
            description = repo.get("description") or "No description provided"
            repo_summary = (
                f"{description}. Stars: {stars}. Language: {language}. "
                f"Last pushed: {repo.get('pushed_at', 'unknown')}."
            )
            normalized.append(
                Article(
                    url=repo.get("html_url", ""),
                    title=repo.get("full_name", "Untitled repository"),
                    description=repo_summary,
                    source="GitHub Trending",
                    published_at=repo.get("updated_at"),
                    author=(repo.get("owner") or {}).get("login"),
                    image_url=(repo.get("owner") or {}).get("avatar_url"),
                    content=repo_summary,
                    relevance_score=0.9,
                )
            )

        return [article for article in normalized if article.url and article.title]
