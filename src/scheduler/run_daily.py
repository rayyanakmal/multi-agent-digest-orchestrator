"""APScheduler setup for daily digest runs"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from src.orchestrator import DailyDigestOrchestrator
from src.config import get_settings


logger = logging.getLogger(__name__)


class DigestScheduler:
    """Manages scheduled digest runs"""

    def __init__(self):
        """Initialize scheduler"""
        self.settings = get_settings()
        self.scheduler = BackgroundScheduler()
        self.orchestrator = DailyDigestOrchestrator()
        self._is_running = False

    def start(self):
        """Start the scheduler"""
        if self._is_running:
            logger.warning("Scheduler already running")
            return
        
        # Parse time from settings (format: HH:MM)
        time_parts = self.settings.digest_time.split(":")
        hour = int(time_parts[0])
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        
        # Create timezone
        tz = timezone(self.settings.digest_tz)
        
        # Schedule daily run
        trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
        self.scheduler.add_job(
            self._run_digest,
            trigger=trigger,
            id="daily_digest",
            name="Daily Digest Runner",
            max_instances=1  # Prevent overlapping runs
        )
        
        self.scheduler.start()
        self._is_running = True
        logger.info(f"Scheduler started. Daily digest at {self.settings.digest_time} {self.settings.digest_tz}")

    def stop(self):
        """Stop the scheduler"""
        if self._is_running:
            self.scheduler.shutdown()
            self._is_running = False
            logger.info("Scheduler stopped")

    def _run_digest(self):
        """Execute digest pipeline (called by scheduler)"""
        logger.info("Running scheduled digest...")
        try:
            context = self.orchestrator.run_digest_pipeline()
            logger.info(f"Digest run completed with status: {context.status}")
        except Exception as e:
            logger.error(f"Scheduled digest run failed: {str(e)}")
