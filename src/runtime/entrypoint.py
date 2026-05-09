"""Application entrypoint supporting multiple run modes"""

import logging
import sys
import os
from src.config import get_settings
from src.orchestrator import DailyDigestOrchestrator
from src.scheduler import DigestScheduler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entrypoint supporting run modes: once | scheduler"""
    settings = get_settings()
    
    logger.info(f"Starting Daily Digest App (mode: {settings.run_mode})")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Topic: {settings.digest_topic}")
    
    if settings.run_mode == "once":
        # Single run mode - execute once and exit
        logger.info("Running in ONCE mode - single execution")
        orchestrator = DailyDigestOrchestrator()
        
        try:
            context = orchestrator.run_digest_pipeline()
            logger.info(f"Run completed with status: {context.status}")
            logger.info(f"Metadata: fetch={context.fetch_count}, dedupe={context.deduplicated_count}, summarized={context.summarized_count}, cost=${context.budget_spent_usd:.4f}")
            
            # Exit with code 0 on success, 1 on failure
            sys.exit(0 if context.status in ["success", "partial"] else 1)
        except Exception as e:
            logger.error(f"Run failed: {str(e)}")
            sys.exit(1)
    
    elif settings.run_mode == "scheduler":
        # Scheduler mode - run daily at configured time
        logger.info(f"Running in SCHEDULER mode - daily at {settings.digest_time} {settings.digest_tz}")
        scheduler = DigestScheduler()
        
        try:
            scheduler.start()
            # Keep scheduler running
            logger.info("Scheduler started. Press Ctrl+C to stop.")
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.stop()
            sys.exit(0)
        except Exception as e:
            logger.error(f"Scheduler error: {str(e)}")
            sys.exit(1)
    
    else:
        logger.error(f"Unknown run mode: {settings.run_mode}. Use 'once' or 'scheduler'")
        sys.exit(1)


if __name__ == "__main__":
    main()
