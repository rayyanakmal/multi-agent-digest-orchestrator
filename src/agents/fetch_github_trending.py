"""GitHub trending repositories fetcher agent."""

from datetime import datetime, timedelta
from typing import List
import logging

import requests

from src.agents.base_agent import BaseAgent
from src.adapters.resilience import CircuitBreaker, request_with_retry
from src.config import get_settings
from src.models.contracts import AgentMessage, Article, RunContext


logger = logging.getLogger(__name__)


class GitHubTrendingFetcher(BaseAgent):
    """Fetches top AI-related repositories from GitHub Search API."""

    def __init__(self):
        super().__init__("github_trending_fetcher")
        self.settings = get_settings()
        self._breaker = CircuitBreaker(name="github_search_api")

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        msg = self.create_message(context, "fetch_github_trending")

        try:
            limit = int(input_data.get("limit", 5))
            articles = self._fetch_repositories(limit=max(1, min(limit, 10)))
            context.fetch_count += len(articles)

            return msg.with_success(
                payload={"articles": [a.model_dump() for a in articles], "source": "github_trending"},
                metadata={
                    "article_count": len(articles),
                    "auth_mode": "token" if self.settings.github_token else "unauthenticated",
                },
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
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        }

        response = request_with_retry(
            fn=lambda: self._search_repositories(params=params, headers=headers),
            operation="github.search_repositories",
            max_retries=self.settings.max_retries,
            breaker=self._breaker,
        )

        # Invalid/expired token is common in long-running deployments.
        # Retry unauthenticated once so GitHub trending still contributes data.
        if response.status_code == 401 and self.settings.github_token:
            logger.warning("GitHub token rejected with 401; retrying GitHub trending fetch without token")
            response = request_with_retry(
                fn=lambda: self._search_repositories(params=params, headers=headers, include_auth=False),
                operation="github.search_repositories_unauthenticated",
                max_retries=self.settings.max_retries,
                breaker=self._breaker,
            )

        if response.status_code == 403:
            logger.warning("GitHub API returned 403; skipping GitHub trending for this run")
            return []

        if response.status_code == 401:
            logger.warning("GitHub API returned 401 without usable fallback; skipping GitHub trending for this run")
            return []

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

    def _search_repositories(self, params: dict, headers: dict, include_auth: bool = True) -> requests.Response:
        """Perform a GitHub search request with optional Authorization header."""
        request_headers = dict(headers)
        if include_auth and self.settings.github_token:
            request_headers["Authorization"] = f"Bearer {self.settings.github_token}"

        response = requests.get(
            "https://api.github.com/search/repositories",
            params=params,
            headers=request_headers,
            timeout=10,
        )
        # Keep explicit handling in caller for authentication and quota responses.
        if response.status_code not in (401, 403):
            response.raise_for_status()
        return response
