"""
Celery application configuration for AgriConnect.
Following Akvo RAG pattern with auto-constructed broker URLs.
"""
from celery import Celery
from celery.schedules import crontab
from config import settings

# Create Celery app (auto-construct URLs like Akvo RAG)
celery_app = Celery(
    "agriconnect",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # Soft limit at 4 minutes
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    result_expires=3600,  # Results expire after 1 hour
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Retry failed broadcasts every 5 minutes
    "retry-failed-broadcasts": {
        "task": "tasks.broadcast_tasks.retry_failed_broadcasts",
        "schedule": crontab(minute="*/5"),
    },
}

# Auto-discover tasks - Celery will import them when needed
celery_app.autodiscover_tasks(lambda: ["tasks"])
