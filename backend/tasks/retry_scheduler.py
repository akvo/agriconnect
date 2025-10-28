"""
Background task scheduler for automatic message retry

Runs periodic jobs to retry failed messages using exponential backoff.
Jobs run at intervals matching the retry backoff schedule (5min, 15min, 60min).
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import SessionLocal
from services.retry_service import RetryService
from config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def retry_failed_messages():
    """
    Background task to retry failed messages.
    This function is called by the scheduler.
    """
    try:
        logger.info("Starting retry task for failed messages")

        # Create new database session for this task
        db = SessionLocal()
        try:
            retry_service = RetryService(db)
            stats = retry_service.retry_all_pending()

            logger.info(
                "Retry task completed: "
                f"{stats['total_attempted']} messages checked, "
                f"{stats['successful']} succeeded, {stats['failed']} failed"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in retry background task: {e}")


def start_retry_scheduler():
    """
    Start the background scheduler for message retries.
    Runs every 5 minutes to check for messages that need retry.
    """
    global scheduler

    if not settings.retry_enabled:
        logger.info("Message retry is disabled in config, skipping scheduler")
        return

    if scheduler is not None:
        logger.warning("Retry scheduler already running")
        return

    try:
        scheduler = BackgroundScheduler(timezone="UTC")

        # Run every 5 minutes (the minimum backoff interval)
        # This ensures we catch messages as soon as they're ready for retry
        scheduler.add_job(
            func=retry_failed_messages,
            trigger=IntervalTrigger(minutes=5),
            id="retry_failed_messages",
            name="Retry failed WhatsApp messages",
            replace_existing=True,
        )

        scheduler.start()
        logger.info("✓ Retry scheduler started (runs every 5 minutes)")

    except Exception as e:
        logger.error(f"Failed to start retry scheduler: {e}")


def stop_retry_scheduler():
    """
    Stop the background scheduler.
    Called during application shutdown.
    """
    global scheduler

    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Retry scheduler stopped")


def get_scheduler_status() -> dict:
    """
    Get current status of the retry scheduler.

    Returns:
        Dict with scheduler status information
    """
    global scheduler

    if scheduler is None:
        return {
            "running": False,
            "enabled": settings.retry_enabled,
            "jobs": [],
        }

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": (
                job.next_run_time.isoformat()
                if job.next_run_time else None
            ),
        })

    return {
        "running": scheduler.running,
        "enabled": settings.retry_enabled,
        "jobs": jobs,
    }
