"""Daily digest orchestration flow"""

import uuid
import logging
from datetime import datetime
from src.models.contracts import RunContext, RunStatus
from src.agents.fetch_newsapi import NewsAPIFetcher
from src.agents.fetch_rss import RSSFetcher
from src.agents.fetch_github_trending import GitHubTrendingFetcher
from src.agents.deduper import DeduplicateAgent
from src.agents.summarizer import SummarizationAgent
from src.agents.publish_digest import DigestFormatterAgent
from src.agents.drive_uploader import DriveUploadAgent
from src.config import get_settings


logger = logging.getLogger(__name__)


class DailyDigestOrchestrator:
    """Orchestrates the multi-agent daily digest pipeline"""

    def __init__(self):
        """Initialize orchestrator with agents"""
        self.settings = get_settings()
        
        # Initialize agents
        self.fetcher_newsapi = NewsAPIFetcher()
        self.fetcher_rss = RSSFetcher()
        self.fetcher_github = GitHubTrendingFetcher()
        self.deduper = DeduplicateAgent()
        self.summarizer = SummarizationAgent()
        self.formatter = DigestFormatterAgent()
        self.uploader = DriveUploadAgent()

    def run_digest_pipeline(self) -> RunContext:
        """Execute the full digest pipeline
        
        Returns:
            RunContext: Final run context with results
        """
        # Initialize run context
        run_id = f"digest-{datetime.utcnow().strftime('%Y-%m-%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        context = RunContext(run_id=run_id)
        business_date = self.settings.get_digest_date_str()
        
        logger.info(f"Starting digest run: {run_id}")
        logger.info(f"Business digest date: {business_date} ({self.settings.digest_tz})")
        
        try:
            # Phase 1: Fetch articles from multiple sources
            logger.info("Phase 1: Fetching articles from News API and RSS")
            newsapi_result = self.fetcher_newsapi.execute(context, {"topic": self.settings.digest_topic})
            if newsapi_result.status == "error":
                logger.warning(f"NewsAPI fetch failed: {newsapi_result.error}")
                newsapi_articles = []
            else:
                newsapi_articles = newsapi_result.payload.get("articles", [])
            
            rss_result = self.fetcher_rss.execute(context, {})
            if rss_result.status == "error":
                logger.warning(f"RSS fetch failed: {rss_result.error}")
                rss_articles = []
            else:
                rss_articles = rss_result.payload.get("articles", [])

            github_result = self.fetcher_github.execute(context, {"limit": 5})
            if github_result.status == "error":
                logger.warning(f"GitHub trending fetch failed: {github_result.error}")
                github_articles = []
            else:
                github_articles = github_result.payload.get("articles", [])
            
            all_articles = newsapi_articles + rss_articles + github_articles
            logger.info(f"Fetched {len(all_articles)} articles total")
            
            # Phase 2: Deduplicate
            logger.info("Phase 2: Deduplicating articles")
            dedup_result = self.deduper.execute(context, {"articles": all_articles})
            if dedup_result.status == "error":
                logger.error(f"Deduplication failed: {dedup_result.error}")
                context.status = RunStatus.FAILED
                return context
            
            deduplicated_articles = dedup_result.payload.get("articles", [])
            logger.info(f"After dedup: {len(deduplicated_articles)} articles")
            
            # Phase 3: Summarize
            logger.info("Phase 3: Summarizing articles")
            summary_result = self.summarizer.execute(context, {"articles": deduplicated_articles})
            if summary_result.status == "error":
                logger.warning(f"Summarization had issues: {summary_result.error}")
                # Continue even if summarization fails partially
                summaries = []
            else:
                summaries = summary_result.payload.get("summaries", [])
            
            logger.info(f"Summarized {len(summaries)} articles")
            
            # Phase 4: Format digest
            logger.info("Phase 4: Formatting digest")
            format_result = self.formatter.execute(context, {"summaries": summaries})
            if format_result.status == "error":
                logger.error(f"Formatting failed: {format_result.error}")
                context.status = RunStatus.FAILED
                return context
            
            digest = format_result.payload
            logger.info(f"Prepared digest payload date: {digest.get('date', '<missing>')}")
            
            # Phase 5: Upload to Drive (with local fallback)
            logger.info("Phase 5: Uploading to Google Drive")
            upload_result = self.uploader.execute(context, {"digest": digest})
            
            if upload_result.status == "success":
                if upload_result.payload.get("fallback"):
                    if self.settings.strict_pdf_only:
                        logger.error(
                            "Strict PDF mode violation: fallback payload returned as success for business date %s",
                            business_date,
                        )
                        context.status = RunStatus.FAILED
                        context.errors.append("strict_pdf_violation_success_fallback")
                        return context
                    logger.warning(
                        f"Drive upload unavailable for business date {business_date}. Saved locally at: {upload_result.payload.get('local_file')}"
                    )
                    context.status = RunStatus.PARTIAL
                else:
                    logger.info(
                        f"Successfully uploaded to Drive for business date {business_date}: {upload_result.payload.get('document_url')}"
                    )
                    context.status = RunStatus.SUCCESS
            else:
                if self.settings.strict_pdf_only:
                    logger.error(
                        "Strict PDF publish failed for business date %s: %s",
                        business_date,
                        upload_result.error,
                    )
                else:
                    logger.error(f"Upload failed with no fallback: {upload_result.error}")
                context.status = RunStatus.FAILED
            
            context.end_time = datetime.utcnow()
            return context
            
        except Exception as e:
            logger.error(f"Orchestrator error: {str(e)}")
            context.status = RunStatus.FAILED
            context.errors.append(str(e))
            context.end_time = datetime.utcnow()
            return context
