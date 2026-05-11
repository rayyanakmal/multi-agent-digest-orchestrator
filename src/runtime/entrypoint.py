"""Application entrypoint supporting multiple run modes"""

import logging
import sys
import os
import signal
from src.config import get_settings
from src.orchestrator import DailyDigestOrchestrator
from src.scheduler import DigestScheduler


logger = logging.getLogger(__name__)


class PipelineTimeoutError(RuntimeError):
    """Raised when a run exceeds the configured timeout budget."""


def _configure_logging(log_level: str):
    """Configure root logger from runtime settings."""
    numeric_level = getattr(logging, str(log_level).upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def _run_with_timeout(orchestrator: DailyDigestOrchestrator, timeout_seconds: int):
    """Run orchestrator with a POSIX alarm timeout guard."""

    if timeout_seconds <= 0:
        return orchestrator.run_digest_pipeline()

    def _timeout_handler(signum, frame):
        raise PipelineTimeoutError(f"digest_pipeline_exceeded_timeout:{timeout_seconds}s")

    previous_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        return orchestrator.run_digest_pipeline()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def main():
    """Main entrypoint supporting run modes: once | scheduler"""
    settings = get_settings()
    _configure_logging(settings.log_level)
    
    logger.info(f"Starting Daily Digest App (mode: {settings.run_mode})")
    logger.info(f"App Version: {settings.app_version}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"Topic: {settings.digest_topic}")
    
    if settings.run_mode == "once":
        # Single run mode - execute once and exit
        logger.info("Running in ONCE mode - single execution")
        orchestrator = DailyDigestOrchestrator()
        
        try:
            context = _run_with_timeout(orchestrator, settings.max_run_seconds)
            logger.info(f"Run completed with status: {context.status}")
            logger.info(f"Metadata: fetch={context.fetch_count}, dedupe={context.deduplicated_count}, summarized={context.summarized_count}, cost=${context.budget_spent_usd:.4f}")
            
            # Exit with code 0 on success, 1 on failure
            sys.exit(0 if context.status in ["success", "partial"] else 1)
        except PipelineTimeoutError as timeout_error:
            logger.error("Run timed out after %ss: %s", settings.max_run_seconds, timeout_error)
            sys.exit(1)
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
