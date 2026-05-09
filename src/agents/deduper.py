"""Deduplication and ranking agent"""

import hashlib
from typing import List, Dict, Set
from urllib.parse import urlparse
from src.agents.base_agent import BaseAgent
from src.models.contracts import AgentMessage, Article, RunContext


class DeduplicateAgent(BaseAgent):
    """Deduplicates articles and ranks by relevance"""

    def __init__(self, dedup_cache_file: str = "./data/dedup_cache.json"):
        """Initialize deduplication agent
        
        Args:
            dedup_cache_file: Path to persistence cache for dedup history
        """
        super().__init__("deduper")
        self.dedup_cache_file = dedup_cache_file
        self._seen_urls: Set[str] = set()
        self._load_cache()

    def execute(self, context: RunContext, input_data: dict) -> AgentMessage:
        """Deduplicate and rank articles
        
        Args:
            context: Run context
            input_data: Should contain 'articles' list
            
        Returns:
            AgentMessage: Result with deduplicated articles
        """
        msg = self.create_message(context, "deduplicate")
        
        try:
            articles_data = input_data.get("articles", [])
            articles = [Article(**a) for a in articles_data]
            
            deduplicated = self._deduplicate(articles)
            deduplicated = self._rank_by_relevance(deduplicated)
            
            context.deduplicated_count = len(deduplicated)
            removed_count = len(articles) - len(deduplicated)
            
            return msg.with_success(
                payload={
                    "articles": [a.model_dump() for a in deduplicated],
                    "removed_count": removed_count
                },
                metadata={
                    "unique_count": len(deduplicated),
                    "removed_count": removed_count,
                    "original_count": len(articles)
                }
            )
        except Exception as e:
            return msg.with_error(f"Deduplication failed: {str(e)}")

    def _deduplicate(self, articles: List[Article]) -> List[Article]:
        """Deduplicate articles using three-layer approach
        
        Args:
            articles: List of articles to deduplicate
            
        Returns:
            List[Article]: Deduplicated articles
        """
        seen_url_hashes: Set[str] = set()
        seen_semantic_hashes: Set[str] = set()
        deduplicated = []
        
        for article in articles:
            # Layer 1: Canonical URL dedup
            canonical_url = self._get_canonical_url(article.url)
            url_hash = hashlib.md5(canonical_url.encode()).hexdigest()
            
            if url_hash in seen_url_hashes or url_hash in self._seen_urls:
                continue
            
            # Layer 2: Semantic dedup (title + source + date)
            semantic_hash = self._get_semantic_hash(article)
            
            if semantic_hash in seen_semantic_hashes:
                continue
            
            # Not a duplicate
            deduplicated.append(article)
            seen_url_hashes.add(url_hash)
            seen_semantic_hashes.add(semantic_hash)
            self._seen_urls.add(url_hash)
        
        return deduplicated

    def _rank_by_relevance(self, articles: List[Article]) -> List[Article]:
        """Sort articles by relevance score (highest first)
        
        Args:
            articles: List of articles
            
        Returns:
            List[Article]: Sorted articles
        """
        return sorted(articles, key=lambda a: a.relevance_score, reverse=True)

    def _get_canonical_url(self, url: str) -> str:
        """Get canonical form of URL for deduplication
        
        Args:
            url: Original URL
            
        Returns:
            str: Canonical URL
        """
        try:
            parsed = urlparse(url)
            # Combine domain and path only, ignore query/fragment
            return f"{parsed.netloc}{parsed.path}"
        except:
            return url

    def _get_semantic_hash(self, article: Article) -> str:
        """Create semantic hash from article metadata
        
        Args:
            article: Article to hash
            
        Returns:
            str: Semantic hash
        """
        content = f"{article.title[:100]}_{article.source}_{article.published_at or 'unknown'}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_cache(self):
        """Load deduplication cache from file"""
        import json
        import os
        
        if os.path.exists(self.dedup_cache_file):
            try:
                with open(self.dedup_cache_file, "r") as f:
                    data = json.load(f)
                    self._seen_urls = set(data.get("seen_urls", []))
            except:
                pass

    def _save_cache(self):
        """Save deduplication cache to file"""
        import json
        import os
        
        os.makedirs(os.path.dirname(self.dedup_cache_file) or ".", exist_ok=True)
        
        try:
            with open(self.dedup_cache_file, "w") as f:
                json.dump({"seen_urls": list(self._seen_urls)}, f)
        except:
            pass
